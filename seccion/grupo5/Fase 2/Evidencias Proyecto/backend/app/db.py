"""Acceso a SQL Server (DB_BI_RUTA_SMART).

Las lecturas de seguridad y metadatos usan la conexión normal del backend.
Las consultas de los reportes se ejecutan impersonando a bi_lector, un usuario
que solo tiene SELECT sobre ods y dim (ver db/sqlserver/16_CREATE_USUARIO_LECTOR.sql):
aunque llegara un SQL malicioso, SQL Server rechazaría escribir o leer otras capas.
"""

import json
import os
import re
from contextlib import closing
from datetime import date
from decimal import Decimal

import pyodbc

SERVIDOR = os.getenv("DB_SERVER", r"localhost\MSSQLSERVER01")
BASE = os.getenv("DB_NAME", "DB_BI_RUTA_SMART")
DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")
USUARIO = os.getenv("DB_USER", "")  # vacío = autenticación de Windows
CLAVE = os.getenv("DB_PASSWORD", "")
LECTOR = os.getenv("DB_USUARIO_LECTOR", "bi_lector")  # vacío = no impersonar
TIEMPO_CONEXION = int(os.getenv("DB_TIMEOUT", "5"))  # en Azure SQL, más alto: la base puede estar pausada
# Tope por consulta: si SQL Server se queda sin memoria, la pantalla recibe un error claro
# en vez de esperar para siempre
TIEMPO_CONSULTA = int(os.getenv("DB_TIMEOUT_CONSULTA", "60"))

if LECTOR and not re.fullmatch(r"\w+", LECTOR):
    raise ValueError("DB_USUARIO_LECTOR solo puede tener letras, números y _")


def _conectar() -> pyodbc.Connection:
    partes = [f"DRIVER={{{DRIVER}}}", f"SERVER={SERVIDOR}", f"DATABASE={BASE}", "TrustServerCertificate=yes"]
    partes += [f"UID={USUARIO}", f"PWD={CLAVE}"] if USUARIO else ["Trusted_Connection=yes"]
    con = pyodbc.connect(";".join(partes), timeout=TIEMPO_CONEXION)
    con.timeout = TIEMPO_CONSULTA
    return con


def es_tiempo_agotado(e: Exception) -> bool:
    """La consulta o el inicio de sesión superó el tiempo máximo (SQLSTATE HYT00/HYT01)."""
    return any(codigo in str(e) for codigo in ("HYT00", "HYT01"))


def _consultar(sql: str, params: tuple = ()) -> list[tuple]:
    with closing(_conectar()) as con:
        return con.cursor().execute(sql, params).fetchall()


def _a_json(valor):
    if isinstance(valor, Decimal):
        return int(valor) if valor == valor.to_integral_value() else float(valor)
    if isinstance(valor, date):
        return valor.isoformat()
    return valor


# --- Seguridad ---------------------------------------------------------------

def dominios() -> dict[str, str]:
    return dict(_consultar("SELECT COD_DOMINIO, DESC_DOMINIO FROM seguridad.SEG_DOMINIO ORDER BY ID_DOMINIO"))


def usuario(cod_usuario: str) -> dict | None:
    """Usuario activo con el hash de su clave (solo para validar el login)."""
    fila = _consultar(
        """SELECT COD_USUARIO, DESC_NOMBRE, DESC_CLAVE_HASH FROM seguridad.SEG_USUARIO
           WHERE COD_USUARIO = ? AND FLG_ACTIVO = 1""",
        (cod_usuario,),
    )
    return {"usuario": fila[0][0], "nombre": fila[0][1], "clave_hash": fila[0][2]} if fila else None


def dominios_autorizados(cod_usuario: str) -> set[str] | None:
    """Dominios que el usuario puede consultar, o None si no existe o está inactivo."""
    activo = _consultar("SELECT FLG_ACTIVO FROM seguridad.SEG_USUARIO WHERE COD_USUARIO = ?", (cod_usuario,))
    if not activo or not activo[0][0]:
        return None
    filas = _consultar(
        """SELECT D.COD_DOMINIO
           FROM seguridad.SEG_USUARIO_DOMINIO UD
           JOIN seguridad.SEG_USUARIO U ON U.ID_USUARIO = UD.ID_USUARIO
           JOIN seguridad.SEG_DOMINIO D ON D.ID_DOMINIO = UD.ID_DOMINIO
           WHERE U.COD_USUARIO = ? AND UD.FLG_PUEDE_CONSULTAR = 1""",
        (cod_usuario,),
    )
    return {fila[0] for fila in filas}


# --- Perfil y administración de usuarios --------------------------------------

def perfil(cod_usuario: str) -> dict | None:
    fila = _consultar(
        """SELECT COD_USUARIO, DESC_NOMBRE, DESC_CORREO, FLG_SUPERADMIN FROM seguridad.SEG_USUARIO
           WHERE COD_USUARIO = ? AND FLG_ACTIVO = 1""",
        (cod_usuario,),
    )
    if not fila:
        return None
    return {"usuario": fila[0][0], "nombre": fila[0][1], "correo": fila[0][2], "superadmin": bool(fila[0][3])}


