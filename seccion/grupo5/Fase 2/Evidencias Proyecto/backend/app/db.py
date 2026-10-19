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

if LECTOR and not re.fullmatch(r"\w+", LECTOR):
    raise ValueError("DB_USUARIO_LECTOR solo puede tener letras, números y _")


def _conectar() -> pyodbc.Connection:
    partes = [f"DRIVER={{{DRIVER}}}", f"SERVER={SERVIDOR}", f"DATABASE={BASE}", "TrustServerCertificate=yes"]
    partes += [f"UID={USUARIO}", f"PWD={CLAVE}"] if USUARIO else ["Trusted_Connection=yes"]
    return pyodbc.connect(";".join(partes), timeout=5)


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
