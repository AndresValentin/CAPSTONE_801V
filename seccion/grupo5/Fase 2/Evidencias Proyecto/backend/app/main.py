"""API de BI Copilot.

Flujo de POST /api/consultas:
  usuario + pregunta + filtros del panel -> permisos del usuario (seguridad.*)
  -> reglas previas -> catálogo (meta.*) -> IA arma plan -> se suman los filtros
  del panel -> validar plan y dominio -> SQL parametrizado
  -> BD como bi_lector (solo lectura) -> resultado + traza en seguridad.SEG_LOG_CONSULTA

POST /api/reportes vuelve a ejecutar un plan ya armado con otros filtros, sin
llamar a la IA (cambiar un filtro en el panel no gasta tokens).
"""

import hashlib
import os
import secrets

from dotenv import load_dotenv

load_dotenv()  # lee backend/.env antes de crear el cliente de Anthropic

import pyodbc  # noqa: E402
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request, Response  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from . import catalogo, claves, db, powerbi, recuperacion, reporte_html, sesion  # noqa: E402
from .consultas import aplicar_filtros_panel, construir_sql, normalizar_salida, rechazo_previo, validar_plan  # noqa: E402
from .ia import ErrorIA, PlanConsulta, interpretar_con_ia  # noqa: E402

app = FastAPI(title="BI Copilot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


class FiltrosPanel(BaseModel):
    """Filtros elegidos en el panel del dashboard. Se aplican además de los que entienda la IA."""
    filtros: dict[str, str] = Field(default_factory=dict, max_length=20)  # campo -> valor
    desde: str = ""
    hasta: str = ""
    area: str = Field(default="", max_length=10)  # área en pantalla; orienta a la IA


class SolicitudConsulta(BaseModel):
    pregunta: str = Field(min_length=1, max_length=500)
    panel: FiltrosPanel = Field(default_factory=FiltrosPanel)


class SolicitudReporte(BaseModel):
    pregunta: str = Field(min_length=1, max_length=500)  # la original, solo para la traza
    plan: PlanConsulta


class SolicitudSesion(BaseModel):
    usuario: str = Field(min_length=1, max_length=50)  # COD_USUARIO de seguridad.SEG_USUARIO
    clave: str = Field(min_length=1, max_length=200)


# Hash de relleno: si el usuario no existe se verifica igual contra este, para
# que la respuesta tarde lo mismo y no revele qué usuarios existen.
_HASH_RELLENO = claves.generar_hash(secrets.token_hex(8))
_CREDENCIALES_INVALIDAS = "Usuario o contraseña incorrectos."


def usuario_autenticado(authorization: str | None = Header(default=None)) -> str:
    """El usuario sale del token firmado, nunca de lo que diga el cuerpo de la solicitud."""
    token = (authorization or "").removeprefix("Bearer ").strip()
    usuario = sesion.leer_token(token) if token else None
    if usuario is None:
        raise HTTPException(status_code=401, detail="La sesión expiró. Vuelve a iniciar sesión.")
    return usuario


def _interpretacion(plan: PlanConsulta, cat: catalogo.Catalogo) -> dict:
    """Describe el reporte con etiquetas listas para mostrar en el frontend."""
    dominio = cat.disponibles[plan.dominio]
    medida = dominio.medidas[plan.metrica]
    return {
        "intencion": plan.titulo,
        "codDominio": plan.dominio,
        "dominio": cat.dominios[plan.dominio],
        "metrica": plan.metrica,
        "metricaEtiqueta": medida.etiqueta,
        "moneda": medida.moneda,
        "agruparPor": plan.agrupar_por,
        "dimensionEtiqueta": dominio.etiqueta_dimension(plan.agrupar_por),
        "visualizacion": plan.tipo_salida.removeprefix("grafico_"),
        "filtros": [
            {"campo": f.campo, "etiqueta": dominio.atributos[f.campo].etiqueta, "valor": f.valor}
            for f in plan.filtros
        ],
        "desde": plan.desde or None,
        "hasta": plan.hasta or None,
        "tipoSalida": plan.tipo_salida.replace("_", " "),
        "catalogoVersion": catalogo.VERSION,
    }


def _contexto_usuario(usuario: str) -> tuple[set[str], catalogo.Catalogo]:
    try:
        dominios_usuario = db.dominios_autorizados(usuario)
        cat = catalogo.obtener()
    except pyodbc.Error as e:
        raise _error_bd(e) from e
    if dominios_usuario is None:
        raise HTTPException(status_code=403, detail=f"El usuario {usuario} no existe o está inactivo.")
    return catalogo.ampliar_permisos(dominios_usuario), cat


def _describir_panel(panel: FiltrosPanel) -> str:
    partes = [f"{campo} = {valor}" for campo, valor in panel.filtros.items()]
    if panel.desde:
        partes.append(f"desde {panel.desde}")
    if panel.hasta:
        partes.append(f"hasta {panel.hasta}")
    return "; ".join(partes)


def _ejecutar_plan(usuario: str, pregunta: str, plan: PlanConsulta, cat: catalogo.Catalogo,
                   dominios_usuario: set[str], uso: dict | None) -> dict:
    """Valida el plan, corre las consultas y arma la respuesta (con traza en la BD)."""
    plan = normalizar_salida(plan)
    plan_dict = plan.model_dump()
    motivo = validar_plan(plan, cat, dominios_usuario)
    if motivo:
        estado = "aclaracion" if plan.accion == "aclarar" else "rechazado"
        db.registrar_consulta(usuario, pregunta, estado, motivo, plan_dict, uso=uso, dominio=plan.dominio or None)
        return {"estado": estado, "motivo": motivo}

    consultas = construir_sql(plan, cat)
    sql_log = "\n".join(f"-- {nombre}\n{sql}" for nombre, (sql, _) in consultas.items())
    try:
        datos = {nombre: db.ejecutar(sql, params) for nombre, (sql, params) in consultas.items()}
    except pyodbc.Error as e:
        db.registrar_consulta(usuario, pregunta, "error", str(e), plan_dict, sql_log, uso, plan.dominio)
        raise HTTPException(status_code=500, detail="La consulta falló en la base de datos.") from e
    db.registrar_consulta(usuario, pregunta, "validado", plan=plan_dict, sql=sql_log, uso=uso, dominio=plan.dominio)

    total = datos["total"]["filas"][0]
    return {
        "estado": "validado",
        "plan": plan_dict,  # el frontend lo reenvía a /api/reportes al cambiar filtros
        "interpretacion": _interpretacion(plan, cat),
        "resultado": {
            "total": total["valor"] or 0,
            "cantidad": total["cantidad"],
            "serie": datos["serie"]["filas"] if "serie" in datos else [],
            "detalle": {
                **datos.get("detalle", {"columnas": [], "filas": []}),
                "columnasMoneda": [a.etiqueta for a in cat.disponibles[plan.dominio].detalle if a.moneda],
            },
        },
    }


def _error_bd(e: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail="No hay conexión con la base de datos.")


@app.get("/api/salud")
def salud():
    try:
        cat = catalogo.obtener()
    except pyodbc.Error as e:
        raise _error_bd(e) from e
    return {"ok": True, "catalogo": catalogo.VERSION, "dominiosConDatos": sorted(cat.disponibles)}


@app.post("/api/sesion")
def iniciar_sesion(solicitud: SolicitudSesion):
    """Valida usuario y clave contra seguridad.SEG_USUARIO y entrega un token de sesión."""
    cod_usuario = solicitud.usuario.strip().upper()
    try:
        usuario = db.usuario(cod_usuario)
        dominios_usuario = db.dominios_autorizados(cod_usuario) if usuario else None
        nombres = db.dominios()
    except pyodbc.Error as e:
        raise _error_bd(e) from e

    hash_guardado = usuario["clave_hash"] if usuario else _HASH_RELLENO
    clave_correcta = claves.verificar(solicitud.clave, hash_guardado)
    if not usuario or not clave_correcta or dominios_usuario is None:
        raise HTTPException(status_code=401, detail=_CREDENCIALES_INVALIDAS)
    return {
        "token": sesion.crear_token(usuario["usuario"]),
        "usuario": usuario["usuario"],
        "nombre": usuario["nombre"],
        "dominios": [{"codigo": cod, "nombre": nombre} for cod, nombre in nombres.items() if cod in dominios_usuario],
    }


class SolicitudRecuperacion(BaseModel):
    usuario: str = Field(min_length=1, max_length=50)  # COD_USUARIO de seguridad.SEG_USUARIO


class CambioClave(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    clave: str = Field(min_length=8, max_length=200)


@app.post("/api/clave/solicitar")
def solicitar_recuperacion(solicitud: SolicitudRecuperacion, tareas: BackgroundTasks):
    """Responde siempre igual, exista o no la cuenta, y envía el correo en segundo plano."""
    tareas.add_task(recuperacion.solicitar, solicitud.usuario)
    return {"ok": True}


@app.post("/api/clave/restablecer")
def restablecer_clave(solicitud: CambioClave):
    try:
        cambiada = recuperacion.restablecer(solicitud.token, solicitud.clave)
    except pyodbc.Error as e:
        raise _error_bd(e) from e
    if not cambiada:
        raise HTTPException(status_code=400, detail="El enlace no es válido o ya venció. Solicita uno nuevo.")
    return {"ok": True}


@app.get("/api/catalogo")
def ver_catalogo(usuario: str = Depends(usuario_autenticado)):
    """Métricas y filtros disponibles para el chat y el panel: solo los dominios que el
    usuario puede consultar, con los valores reales de la BD."""
    dominios_usuario, cat = _contexto_usuario(usuario)
    return {
        "dominios": [
            {
                "codigo": cod,
                "nombre": cat.dominios[cod],
                "metricas": [{"clave": clave, "etiqueta": m.etiqueta} for clave, m in d.medidas.items()],
                "filtros": [
                    {"campo": campo, "etiqueta": a.etiqueta, "valores": d.valores[campo]}
                    for campo, a in d.atributos.items()
                ],
                "fecha": {"etiqueta": d.definicion.fecha.etiqueta, "desde": d.rango_meses[0], "hasta": d.rango_meses[1]}
                if d.rango_meses else None,
                "recomendaciones": [
                    {"pregunta": r.pregunta, "metrica": r.metrica, "agruparPor": r.agrupar_por, "motivo": r.motivo}
                    for r in catalogo.RECOMENDACIONES.get(cod, ())
                    if r.metrica in d.medidas and r.agrupar_por in d.dimensiones()
                ],
            }
            for cod, d in cat.disponibles.items() if cod in dominios_usuario
        ]
    }


@app.post("/api/consultas")
def consultar(solicitud: SolicitudConsulta, usuario: str = Depends(usuario_autenticado)):
    pregunta = solicitud.pregunta.strip()
    dominios_usuario, cat = _contexto_usuario(usuario)

    motivo = rechazo_previo(pregunta)
    if motivo:
        db.registrar_consulta(usuario, pregunta, "rechazado", motivo)
        return {"estado": "rechazado", "motivo": motivo}

    try:
        plan, uso = interpretar_con_ia(pregunta, cat, dominios_usuario, _describir_panel(solicitud.panel), solicitud.panel.area)
    except ErrorIA as e:
        db.registrar_consulta(usuario, pregunta, "error", str(e))
        raise HTTPException(status_code=502, detail=str(e)) from e

    if plan.accion == "consultar":
        plan = aplicar_filtros_panel(plan, cat, solicitud.panel.filtros, solicitud.panel.desde, solicitud.panel.hasta)
    return _ejecutar_plan(usuario, pregunta, plan, cat, dominios_usuario, uso)


class GraficoExportar(BaseModel):
    titulo: str = Field(min_length=1, max_length=200)
    plan: PlanConsulta


class SolicitudExportacion(BaseModel):
    titulo: str = Field(default="Reporte BI Copilot", min_length=1, max_length=200)
    graficos: list[GraficoExportar] = Field(min_length=1, max_length=30)


def _graficos_a_exportar(solicitud: SolicitudExportacion, usuario: str) -> tuple[catalogo.Catalogo, list[tuple[str, PlanConsulta]]]:
    """Los planes vienen del navegador, así que pasan por la misma validación."""
    dominios_usuario, cat = _contexto_usuario(usuario)
    graficos = []
    for g in solicitud.graficos:
        plan = normalizar_salida(g.plan.model_copy(update={"accion": "consultar"}))
        motivo = validar_plan(plan, cat, dominios_usuario)
        if motivo:
            raise HTTPException(status_code=400, detail=f"No se pudo exportar «{g.titulo}»: {motivo}")
        graficos.append((g.titulo, plan))
    return cat, graficos


ORGANIZACION = os.getenv("ORGANIZACION", "Ruta Smart")
_CORREO = r"^$|^[^@\s]+@[^@\s]+\.[^@\s]+$"


class DatosUsuario(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    correo: str = Field(default="", max_length=254, pattern=_CORREO)
    dominios: list[str] = Field(default_factory=list, max_length=20)
    superadmin: bool = False
    activo: bool = True


class UsuarioNuevo(DatosUsuario):
    usuario: str = Field(pattern=r"^[A-Za-z0-9_]{3,50}$")


def usuario_superadmin(usuario: str = Depends(usuario_autenticado)) -> str:
    """El permiso se consulta en la BD en cada solicitud, no se confía en el navegador."""
    try:
        datos = db.perfil(usuario)
    except pyodbc.Error as e:
        raise _error_bd(e) from e
    if not datos or not datos["superadmin"]:
        raise HTTPException(status_code=403, detail="Solo un superadministrador puede hacer esto.")
    return usuario


def _validar_dominios(dominios: list[str]) -> None:
    desconocidos = set(dominios) - set(db.dominios())
    if desconocidos:
        raise HTTPException(status_code=400, detail=f"Áreas no válidas: {', '.join(sorted(desconocidos))}.")


@app.get("/api/perfil")
def ver_perfil(usuario: str = Depends(usuario_autenticado)):
    dominios_usuario, cat = _contexto_usuario(usuario)
    try:
        datos = db.perfil(usuario)
        pendientes = db.contar_solicitudes_pendientes() if datos and datos["superadmin"] else 0
    except pyodbc.Error as e:
        raise _error_bd(e) from e
    if datos is None:
        raise HTTPException(status_code=403, detail=f"El usuario {usuario} no existe o está inactivo.")
    return {
        **datos,
        "solicitudesPendientes": pendientes,
        "correo": datos["correo"] or "",
        "organizacion": ORGANIZACION,
        "areas": [nombre for cod, nombre in cat.dominios.items() if cod in dominios_usuario],
    }


@app.get("/api/usuarios")
def ver_usuarios(_usuario: str = Depends(usuario_superadmin)):
    try:
        return {
            "usuarios": db.listar_usuarios(),
            "dominios": [{"codigo": cod, "nombre": nombre} for cod, nombre in db.dominios().items()],
        }
    except pyodbc.Error as e:
        raise _error_bd(e) from e


@app.post("/api/usuarios")
def crear_usuario(datos: UsuarioNuevo, usuario: str = Depends(usuario_superadmin)):
    cod = datos.usuario.upper()
    try:
        _validar_dominios(datos.dominios)
        creado = db.guardar_usuario(cod, datos.nombre.strip(), datos.correo or None, datos.activo, datos.superadmin, datos.dominios, crear=True)
    except pyodbc.Error as e:
        raise _error_bd(e) from e
    if not creado:
        raise HTTPException(status_code=409, detail=f"El usuario {cod} ya existe.")
    db.registrar_consulta(usuario, f"[admin] crea usuario {cod}", "validado")
    return {"ok": True}


@app.post("/api/usuarios/{cod_usuario}")
def editar_usuario(cod_usuario: str, datos: DatosUsuario, usuario: str = Depends(usuario_superadmin)):
    # Evita quedar sin nadie que pueda administrar
    if cod_usuario == usuario and (not datos.activo or not datos.superadmin):
        raise HTTPException(status_code=400, detail="No puedes desactivar ni quitarte el rol de superadministrador a ti mismo.")
    try:
        _validar_dominios(datos.dominios)
        guardado = db.guardar_usuario(cod_usuario, datos.nombre.strip(), datos.correo or None, datos.activo, datos.superadmin, datos.dominios, crear=False)
    except pyodbc.Error as e:
        raise _error_bd(e) from e
    if not guardado:
        raise HTTPException(status_code=404, detail="El usuario no existe.")
    db.registrar_consulta(usuario, f"[admin] edita usuario {cod_usuario}", "validado")
    return {"ok": True}


@app.post("/api/usuarios/{cod_usuario}/enlace-clave")
def enviar_enlace_clave(cod_usuario: str, tareas: BackgroundTasks, usuario: str = Depends(usuario_superadmin)):
    try:
        destino = db.usuario_para_recuperar(cod_usuario)
    except pyodbc.Error as e:
        raise _error_bd(e) from e
    if destino is None:
        raise HTTPException(status_code=400, detail="El usuario debe estar activo y tener un correo registrado.")
    tareas.add_task(recuperacion.solicitar, cod_usuario)
    db.registrar_consulta(usuario, f"[admin] envía enlace de clave a {cod_usuario}", "validado")
    return {"ok": True}


# Límites por 24 horas para el formulario público de solicitud de acceso
MAX_SOLICITUDES_CORREO = 2
MAX_SOLICITUDES_IP = 5
MAX_SOLICITUDES_TOTAL = 50


class SolicitudAcceso(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    correo: str = Field(max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    areas: list[str] = Field(default_factory=list, max_length=20)
    motivo: str = Field(default="", max_length=500)
    sitio: str = Field(default="", max_length=200)  # campo oculto: solo lo completan los bots


def _registrar_solicitud(datos: SolicitudAcceso, ip: str) -> None:
    """Corre en segundo plano: el resultado no debe notarse en la respuesta."""
    try:
        validas = db.dominios()
        creada = db.crear_solicitud(
            datos.nombre.strip(), datos.correo.strip().lower(), [a for a in datos.areas if a in validas],
            datos.motivo.strip(), hashlib.sha256(ip.encode("utf-8")).hexdigest(),
            MAX_SOLICITUDES_CORREO, MAX_SOLICITUDES_IP, MAX_SOLICITUDES_TOTAL,
        )
        if not creada:
            print("[solicitud-acceso] descartada: límite diario, duplicada o correo ya registrado", flush=True)
    except pyodbc.Error as e:
        print(f"[solicitud-acceso] no se pudo registrar: {type(e).__name__}", flush=True)


@app.get("/api/areas")
def ver_areas():
    """Nombres de las áreas para el formulario público; no incluye datos."""
    try:
        return [{"codigo": cod, "nombre": nombre} for cod, nombre in db.dominios().items()]
    except pyodbc.Error as e:
        raise _error_bd(e) from e


@app.post("/api/solicitudes-acceso")
def solicitar_acceso(datos: SolicitudAcceso, request: Request, tareas: BackgroundTasks):
    """Responde siempre igual, para no revelar qué correos ya tienen cuenta."""
    if not datos.sitio:
        tareas.add_task(_registrar_solicitud, datos, request.client.host if request.client else "desconocida")
    return {"ok": True}


@app.get("/api/solicitudes-acceso")
def ver_solicitudes(_usuario: str = Depends(usuario_superadmin)):
    try:
        return {"solicitudes": db.listar_solicitudes()}
    except pyodbc.Error as e:
        raise _error_bd(e) from e


@app.post("/api/solicitudes-acceso/{id_solicitud}/aprobar")
def aprobar_solicitud(id_solicitud: int, datos: UsuarioNuevo, tareas: BackgroundTasks, usuario: str = Depends(usuario_superadmin)):
    cod = datos.usuario.upper()
    try:
        _validar_dominios(datos.dominios)
        # Primero se toma la solicitud, así dos aprobaciones simultáneas no crean dos cuentas
        if not db.resolver_solicitud(id_solicitud, "APROBADA", usuario):
            raise HTTPException(status_code=409, detail="Esa solicitud ya fue resuelta.")
        if not db.guardar_usuario(cod, datos.nombre.strip(), datos.correo or None, datos.activo, datos.superadmin, datos.dominios, crear=True):
            db.resolver_solicitud(id_solicitud, "PENDIENTE", None)
            raise HTTPException(status_code=409, detail=f"El usuario {cod} ya existe.")
    except pyodbc.Error as e:
        raise _error_bd(e) from e
    db.registrar_consulta(usuario, f"[admin] aprueba solicitud {id_solicitud}: {cod}", "validado")
    if datos.correo:
        tareas.add_task(recuperacion.solicitar, cod)
    return {"ok": True}


@app.post("/api/solicitudes-acceso/{id_solicitud}/rechazar")
def rechazar_solicitud(id_solicitud: int, usuario: str = Depends(usuario_superadmin)):
    try:
        if not db.resolver_solicitud(id_solicitud, "RECHAZADA", usuario):
            raise HTTPException(status_code=409, detail="Esa solicitud ya fue resuelta.")
    except pyodbc.Error as e:
        raise _error_bd(e) from e
    db.registrar_consulta(usuario, f"[admin] rechaza solicitud {id_solicitud}", "validado")
    return {"ok": True}


@app.get("/api/mapa-chile")
def mapa_chile(_usuario: str = Depends(usuario_autenticado)):
    """Formas de las regiones de Chile, ya proyectadas para dibujarlas en SVG."""
    return Response(content=reporte_html.mapa_chile(), media_type="application/json")


@app.post("/api/reporte-html")
def exportar_html(solicitud: SolicitudExportacion, usuario: str = Depends(usuario_autenticado)):
    """Un solo archivo .html interactivo con los gráficos pedidos en el chat."""
    cat, graficos = _graficos_a_exportar(solicitud, usuario)
    try:
        contenido = reporte_html.generar(solicitud.titulo, cat, graficos)
    except pyodbc.Error as e:
        db.registrar_consulta(usuario, "[html]", "error", str(e))
        raise HTTPException(status_code=500, detail="La consulta falló en la base de datos.") from e
    db.registrar_consulta(usuario, f"[html] {len(graficos)} gráficos del chat", "validado")
    return Response(content=contenido, media_type="text/html; charset=utf-8")


@app.post("/api/powerbi")
def exportar_powerbi(solicitud: SolicitudExportacion, usuario: str = Depends(usuario_autenticado)):
    """Proyecto .pbip (en un .zip) con los gráficos pedidos en el chat."""
    cat, graficos = _graficos_a_exportar(solicitud, usuario)
    contenido = powerbi.generar_zip(cat, graficos, solicitud.titulo)
    db.registrar_consulta(usuario, f"[powerbi] {len(graficos)} gráficos del chat", "validado")
    return Response(
        content=contenido,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="BI_Copilot_PowerBI.zip"'},
    )


@app.post("/api/reportes")
def reejecutar(solicitud: SolicitudReporte, usuario: str = Depends(usuario_autenticado)):
    """Vuelve a ejecutar un plan con otros filtros sin llamar a la IA. El plan viene
    del navegador, así que pasa por la misma validación que uno recién armado."""
    dominios_usuario, cat = _contexto_usuario(usuario)
    plan = solicitud.plan.model_copy(update={"accion": "consultar"})
    return _ejecutar_plan(usuario, f"[filtros] {solicitud.pregunta.strip()}", plan, cat, dominios_usuario, None)