def listar_usuarios() -> list[dict]:
    usuarios = {
        f[0]: {"usuario": f[0], "nombre": f[1], "correo": f[2] or "", "activo": bool(f[3]), "superadmin": bool(f[4]), "dominios": []}
        for f in _consultar(
            """SELECT COD_USUARIO, DESC_NOMBRE, DESC_CORREO, FLG_ACTIVO, FLG_SUPERADMIN
               FROM seguridad.SEG_USUARIO ORDER BY COD_USUARIO"""
        )
    }
    for cod_usuario, cod_dominio in _consultar(
        """SELECT U.COD_USUARIO, D.COD_DOMINIO
           FROM seguridad.SEG_USUARIO_DOMINIO UD
           JOIN seguridad.SEG_USUARIO U ON U.ID_USUARIO = UD.ID_USUARIO
           JOIN seguridad.SEG_DOMINIO D ON D.ID_DOMINIO = UD.ID_DOMINIO
           WHERE UD.FLG_PUEDE_CONSULTAR = 1"""
    ):
        usuarios[cod_usuario]["dominios"].append(cod_dominio)
    return list(usuarios.values())


def guardar_usuario(cod_usuario: str, nombre: str, correo: str | None, activo: bool, superadmin: bool,
                    dominios: list[str], crear: bool) -> bool:
    """Crea o actualiza el usuario y sus áreas en una transacción.
    False si al crear ya existe, o si al actualizar no existe. Un usuario nuevo no tiene
    clave: la define con el enlace de recuperación."""
    with closing(_conectar()) as con:
        cursor = con.cursor()
        if crear:
            if cursor.execute("SELECT 1 FROM seguridad.SEG_USUARIO WHERE COD_USUARIO = ?", (cod_usuario,)).fetchone():
                return False
            fila = cursor.execute(
                """INSERT INTO seguridad.SEG_USUARIO (COD_USUARIO, DESC_NOMBRE, DESC_CORREO, FLG_ACTIVO, FLG_SUPERADMIN)
                   OUTPUT inserted.ID_USUARIO VALUES (?, ?, ?, ?, ?)""",
                (cod_usuario, nombre, correo, activo, superadmin),
            ).fetchone()
        else:
            fila = cursor.execute(
                """UPDATE seguridad.SEG_USUARIO
                   SET DESC_NOMBRE = ?, DESC_CORREO = ?, FLG_ACTIVO = ?, FLG_SUPERADMIN = ?
                   OUTPUT inserted.ID_USUARIO WHERE COD_USUARIO = ?""",
                (nombre, correo, activo, superadmin, cod_usuario),
            ).fetchone()
            if fila is None:
                return False
        id_usuario = fila[0]
        cursor.execute("DELETE FROM seguridad.SEG_USUARIO_DOMINIO WHERE ID_USUARIO = ?", (id_usuario,))
        for dominio in dominios:
            cursor.execute(
                """INSERT INTO seguridad.SEG_USUARIO_DOMINIO (ID_USUARIO, ID_DOMINIO, FLG_PUEDE_CONSULTAR)
                   SELECT ?, ID_DOMINIO, 1 FROM seguridad.SEG_DOMINIO WHERE COD_DOMINIO = ?""",
                (id_usuario, dominio),
            )
        con.commit()
    return True


# --- Solicitudes de acceso -----------------------------------------------------

def crear_solicitud(nombre: str, correo: str, areas: list[str], motivo: str, ip_hash: str,
                    max_correo: int, max_ip: int, max_total: int) -> bool:
    """Registra la solicitud si no supera los límites de las últimas 24 horas.
    False también si ya tiene una pendiente o si el correo ya pertenece a una cuenta."""
    with closing(_conectar()) as con:
        cursor = con.cursor()
        total, por_correo, por_ip = cursor.execute(
            """SELECT COUNT(*),
                      COALESCE(SUM(CASE WHEN DESC_CORREO = ? THEN 1 ELSE 0 END), 0),
                      COALESCE(SUM(CASE WHEN DESC_IP_HASH = ? THEN 1 ELSE 0 END), 0)
               FROM seguridad.SEG_SOLICITUD_ACCESO WITH (UPDLOCK, HOLDLOCK)
               WHERE DT_CREADO > DATEADD(DAY, -1, SYSUTCDATETIME())""",
            (correo, ip_hash),
        ).fetchone()
        if total >= max_total or por_correo >= max_correo or por_ip >= max_ip:
            return False
        repetida = cursor.execute(
            """SELECT 1 WHERE EXISTS (SELECT 1 FROM seguridad.SEG_SOLICITUD_ACCESO
                                      WHERE DESC_CORREO = ? AND COD_ESTADO = 'PENDIENTE')
                          OR EXISTS (SELECT 1 FROM seguridad.SEG_USUARIO WHERE DESC_CORREO = ?)""",
            (correo, correo),
        ).fetchone()
        if repetida:
            return False
        cursor.execute(
            """INSERT INTO seguridad.SEG_SOLICITUD_ACCESO (DESC_NOMBRE, DESC_CORREO, DESC_AREAS, DESC_MOTIVO, DESC_IP_HASH)
               VALUES (?, ?, ?, ?, ?)""",
            (nombre, correo, ",".join(areas), motivo, ip_hash),
        )
        con.commit()
    return True


def contar_solicitudes_pendientes() -> int:
    return _consultar("SELECT COUNT(*) FROM seguridad.SEG_SOLICITUD_ACCESO WHERE COD_ESTADO = 'PENDIENTE'")[0][0]


def listar_solicitudes() -> list[dict]:
    filas = _consultar(
        """SELECT ID_SOLICITUD, DESC_NOMBRE, DESC_CORREO, DESC_AREAS, DESC_MOTIVO, CONVERT(CHAR(10), DT_CREADO, 120)
           FROM seguridad.SEG_SOLICITUD_ACCESO WHERE COD_ESTADO = 'PENDIENTE' ORDER BY DT_CREADO"""
    )
    return [
        {"id": f[0], "nombre": f[1], "correo": f[2], "areas": [a for a in f[3].split(",") if a], "motivo": f[4], "fecha": f[5]}
        for f in filas
    ]


def resolver_solicitud(id_solicitud: int, estado: str, resuelto_por: str | None) -> bool:
    """Cambia de estado una solicitud. False si ya no está en el estado esperado."""
    origen = "APROBADA" if estado == "PENDIENTE" else "PENDIENTE"
    with closing(_conectar()) as con:
        cursor = con.cursor()
        cursor.execute(
            """UPDATE seguridad.SEG_SOLICITUD_ACCESO
               SET COD_ESTADO = ?, DT_RESUELTO = CASE WHEN ? = 'PENDIENTE' THEN NULL ELSE SYSUTCDATETIME() END,
                   COD_RESUELTO_POR = ?
               WHERE ID_SOLICITUD = ? AND COD_ESTADO = ?""",
            (estado, estado, resuelto_por, id_solicitud, origen),
        )
        cambiada = cursor.rowcount == 1
        con.commit()
    return cambiada


# --- Recuperación de contraseña -----------------------------------------------

def usuario_para_recuperar(cod_usuario: str) -> dict | None:
    """Usuario activo con correo registrado."""
    fila = _consultar(
        """SELECT ID_USUARIO, COD_USUARIO, DESC_NOMBRE, DESC_CORREO FROM seguridad.SEG_USUARIO
           WHERE FLG_ACTIVO = 1 AND DESC_CORREO IS NOT NULL AND COD_USUARIO = ?""",
        (cod_usuario,),
    )
    if not fila:
        return None
    return {"id": fila[0][0], "usuario": fila[0][1], "nombre": fila[0][2], "correo": fila[0][3]}


def crear_recuperacion(id_usuario: int, token_hash: str, minutos: int, maximo_por_hora: int) -> bool:
    """Registra un enlace nuevo y anula los anteriores. False si superó el límite por hora."""
    with closing(_conectar()) as con:
        cursor = con.cursor()
        recientes = cursor.execute(
            """SELECT COUNT(*) FROM seguridad.SEG_RECUPERACION_CLAVE WITH (UPDLOCK, HOLDLOCK)
               WHERE ID_USUARIO = ? AND DT_CREADO > DATEADD(HOUR, -1, SYSUTCDATETIME())""",
            (id_usuario,),
        ).fetchone()[0]
        if recientes >= maximo_por_hora:
            return False
        cursor.execute(
            """UPDATE seguridad.SEG_RECUPERACION_CLAVE SET DT_USADO = SYSUTCDATETIME()
               WHERE ID_USUARIO = ? AND DT_USADO IS NULL""",
            (id_usuario,),
        )
        cursor.execute(
            """INSERT INTO seguridad.SEG_RECUPERACION_CLAVE (ID_USUARIO, DESC_TOKEN_HASH, DT_VENCE)
               VALUES (?, ?, DATEADD(MINUTE, ?, SYSUTCDATETIME()))""",
            (id_usuario, token_hash, minutos),
        )
        con.commit()
    return True


def aplicar_recuperacion(token_hash: str, clave_hash: str) -> bool:
    """Consume el enlace y cambia la clave en una sola transacción. El UPDATE con las
    condiciones de vigencia impide que dos solicitudes usen el mismo enlace."""
    with closing(_conectar()) as con:
        cursor = con.cursor()
        fila = cursor.execute(
            """UPDATE seguridad.SEG_RECUPERACION_CLAVE SET DT_USADO = SYSUTCDATETIME()
               OUTPUT inserted.ID_USUARIO
               WHERE DESC_TOKEN_HASH = ? AND DT_USADO IS NULL AND DT_VENCE > SYSUTCDATETIME()""",
            (token_hash,),
        ).fetchone()
        if fila is None:
            return False
        cursor.execute(
            "UPDATE seguridad.SEG_USUARIO SET DESC_CLAVE_HASH = ? WHERE ID_USUARIO = ? AND FLG_ACTIVO = 1",
            (clave_hash, fila[0]),
        )
        if cursor.rowcount != 1:
            con.rollback()
            return False
        con.commit()
    return True


# --- Carpetas y dashboards compartidos (app.*) ----------------------------------
# Una carpeta es un repositorio compartido: su propietario agrega miembros como
# LECTOR o EDITOR y todos ven los mismos dashboards. Un dashboard guarda los PLANES
# de sus gráficos, nunca los datos: al abrirlo se vuelven a ejecutar con los
# permisos de quien lo mira (ver main.py).

PROPIETARIO = "PROPIETARIO"
ROLES_MIEMBRO = ("LECTOR", "EDITOR")

# Condición "el usuario ? ve la carpeta C": es su propietario o es miembro
_VE_CARPETA = """(C.ID_PROPIETARIO = (SELECT ID_USUARIO FROM seguridad.SEG_USUARIO WHERE COD_USUARIO = ?)
                  OR EXISTS (SELECT 1 FROM app.CARPETA_MIEMBRO M
                             JOIN seguridad.SEG_USUARIO U ON U.ID_USUARIO = M.ID_USUARIO
                             WHERE M.ID_CARPETA = C.ID_CARPETA AND U.COD_USUARIO = ?))"""


def directorio() -> list[dict]:
    """Usuarios activos, para elegir con quién compartir. Solo código y nombre."""
    return [{"usuario": f[0], "nombre": f[1]} for f in _consultar(
        "SELECT COD_USUARIO, DESC_NOMBRE FROM seguridad.SEG_USUARIO WHERE FLG_ACTIVO = 1 ORDER BY DESC_NOMBRE"
    )]


def rol_en_carpeta(cod_usuario: str, id_carpeta: int) -> str | None:
    fila = _consultar(
        """SELECT CASE WHEN C.ID_PROPIETARIO = U.ID_USUARIO THEN 'PROPIETARIO' ELSE M.COD_ROL END
           FROM app.CARPETA C
           JOIN seguridad.SEG_USUARIO U ON U.COD_USUARIO = ? AND U.FLG_ACTIVO = 1
           LEFT JOIN app.CARPETA_MIEMBRO M ON M.ID_CARPETA = C.ID_CARPETA AND M.ID_USUARIO = U.ID_USUARIO
           WHERE C.ID_CARPETA = ?""",
        (cod_usuario, id_carpeta),
    )
    return fila[0][0] if fila else None


def rol_en_dashboard(cod_usuario: str, id_dashboard: int) -> str | None:
    """Rol efectivo en un dashboard: el propietario de la carpeta siempre es PROPIETARIO;
    un miembro tiene su excepción para ese dashboard (app.DASHBOARD_PERMISO) o, si no
    hay, su rol en la carpeta. None si no es miembro."""
    fila = _consultar(
        """SELECT CASE WHEN C.ID_PROPIETARIO = U.ID_USUARIO THEN 'PROPIETARIO'
                       WHEN M.COD_ROL IS NULL THEN NULL
                       ELSE COALESCE(P.COD_ROL, M.COD_ROL) END
           FROM app.DASHBOARD D
           JOIN app.CARPETA C ON C.ID_CARPETA = D.ID_CARPETA
           JOIN seguridad.SEG_USUARIO U ON U.COD_USUARIO = ? AND U.FLG_ACTIVO = 1
           LEFT JOIN app.CARPETA_MIEMBRO M ON M.ID_CARPETA = C.ID_CARPETA AND M.ID_USUARIO = U.ID_USUARIO
           LEFT JOIN app.DASHBOARD_PERMISO P ON P.ID_DASHBOARD = D.ID_DASHBOARD AND P.ID_USUARIO = U.ID_USUARIO
           WHERE D.ID_DASHBOARD = ?""",
        (cod_usuario, id_dashboard),
    )
    return fila[0][0] if fila else None


def permisos_dashboard(id_dashboard: int) -> list[dict]:
    """Miembros de la carpeta del dashboard con su rol en la carpeta y su excepción ("" = sin excepción)."""
    return [{"usuario": f[0], "nombre": f[1], "rolCarpeta": f[2], "rol": f[3] or ""} for f in _consultar(
        """SELECT U.COD_USUARIO, U.DESC_NOMBRE, M.COD_ROL, P.COD_ROL
           FROM app.DASHBOARD D
           JOIN app.CARPETA_MIEMBRO M ON M.ID_CARPETA = D.ID_CARPETA
           JOIN seguridad.SEG_USUARIO U ON U.ID_USUARIO = M.ID_USUARIO
           LEFT JOIN app.DASHBOARD_PERMISO P ON P.ID_DASHBOARD = D.ID_DASHBOARD AND P.ID_USUARIO = M.ID_USUARIO
           WHERE D.ID_DASHBOARD = ?
           ORDER BY U.DESC_NOMBRE""",
        (id_dashboard,),
    )]


def guardar_permiso_dashboard(id_dashboard: int, cod_miembro: str, rol: str | None) -> bool:
    """Fija la excepción de un miembro en un dashboard; rol None vuelve a su rol de la
    carpeta. False si la persona no es miembro de la carpeta."""
    with closing(_conectar()) as con:
        cursor = con.cursor()
        fila = cursor.execute(
            """SELECT M.ID_USUARIO FROM app.DASHBOARD D
               JOIN app.CARPETA_MIEMBRO M ON M.ID_CARPETA = D.ID_CARPETA
               JOIN seguridad.SEG_USUARIO U ON U.ID_USUARIO = M.ID_USUARIO
               WHERE D.ID_DASHBOARD = ? AND U.COD_USUARIO = ?""",
            (id_dashboard, cod_miembro),
        ).fetchone()
        if fila is None:
            return False
        cursor.execute("DELETE FROM app.DASHBOARD_PERMISO WHERE ID_DASHBOARD = ? AND ID_USUARIO = ?", (id_dashboard, fila[0]))
        if rol:
            cursor.execute(
                "INSERT INTO app.DASHBOARD_PERMISO (ID_DASHBOARD, ID_USUARIO, COD_ROL) VALUES (?, ?, ?)",
                (id_dashboard, fila[0], rol),
            )
        con.commit()
    return True


def carpetas(cod_usuario: str) -> list[dict]:
    """Carpetas que el usuario ve, con su rol y sus dashboards (sin gráficos). Cada
    dashboard trae el rol efectivo del usuario en él (ver rol_en_dashboard)."""
    lista = {
        f[0]: {"id": f[0], "nombre": f[1], "descripcion": f[2] or "", "propietario": f[3], "rol": f[4],
               "miembros": f[5], "dashboards": []}
        for f in _consultar(
            f"""SELECT C.ID_CARPETA, C.DESC_NOMBRE, C.DESC_DESCRIPCION, P.DESC_NOMBRE,
                       CASE WHEN P.COD_USUARIO = ? THEN 'PROPIETARIO'
                            ELSE (SELECT M.COD_ROL FROM app.CARPETA_MIEMBRO M
                                  JOIN seguridad.SEG_USUARIO U ON U.ID_USUARIO = M.ID_USUARIO
                                  WHERE M.ID_CARPETA = C.ID_CARPETA AND U.COD_USUARIO = ?) END,
                       (SELECT COUNT(*) FROM app.CARPETA_MIEMBRO M WHERE M.ID_CARPETA = C.ID_CARPETA)
                FROM app.CARPETA C
                JOIN seguridad.SEG_USUARIO P ON P.ID_USUARIO = C.ID_PROPIETARIO
                WHERE {_VE_CARPETA}
                ORDER BY C.DESC_NOMBRE""",
            (cod_usuario, cod_usuario, cod_usuario, cod_usuario),
        )
    }
    for f in _consultar(
        f"""SELECT D.ID_DASHBOARD, D.ID_CARPETA, D.DESC_NOMBRE, D.DESC_DESCRIPCION,
                   CONVERT(VARCHAR(16), D.DT_ACTUALIZADO, 120), A.DESC_NOMBRE,
                   (SELECT COUNT(*) FROM app.DASHBOARD_GRAFICO G WHERE G.ID_DASHBOARD = D.ID_DASHBOARD),
                   (SELECT P.COD_ROL FROM app.DASHBOARD_PERMISO P
                    JOIN seguridad.SEG_USUARIO U ON U.ID_USUARIO = P.ID_USUARIO
                    WHERE P.ID_DASHBOARD = D.ID_DASHBOARD AND U.COD_USUARIO = ?),
                   (SELECT COUNT(*) FROM app.DASHBOARD_PERMISO P WHERE P.ID_DASHBOARD = D.ID_DASHBOARD)
            FROM app.DASHBOARD D
            JOIN app.CARPETA C ON C.ID_CARPETA = D.ID_CARPETA
            LEFT JOIN seguridad.SEG_USUARIO A ON A.ID_USUARIO = D.ID_ACTUALIZADO_POR
            WHERE {_VE_CARPETA}
            ORDER BY D.DT_ACTUALIZADO DESC""",
        (cod_usuario, cod_usuario, cod_usuario),
    ):
        carpeta = lista.get(f[1])
        if carpeta is None:
            continue  # se creó entre las dos consultas
        rol = carpeta["rol"] if carpeta["rol"] == PROPIETARIO else (f[7] or carpeta["rol"])
        carpeta["dashboards"].append({
            "id": f[0], "nombre": f[2], "descripcion": f[3] or "", "actualizado": f[4],
            "actualizadoPor": f[5] or "", "graficos": f[6], "rol": rol, "excepciones": f[8],
        })
    return list(lista.values())


def crear_carpeta(cod_usuario: str, nombre: str, descripcion: str) -> int:
    with closing(_conectar()) as con:
        fila = con.cursor().execute(
            """INSERT INTO app.CARPETA (DESC_NOMBRE, DESC_DESCRIPCION, ID_PROPIETARIO)
               OUTPUT inserted.ID_CARPETA
               SELECT ?, ?, ID_USUARIO FROM seguridad.SEG_USUARIO WHERE COD_USUARIO = ? AND FLG_ACTIVO = 1""",
            (nombre, descripcion or None, cod_usuario),
        ).fetchone()
        con.commit()
    return fila[0] if fila else None  # None: el usuario no existe o está inactivo


def editar_carpeta(id_carpeta: int, nombre: str, descripcion: str) -> bool:
    with closing(_conectar()) as con:
        cursor = con.cursor()
        cursor.execute(
            "UPDATE app.CARPETA SET DESC_NOMBRE = ?, DESC_DESCRIPCION = ? WHERE ID_CARPETA = ?",
            (nombre, descripcion or None, id_carpeta),
        )
        cambiada = cursor.rowcount == 1
        con.commit()
    return cambiada


def eliminar_carpeta(id_carpeta: int) -> bool:
    """Borra la carpeta con sus dashboards y miembros (ON DELETE CASCADE)."""
    with closing(_conectar()) as con:
        cursor = con.cursor()
        cursor.execute("DELETE FROM app.CARPETA WHERE ID_CARPETA = ?", (id_carpeta,))
        borrada = cursor.rowcount == 1
        con.commit()
    return borrada


def miembros(id_carpeta: int) -> list[dict]:
    """El propietario primero y luego los miembros."""
    return [{"usuario": f[0], "nombre": f[1], "rol": f[2]} for f in _consultar(
        """SELECT U.COD_USUARIO, U.DESC_NOMBRE, 'PROPIETARIO', 0
           FROM app.CARPETA C JOIN seguridad.SEG_USUARIO U ON U.ID_USUARIO = C.ID_PROPIETARIO
           WHERE C.ID_CARPETA = ?
           UNION ALL
           SELECT U.COD_USUARIO, U.DESC_NOMBRE, M.COD_ROL, 1
           FROM app.CARPETA_MIEMBRO M JOIN seguridad.SEG_USUARIO U ON U.ID_USUARIO = M.ID_USUARIO
           WHERE M.ID_CARPETA = ?
           ORDER BY 4, 2""",
        (id_carpeta, id_carpeta),
    )]


def guardar_miembro(id_carpeta: int, cod_miembro: str, rol: str | None) -> bool:
    """Agrega o cambia el rol de un miembro; rol None lo quita. False si el usuario no
    existe, está inactivo o es el propietario."""
    with closing(_conectar()) as con:
        cursor = con.cursor()
        fila = cursor.execute(
            """SELECT U.ID_USUARIO FROM seguridad.SEG_USUARIO U
               JOIN app.CARPETA C ON C.ID_CARPETA = ?
               WHERE U.COD_USUARIO = ? AND U.FLG_ACTIVO = 1 AND U.ID_USUARIO <> C.ID_PROPIETARIO""",
            (id_carpeta, cod_miembro),
        ).fetchone()
        if fila is None:
            return False
        cursor.execute("DELETE FROM app.CARPETA_MIEMBRO WHERE ID_CARPETA = ? AND ID_USUARIO = ?", (id_carpeta, fila[0]))
        if not rol:
            # Sale de la carpeta: sus excepciones por dashboard no deben revivir si vuelve
            cursor.execute(
                """DELETE P FROM app.DASHBOARD_PERMISO P
                   JOIN app.DASHBOARD D ON D.ID_DASHBOARD = P.ID_DASHBOARD
                   WHERE D.ID_CARPETA = ? AND P.ID_USUARIO = ?""",
                (id_carpeta, fila[0]),
            )
        if rol:
            cursor.execute(
                "INSERT INTO app.CARPETA_MIEMBRO (ID_CARPETA, ID_USUARIO, COD_ROL) VALUES (?, ?, ?)",
                (id_carpeta, fila[0], rol),
            )
        con.commit()
    return True


def _insertar_graficos(cursor, id_dashboard: int, graficos: list[tuple[str, str]]) -> None:
    for orden, (titulo, plan_json) in enumerate(graficos, start=1):
        cursor.execute(
            """INSERT INTO app.DASHBOARD_GRAFICO (ID_DASHBOARD, NRO_ORDEN, DESC_TITULO, DESC_PLAN_JSON)
               VALUES (?, ?, ?, ?)""",
            (id_dashboard, orden, titulo, plan_json),
        )


def crear_dashboard(cod_usuario: str, id_carpeta: int, nombre: str, descripcion: str,
                    graficos: list[tuple[str, str]]) -> int:
    """`graficos` = [(título, plan en JSON)], en el orden en que se muestran."""
    with closing(_conectar()) as con:
        cursor = con.cursor()
        id_dashboard = cursor.execute(
            """INSERT INTO app.DASHBOARD (ID_CARPETA, DESC_NOMBRE, DESC_DESCRIPCION, ID_CREADO_POR, ID_ACTUALIZADO_POR)
               OUTPUT inserted.ID_DASHBOARD
               SELECT ?, ?, ?, ID_USUARIO, ID_USUARIO FROM seguridad.SEG_USUARIO WHERE COD_USUARIO = ?""",
            (id_carpeta, nombre, descripcion or None, cod_usuario),
        ).fetchone()[0]
        _insertar_graficos(cursor, id_dashboard, graficos)
        con.commit()
    return id_dashboard


def dashboard(id_dashboard: int) -> dict | None:
    fila = _consultar(
        """SELECT D.ID_DASHBOARD, D.ID_CARPETA, C.DESC_NOMBRE, D.DESC_NOMBRE, D.DESC_DESCRIPCION, D.NUM_VERSION,
                  CONVERT(VARCHAR(16), D.DT_ACTUALIZADO, 120), A.DESC_NOMBRE, R.DESC_NOMBRE
           FROM app.DASHBOARD D
           JOIN app.CARPETA C ON C.ID_CARPETA = D.ID_CARPETA
           LEFT JOIN seguridad.SEG_USUARIO A ON A.ID_USUARIO = D.ID_ACTUALIZADO_POR
           LEFT JOIN seguridad.SEG_USUARIO R ON R.ID_USUARIO = D.ID_CREADO_POR
           WHERE D.ID_DASHBOARD = ?""",
        (id_dashboard,),
    )
    if not fila:
        return None
    f = fila[0]
    graficos = _consultar(
        "SELECT DESC_TITULO, DESC_PLAN_JSON FROM app.DASHBOARD_GRAFICO WHERE ID_DASHBOARD = ? ORDER BY NRO_ORDEN",
        (id_dashboard,),
    )
    return {
        "id": f[0], "carpeta": f[1], "carpetaNombre": f[2], "nombre": f[3], "descripcion": f[4] or "",
        "version": f[5], "actualizado": f[6], "actualizadoPor": f[7] or "", "creadoPor": f[8] or "",
        "graficos": [{"titulo": g[0], "plan": g[1]} for g in graficos],
    }


def actualizar_dashboard(id_dashboard: int, cod_usuario: str, nombre: str, descripcion: str,
                         graficos: list[tuple[str, str]], version: int) -> bool:
    """Reemplaza nombre, descripción y gráficos solo si nadie guardó desde `version`.
    False si hubo un cambio intermedio: así dos editores no se pisan."""
    with closing(_conectar()) as con:
        cursor = con.cursor()
        cursor.execute(
            """UPDATE app.DASHBOARD
               SET DESC_NOMBRE = ?, DESC_DESCRIPCION = ?, NUM_VERSION = NUM_VERSION + 1,
                   DT_ACTUALIZADO = SYSDATETIME(),
                   ID_ACTUALIZADO_POR = (SELECT ID_USUARIO FROM seguridad.SEG_USUARIO WHERE COD_USUARIO = ?)
               WHERE ID_DASHBOARD = ? AND NUM_VERSION = ?""",
            (nombre, descripcion or None, cod_usuario, id_dashboard, version),
        )
        if cursor.rowcount != 1:
            con.rollback()
            return False
        cursor.execute("DELETE FROM app.DASHBOARD_GRAFICO WHERE ID_DASHBOARD = ?", (id_dashboard,))
        _insertar_graficos(cursor, id_dashboard, graficos)
        con.commit()
    return True


def eliminar_dashboard(id_dashboard: int) -> bool:
    with closing(_conectar()) as con:
        cursor = con.cursor()
        cursor.execute("DELETE FROM app.DASHBOARD WHERE ID_DASHBOARD = ?", (id_dashboard,))
        borrado = cursor.rowcount == 1
        con.commit()
    return borrado


# --- Metadatos ---------------------------------------------------------------

def tablas_disponibles() -> dict[str, str]:
    """{tabla: cod_dominio} de las tablas del schema ods activas y disponibles para la IA."""
    filas = _consultar(
        """SELECT T.DESC_TABLA, D.COD_DOMINIO
           FROM meta.MET_TABLA T
           JOIN seguridad.SEG_DOMINIO D ON D.ID_DOMINIO = T.ID_DOMINIO
           WHERE T.DESC_SCHEMA = 'ods' AND T.FLG_ACTIVO = 1 AND T.FLG_DISPONIBLE_IA = 1"""
    )
    return dict(filas)


def relaciones_disponibles() -> set[tuple[str, str, str, str]]:
    """(tabla_origen, columna_origen, tabla_destino, columna_destino) habilitadas en meta.MET_RELACION."""
    filas = _consultar(
        """SELECT TOG.DESC_TABLA, COG.DESC_COLUMNA, TDE.DESC_TABLA, CDE.DESC_COLUMNA
           FROM meta.MET_RELACION R
           JOIN meta.MET_TABLA TOG ON TOG.ID_TABLA = R.ID_TABLA_ORIGEN
           JOIN meta.MET_COLUMNA COG ON COG.ID_COLUMNA = R.ID_COLUMNA_ORIGEN
           JOIN meta.MET_TABLA TDE ON TDE.ID_TABLA = R.ID_TABLA_DESTINO
           JOIN meta.MET_COLUMNA CDE ON CDE.ID_COLUMNA = R.ID_COLUMNA_DESTINO
           WHERE R.FLG_ACTIVO = 1 AND R.FLG_DISPONIBLE_IA = 1"""
    )
    return {tuple(f) for f in filas}


def columnas_disponibles(schema: str, tabla: str) -> dict[str, str]:
    """{columna: descripción de negocio} de las columnas activas y disponibles para la IA."""
    filas = _consultar(
        """SELECT C.DESC_COLUMNA, C.DESC_NEGOCIO
           FROM meta.MET_COLUMNA C
           JOIN meta.MET_TABLA T ON T.ID_TABLA = C.ID_TABLA
           WHERE T.DESC_SCHEMA = ? AND T.DESC_TABLA = ?
             AND C.FLG_ACTIVO = 1 AND C.FLG_DISPONIBLE_IA = 1
           ORDER BY C.ID_COLUMNA""",
        (schema, tabla),
    )
    return dict(filas)


# origen y columna vienen de las constantes de catalogo.py, nunca del usuario
def valores_distintos(origen: str, columna: str) -> list[str]:
    return [fila[0] for fila in _consultar(f"SELECT DISTINCT {columna} FROM {origen} ORDER BY {columna}")]


def registros_por_mes(origen: str, columna: str) -> dict[str, int]:
    mes = f"CONVERT(CHAR(7), {columna}, 120)"
    return {f[0]: f[1] for f in _consultar(f"SELECT {mes}, COUNT(*) FROM {origen} WHERE {columna} IS NOT NULL GROUP BY {mes}")}


def rango_meses(origen: str, columna: str) -> tuple[str, str] | None:
    fila = _consultar(
        f"SELECT CONVERT(CHAR(7), MIN({columna}), 120), CONVERT(CHAR(7), MAX({columna}), 120) FROM {origen}"
    )[0]
    return (fila[0], fila[1]) if fila[0] else None


# --- Reportes ----------------------------------------------------------------

def ejecutar(sql: str, params: list) -> dict:
    """Ejecuta la consulta del reporte con permisos de solo lectura."""
    with closing(_conectar()) as con:
        cursor = con.cursor()
        if LECTOR:
            cursor.execute(f"EXECUTE AS USER = '{LECTOR}'")
        try:
            cursor.execute(sql, params)
            columnas = [c[0] for c in cursor.description]
            filas = [{col: _a_json(v) for col, v in zip(columnas, fila)} for fila in cursor.fetchall()]
        finally:
            con.rollback()  # nada de lo ejecutado aquí debe quedar guardado
            if LECTOR:
                cursor.execute("REVERT")
    return {"columnas": columnas, "filas": filas}


def registrar_consulta(usuario: str, pregunta: str, estado: str, motivo: str | None = None,
                       plan: dict | None = None, sql: str | None = None, uso: dict | None = None,
                       dominio: str | None = None) -> None:
    """Deja traza de cada solicitud (RF-07). Un fallo aquí no debe botar la respuesta."""
    uso = uso or {}
    # Recortes según el largo de las columnas, para que el INSERT no falle
    pregunta, motivo = pregunta[:500], motivo[:1000] if motivo else motivo
    try:
        with closing(_conectar()) as con:
            con.cursor().execute(
                """INSERT INTO seguridad.SEG_LOG_CONSULTA
                   (COD_USUARIO, COD_DOMINIO, DESC_PREGUNTA, COD_ESTADO, DESC_MOTIVO,
                    DESC_PLAN_JSON, DESC_SQL, NUM_TOKENS_ENTRADA, NUM_TOKENS_SALIDA)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (usuario, dominio, pregunta, estado, motivo,
                 json.dumps(plan, ensure_ascii=False) if plan else None, sql,
                 uso.get("entrada"), uso.get("salida")),
            )
            con.commit()
    except pyodbc.Error as e:
        print(f"[SEG_LOG_CONSULTA] no se pudo registrar: {e}")
