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
from typing import Literal

from dotenv import load_dotenv

load_dotenv()  # lee backend/.env antes de crear el cliente de Anthropic

import pyodbc  # noqa: E402
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request, Response  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field, ValidationError  # noqa: E402

from . import analisis, catalogo, claves, db, powerbi, recuperacion, reporte_html, sesion  # noqa: E402
from .consultas import (  # noqa: E402
    FORMATO_MES, aplicar_filtros_panel, construir_sql, normalizar_salida, rechazo_previo, validar_plan,
)
from .ia import ErrorIA, PlanConsulta, interpretar_con_ia  # noqa: E402

app = FastAPI(title="BI Copilot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["X-Graficos-Omitidos"],  # el navegador solo deja leer los encabezados listados
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
        "comparar": plan.comparar,
        "comparable": medida.comparable,
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

    dominio = cat.disponibles[plan.dominio]
    # El plan que se devuelve es el pedido. Al comparar sin período, el backend elige los
    # últimos 12 meses solo para esta ejecución: si esas fechas volvieran en el plan, un
    # dashboard guardado quedaría fijo en ellas en vez de mostrar siempre lo último.
    plan_pedido = plan.model_dump()
    # Si la comparación no tiene sentido para esta métrica, no se calcula: se explica por qué
    plan, plan_anterior, comparacion = analisis.preparar_comparacion(plan, dominio)
    plan_dict = plan.model_dump()

    consultas = construir_sql(plan, cat)
    if plan_anterior:
        consultas |= {f"anterior_{nombre}": consulta for nombre, consulta in construir_sql(plan_anterior, cat).items()
                      if nombre != "detalle"}
    sql_log = "\n".join(f"-- {nombre}\n{sql}" for nombre, (sql, _) in consultas.items())
    try:
        datos = {nombre: db.ejecutar(sql, params) for nombre, (sql, params) in consultas.items()}
    except pyodbc.Error as e:
        db.registrar_consulta(usuario, pregunta, "error", str(e), plan_dict, sql_log, uso, plan.dominio)
        if db.es_tiempo_agotado(e):
            raise _error_bd(e) from e
        raise HTTPException(status_code=500, detail="La consulta falló en la base de datos.") from e
    db.registrar_consulta(usuario, pregunta, "validado", plan=plan_dict, sql=sql_log, uso=uso, dominio=plan.dominio)

    total = datos["total"]["filas"][0]
    serie = analisis.completar_meses(datos["serie"]["filas"] if "serie" in datos else [], plan, dominio)
    resultado = {
        "total": total["valor"] or 0,
        "cantidad": total["cantidad"],
        "serie": serie,
        "detalle": {
            **datos.get("detalle", {"columnas": [], "filas": []}),
            "columnasMoneda": [a.etiqueta for a in dominio.detalle if a.moneda],
        },
    }
    if comparacion is not None:
        if plan_anterior:
            analisis.completar_comparacion(
                comparacion, total["valor"], datos["anterior_total"]["filas"][0]["valor"], serie,
                datos["anterior_serie"]["filas"] if "anterior_serie" in datos else [], plan.agrupar_por,
            )
        resultado["comparacion"] = comparacion
    proyeccion = analisis.proyectar(serie, plan, dominio)
    if proyeccion is not None:
        resultado["proyeccion"] = proyeccion

    return {
        "estado": "validado",
        "plan": plan_pedido,  # el frontend lo reenvía a /api/reportes al cambiar filtros
        "interpretacion": _interpretacion(plan, cat),
        "resultado": resultado,
    }


def _error_bd(e: Exception) -> HTTPException:
    if db.es_tiempo_agotado(e):
        return HTTPException(status_code=503, detail="La base de datos tardó demasiado en responder. "
                                                     "Puede estar sin memoria: intenta de nuevo en un momento.")
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
                "metricas": [
                    {"clave": clave, "etiqueta": m.etiqueta, "comparable": m.comparable, "nota": m.nota,
                     "proyectable": catalogo.proyectable(d, clave)}
                    for clave, m in d.medidas.items()
                ],
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
                # Dashboard completo del área (POST /api/paquetes) y el mes que propone por defecto
                "dashboard": {
                    "nombre": catalogo.PAQUETES[cod].nombre,
                    "paraQue": catalogo.PAQUETES[cod].para_que,
                    "graficos": [{"titulo": g.titulo, "lectura": g.lectura} for g in catalogo.graficos_paquete(d, cod)],
                    "mes": d.mes_recomendado(analisis.ultimo_mes_completo(d.rango_meses)),
                } if cod in catalogo.PAQUETES and d.rango_meses and catalogo.graficos_paquete(d, cod) else None,
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

    if plan.accion == "dashboard":
        return _armar_paquete(usuario, pregunta, plan.dominio, plan.desde or solicitud.panel.desde,
                              plan.hasta or solicitud.panel.hasta, plan.filtros, cat, dominios_usuario, uso)
    if plan.accion == "consultar":
        plan = aplicar_filtros_panel(plan, cat, solicitud.panel.filtros, solicitud.panel.desde, solicitud.panel.hasta)
    return _ejecutar_plan(usuario, pregunta, plan, cat, dominios_usuario, uso)


def _armar_paquete(usuario: str, pregunta: str, cod: str, desde: str, hasta: str, filtros: list,
                   cat: catalogo.Catalogo, dominios_usuario: set[str], uso: dict | None) -> dict:
    """Dashboard completo de un área para un período (catalogo.PAQUETES): cifras clave
    contra el período anterior, tendencia de 12 meses y reparto por región, producto y
    tipo. Cada gráfico pasa por la misma validación y traza que uno pedido en el chat."""
    nombre = cat.dominios.get(cod, cod)
    if cod not in dominios_usuario:
        motivo = f"Acceso no autorizado al dominio {cod} ({nombre})."
        db.registrar_consulta(usuario, pregunta, "rechazado", motivo, uso=uso, dominio=cod or None)
        return {"estado": "rechazado", "motivo": motivo}
    dominio = cat.disponibles.get(cod)
    graficos = catalogo.graficos_paquete(dominio, cod) if dominio else []
    if not graficos or not dominio.rango_meses:
        return {"estado": "aclaracion", "motivo": f"Aún no hay un dashboard completo para {nombre}. Pídeme gráficos "
                                                  "sueltos, por ejemplo uno de las recomendaciones de abajo."}
    for valor in (desde, hasta):
        if valor and not FORMATO_MES.match(valor):
            return {"estado": "aclaracion", "motivo": f"No entendí el período «{valor}». Dime el mes, por ejemplo «abril 2026»."}

    # Sin período: el último mes terminado con un volumen normal de registros
    primero, ultimo = dominio.rango_meses
    ultimo_completo = dominio.mes_recomendado(analisis.ultimo_mes_completo(dominio.rango_meses))
    hasta = hasta or desde or ultimo_completo
    desde = desde or hasta
    if desde > hasta:
        desde, hasta = hasta, desde
    if hasta < primero or desde > ultimo:
        return {"estado": "aclaracion",
                "motivo": f"No hay datos de {nombre.lower()} entre {desde} y {hasta}: hay datos entre {primero} y {ultimo}. "
                          f"Pídeme, por ejemplo, el dashboard de {nombre.lower()} de {ultimo_completo}."}

    # Filtros mencionados (por ejemplo «en Valparaíso»): solo los que existen en el área
    validos = [f for f in filtros if f.campo in dominio.atributos and f.valor in dominio.valores.get(f.campo, [])]
    paquete = catalogo.PAQUETES[cod]
    periodo = desde if desde == hasta else f"{desde} a {hasta}"
    salida = []
    for g in graficos:
        plan = PlanConsulta(
            accion="consultar", motivo_rechazo="", dominio=cod, titulo=g.titulo, metrica=g.metrica,
            agrupar_por=g.agrupar_por, filtros=validos,
            desde=analisis.sumar_meses(hasta, -11) if g.tendencia else desde, hasta=hasta,
            tipo_salida=g.tipo, comparar=g.comparar,
        )
        try:
            r = _ejecutar_plan(usuario, f"{pregunta} · {g.titulo}", plan, cat, dominios_usuario, None if salida else uso)
        except HTTPException as e:
            if e.status_code == 503:
                raise  # la base no responde: no tiene sentido esperar por los demás gráficos
            continue  # un gráfico que falla no bota el resto del dashboard
        if r["estado"] == "validado":
            salida.append({"titulo": g.titulo, "lectura": g.lectura, "plan": r["plan"],
                           "interpretacion": r["interpretacion"], "resultado": r["resultado"]})
    if not salida:
        raise HTTPException(status_code=500, detail="No se pudo armar ningún gráfico del dashboard.")
    filtro_texto = f" · {', '.join(f.valor for f in validos)}" if validos else ""
    return {
        "estado": "dashboard",
        "dominio": cod,
        "titulo": f"{paquete.nombre} · {periodo}{filtro_texto}",
        "explicacion": paquete.para_que,
        "periodo": periodo,
        "graficos": salida,
    }


class SolicitudPaquete(BaseModel):
    dominio: str = Field(min_length=1, max_length=10)
    mes: str = Field(default="", max_length=7)  # AAAA-MM; vacío = último mes completo con datos


@app.post("/api/paquetes")
def armar_dashboard_recomendado(solicitud: SolicitudPaquete, usuario: str = Depends(usuario_autenticado)):
    """Dashboard recomendado de un área, elegido desde la pantalla (sin pasar por la IA)."""
    dominios_usuario, cat = _contexto_usuario(usuario)
    return _armar_paquete(usuario, f"[dashboard recomendado] {solicitud.dominio} {solicitud.mes}".strip(),
                          solicitud.dominio, solicitud.mes, solicitud.mes, [], cat, dominios_usuario, None)


class GraficoExportar(BaseModel):
    titulo: str = Field(min_length=1, max_length=200)
    plan: PlanConsulta


class SolicitudExportacion(BaseModel):
    titulo: str = Field(default="Reporte BI Copilot", min_length=1, max_length=200)
    graficos: list[GraficoExportar] = Field(min_length=1, max_length=30)


def _validar_graficos(graficos: list[GraficoExportar], usuario: str, verbo: str,
                      permitidos: set[str] = frozenset()) -> tuple[catalogo.Catalogo, list[tuple[str, PlanConsulta]]]:
    """Los planes vienen del navegador, así que pasan por la misma validación.
    `permitidos` = planes (en JSON) ya guardados que se aceptan sin revalidar: un editor
    puede reordenar o quitar gráficos de áreas que él no ve, pero no crearlos."""
    dominios_usuario, cat = _contexto_usuario(usuario)
    validos = []
    for g in graficos:
        plan = normalizar_salida(g.plan.model_copy(update={"accion": "consultar"}))
        if plan.model_dump_json() not in permitidos:
            motivo = validar_plan(plan, cat, dominios_usuario)
            if motivo:
                raise HTTPException(status_code=400, detail=f"No se pudo {verbo} «{g.titulo}»: {motivo}")
        validos.append((g.titulo, plan))
    return cat, validos


def _graficos_a_exportar(solicitud: SolicitudExportacion, usuario: str) -> tuple[catalogo.Catalogo, list[tuple[str, PlanConsulta]], int]:
    """Como al guardar un dashboard: un gráfico viejo que ya no calza con el catálogo se
    deja fuera (el encabezado X-Graficos-Omitidos dice cuántos) en vez de no exportar nada."""
    dominios_usuario, cat = _contexto_usuario(usuario)
    validos, motivos = [], []
    for g in solicitud.graficos:
        plan = normalizar_salida(g.plan.model_copy(update={"accion": "consultar"}))
        motivo = validar_plan(plan, cat, dominios_usuario)
        if motivo:
            motivos.append(f"«{g.titulo}»: {motivo}")
        else:
            validos.append((g.titulo, plan))
    if not validos:
        raise HTTPException(status_code=400, detail=f"Ningún gráfico se puede exportar. {motivos[0]}")
    return cat, validos, len(motivos)


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
    # SQL Server no distingue mayúsculas: "usr_admin" en la URL es el mismo USR_ADMIN
    cod_usuario = cod_usuario.strip().upper()
    # Evita quedar sin nadie que pueda administrar
    if cod_usuario == usuario.upper() and (not datos.activo or not datos.superadmin):
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
    except pyodbc.Error as e:
        raise _error_bd(e) from e
    try:
        creado = db.guardar_usuario(cod, datos.nombre.strip(), datos.correo or None, datos.activo, datos.superadmin, datos.dominios, crear=True)
    except pyodbc.Error as e:
        creado = None
        error = e
    if not creado:
        # La solicitud vuelve a quedar pendiente: no puede quedar aprobada sin cuenta creada
        try:
            db.resolver_solicitud(id_solicitud, "PENDIENTE", None)
        except pyodbc.Error:
            pass
        if creado is None:
            raise _error_bd(error) from error
        raise HTTPException(status_code=409, detail=f"El usuario {cod} ya existe.")
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
    cat, graficos, omitidos = _graficos_a_exportar(solicitud, usuario)
    try:
        contenido = reporte_html.generar(solicitud.titulo, cat, graficos)
    except pyodbc.Error as e:
        db.registrar_consulta(usuario, "[html]", "error", str(e))
        raise HTTPException(status_code=500, detail="La consulta falló en la base de datos.") from e
    db.registrar_consulta(usuario, f"[html] {len(graficos)} gráficos del chat", "validado")
    return Response(content=contenido, media_type="text/html; charset=utf-8",
                    headers={"X-Graficos-Omitidos": str(omitidos)})


@app.post("/api/powerbi")
def exportar_powerbi(solicitud: SolicitudExportacion, usuario: str = Depends(usuario_autenticado)):
    """Proyecto .pbip (en un .zip) con los gráficos pedidos en el chat."""
    cat, graficos, omitidos = _graficos_a_exportar(solicitud, usuario)
    contenido = powerbi.generar_zip(cat, graficos, solicitud.titulo)
    db.registrar_consulta(usuario, f"[powerbi] {len(graficos)} gráficos del chat", "validado")
    return Response(
        content=contenido,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="BI_Copilot_PowerBI.zip"',
                 "X-Graficos-Omitidos": str(omitidos)},
    )


@app.post("/api/reportes")
def reejecutar(solicitud: SolicitudReporte, usuario: str = Depends(usuario_autenticado)):
    """Vuelve a ejecutar un plan con otros filtros sin llamar a la IA. El plan viene
    del navegador, así que pasa por la misma validación que uno recién armado."""
    dominios_usuario, cat = _contexto_usuario(usuario)
    plan = solicitud.plan.model_copy(update={"accion": "consultar"})
    return _ejecutar_plan(usuario, f"[filtros] {solicitud.pregunta.strip()}", plan, cat, dominios_usuario, None)


# --- Carpetas y dashboards compartidos --------------------------------------------
# Una carpeta es un repositorio compartido. Roles: PROPIETARIO (todo, incluido
# compartir), EDITOR (crea, edita y borra dashboards) y LECTOR (solo los ve).
# Ver db/sqlserver/25_CREATE_DASHBOARDS.sql.

EDITAN = (db.PROPIETARIO, "EDITOR")


class DatosCarpeta(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    descripcion: str = Field(default="", max_length=500)


class MiembroCarpeta(BaseModel):
    usuario: str = Field(min_length=1, max_length=50)
    rol: Literal["LECTOR", "EDITOR", ""]  # "" quita al miembro


class DatosDashboard(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    descripcion: str = Field(default="", max_length=500)
    graficos: list[GraficoExportar] = Field(min_length=1, max_length=30)


class DashboardNuevo(DatosDashboard):
    carpeta: int


class DashboardEditado(DatosDashboard):
    version: int


class PermisoDashboard(BaseModel):
    usuario: str = Field(min_length=1, max_length=50)
    rol: Literal["LECTOR", "EDITOR", ""]  # "" = el mismo rol que tiene en la carpeta


def usuario_activo(usuario: str = Depends(usuario_autenticado)) -> str:
    """El token dura 8 horas: si en ese tiempo desactivan la cuenta, deja de servir aquí."""
    try:
        datos = db.perfil(usuario)
    except pyodbc.Error as e:
        raise _error_bd(e) from e
    if datos is None:
        raise HTTPException(status_code=403, detail=f"El usuario {usuario} no existe o está inactivo.")
    return usuario


def _rol(usuario: str, id_carpeta: int, permitidos: tuple[str, ...], accion: str) -> str:
    """Rol del usuario en la carpeta; 404 si no la ve, 403 si su rol no alcanza."""
    try:
        rol = db.rol_en_carpeta(usuario, id_carpeta)
    except pyodbc.Error as e:
        raise _error_bd(e) from e
    if rol is None:
        raise HTTPException(status_code=404, detail="La carpeta no existe o no tienes acceso a ella.")
    if rol not in permitidos:
        raise HTTPException(status_code=403, detail=f"Tu rol en esta carpeta ({rol.lower()}) no permite {accion}.")
    return rol


def _dashboard_y_rol(usuario: str, id_dashboard: int, permitidos: tuple[str, ...], accion: str) -> tuple[dict, str]:
    """Dashboard y rol efectivo del usuario en él (con la excepción por dashboard, si la hay)."""
    try:
        datos = db.dashboard(id_dashboard)
        rol = db.rol_en_dashboard(usuario, id_dashboard) if datos else None
    except pyodbc.Error as e:
        raise _error_bd(e) from e
    if datos is None or rol is None:
        raise HTTPException(status_code=404, detail="El dashboard no existe o no tienes acceso a él.")
    if rol not in permitidos:
        raise HTTPException(status_code=403, detail=f"Tu rol en este dashboard ({rol.lower()}) no permite {accion}.")
    return datos, rol


@app.get("/api/usuarios-directorio")
def ver_directorio(_usuario: str = Depends(usuario_activo)):
    """Personas con quienes se puede compartir una carpeta (solo código y nombre)."""
    try:
        return {"usuarios": db.directorio()}
    except pyodbc.Error as e:
        raise _error_bd(e) from e


@app.get("/api/carpetas")
def ver_carpetas(usuario: str = Depends(usuario_activo)):
    try:
        return {"carpetas": db.carpetas(usuario)}
    except pyodbc.Error as e:
        raise _error_bd(e) from e


@app.post("/api/carpetas")
def crear_carpeta(datos: DatosCarpeta, usuario: str = Depends(usuario_autenticado)):
    if not datos.nombre.strip():
        raise HTTPException(status_code=400, detail="Escribe un nombre para la carpeta.")
    try:
        id_carpeta = db.crear_carpeta(usuario, datos.nombre.strip(), datos.descripcion.strip())
    except pyodbc.Error as e:
        raise _error_bd(e) from e
    if id_carpeta is None:
        raise HTTPException(status_code=403, detail=f"El usuario {usuario} no existe o está inactivo.")
    db.registrar_consulta(usuario, f"[carpeta] crea {id_carpeta}: {datos.nombre}", "validado")
    return {"id": id_carpeta}


@app.post("/api/carpetas/{id_carpeta}")
def editar_carpeta(id_carpeta: int, datos: DatosCarpeta, usuario: str = Depends(usuario_autenticado)):
    _rol(usuario, id_carpeta, (db.PROPIETARIO,), "editar la carpeta")
    if not datos.nombre.strip():
        raise HTTPException(status_code=400, detail="Escribe un nombre para la carpeta.")
    try:
        db.editar_carpeta(id_carpeta, datos.nombre.strip(), datos.descripcion.strip())
    except pyodbc.Error as e:
        raise _error_bd(e) from e
    return {"ok": True}


@app.post("/api/carpetas/{id_carpeta}/eliminar")
def eliminar_carpeta(id_carpeta: int, usuario: str = Depends(usuario_autenticado)):
    _rol(usuario, id_carpeta, (db.PROPIETARIO,), "eliminar la carpeta")
    try:
        db.eliminar_carpeta(id_carpeta)
    except pyodbc.Error as e:
        raise _error_bd(e) from e
    db.registrar_consulta(usuario, f"[carpeta] elimina {id_carpeta}", "validado")
    return {"ok": True}


@app.get("/api/carpetas/{id_carpeta}/miembros")
def ver_miembros(id_carpeta: int, usuario: str = Depends(usuario_autenticado)):
    _rol(usuario, id_carpeta, (db.PROPIETARIO, *db.ROLES_MIEMBRO), "ver los miembros")
    try:
        return {"miembros": db.miembros(id_carpeta)}
    except pyodbc.Error as e:
        raise _error_bd(e) from e


@app.post("/api/carpetas/{id_carpeta}/miembros")
def guardar_miembro(id_carpeta: int, datos: MiembroCarpeta, usuario: str = Depends(usuario_autenticado)):
    _rol(usuario, id_carpeta, (db.PROPIETARIO,), "compartir la carpeta")
    cod = datos.usuario.strip().upper()
    try:
        guardado = db.guardar_miembro(id_carpeta, cod, datos.rol or None)
    except pyodbc.Error as e:
        raise _error_bd(e) from e
    if not guardado:
        raise HTTPException(status_code=400, detail=f"No se puede compartir con {cod}: no existe, está inactivo o es el propietario.")
    accion = f"da rol {datos.rol} a" if datos.rol else "quita a"
    db.registrar_consulta(usuario, f"[carpeta {id_carpeta}] {accion} {cod}", "validado")
    return {"ok": True}


@app.post("/api/dashboards")
def crear_dashboard(datos: DashboardNuevo, usuario: str = Depends(usuario_autenticado)):
    _rol(usuario, datos.carpeta, EDITAN, "guardar dashboards en ella")
    if not datos.nombre.strip():
        raise HTTPException(status_code=400, detail="Escribe un nombre para el dashboard.")
    # Un gráfico viejo del chat puede usar algo que ya no está en el catálogo: se guardan
    # los demás y se avisa cuáles quedaron fuera, en vez de no guardar nada
    dominios_usuario, cat = _contexto_usuario(usuario)
    graficos, omitidos = [], []
    for g in datos.graficos:
        plan = normalizar_salida(g.plan.model_copy(update={"accion": "consultar"}))
        motivo = validar_plan(plan, cat, dominios_usuario)
        if motivo:
            omitidos.append({"titulo": g.titulo, "motivo": motivo})
        else:
            graficos.append((g.titulo, plan))
    if not graficos:
        raise HTTPException(status_code=400, detail=f"Ningún gráfico se puede guardar. «{omitidos[0]['titulo']}»: {omitidos[0]['motivo']}")
    try:
        id_dashboard = db.crear_dashboard(usuario, datos.carpeta, datos.nombre.strip(), datos.descripcion.strip(),
                                          [(titulo, plan.model_dump_json()) for titulo, plan in graficos])
    except pyodbc.Error as e:
        raise _error_bd(e) from e
    db.registrar_consulta(usuario, f"[dashboard] crea {id_dashboard} en carpeta {datos.carpeta}", "validado")
    return {"id": id_dashboard, "omitidos": omitidos}


@app.get("/api/dashboards/{id_dashboard}")
def abrir_dashboard(id_dashboard: int, usuario: str = Depends(usuario_autenticado)):
    """Vuelve a ejecutar cada gráfico guardado con los permisos de quien lo abre: los
    datos están al día y compartir un dashboard no da acceso a otras áreas."""
    datos, rol = _dashboard_y_rol(usuario, id_dashboard, (db.PROPIETARIO, *db.ROLES_MIEMBRO), "verlo")
    dominios_usuario, cat = _contexto_usuario(usuario)
    graficos = []
    for numero, guardado in enumerate(datos.pop("graficos")):
        base = {"id": f"g{numero}", "pregunta": guardado["titulo"]}
        try:
            plan = PlanConsulta.model_validate_json(guardado["plan"])
        except ValidationError:
            graficos.append({**base, "error": "Este gráfico ya no es compatible con el catálogo actual."})
            continue
        base["plan"] = plan.model_dump()
        if plan.dominio not in dominios_usuario:
            graficos.append({**base, "sinAcceso": cat.dominios.get(plan.dominio, plan.dominio)})
            continue
        try:
            r = _ejecutar_plan(usuario, f"[dashboard {id_dashboard}] {guardado['titulo']}",
                               plan.model_copy(update={"accion": "consultar"}), cat, dominios_usuario, None)
        except HTTPException as e:
            graficos.append({**base, "error": e.detail})
            continue
        if r["estado"] != "validado":
            graficos.append({**base, "error": r["motivo"]})
            continue
        graficos.append({**base, "plan": r["plan"], "interpretacion": r["interpretacion"], "resultado": r["resultado"]})
    return {**datos, "rol": rol, "graficos": graficos}


@app.post("/api/dashboards/{id_dashboard}")
def editar_dashboard(id_dashboard: int, datos: DashboardEditado, usuario: str = Depends(usuario_autenticado)):
    guardado, _ = _dashboard_y_rol(usuario, id_dashboard, EDITAN, "editarlo")
    if not datos.nombre.strip():
        raise HTTPException(status_code=400, detail="Escribe un nombre para el dashboard.")
    # Los gráficos que ya estaban se aceptan aunque sean de un área que este editor no ve
    previos = set()
    for g in guardado["graficos"]:
        try:
            previos.add(normalizar_salida(PlanConsulta.model_validate_json(g["plan"])
                                          .model_copy(update={"accion": "consultar"})).model_dump_json())
        except ValidationError:
            pass
    _, graficos = _validar_graficos(datos.graficos, usuario, "guardar", previos)
    try:
        ok = db.actualizar_dashboard(id_dashboard, usuario, datos.nombre.strip(), datos.descripcion.strip(),
                                     [(titulo, plan.model_dump_json()) for titulo, plan in graficos], datos.version)
    except pyodbc.Error as e:
        raise _error_bd(e) from e
    if not ok:
        raise HTTPException(status_code=409, detail="Otra persona guardó cambios en este dashboard. Vuelve a abrirlo para verlos.")
    db.registrar_consulta(usuario, f"[dashboard] edita {id_dashboard}", "validado")
    return {"ok": True, "version": datos.version + 1}


@app.post("/api/dashboards/{id_dashboard}/eliminar")
def eliminar_dashboard(id_dashboard: int, usuario: str = Depends(usuario_autenticado)):
    _dashboard_y_rol(usuario, id_dashboard, EDITAN, "eliminarlo")
    try:
        db.eliminar_dashboard(id_dashboard)
    except pyodbc.Error as e:
        raise _error_bd(e) from e
    db.registrar_consulta(usuario, f"[dashboard] elimina {id_dashboard}", "validado")
    return {"ok": True}


# Permiso por dashboard: el propietario de la carpeta puede dar a un miembro un rol
# distinto en un dashboard puntual (ver db/sqlserver/26_DASHBOARD_PERMISO.sql).

@app.get("/api/dashboards/{id_dashboard}/permisos")
def ver_permisos_dashboard(id_dashboard: int, usuario: str = Depends(usuario_autenticado)):
    _dashboard_y_rol(usuario, id_dashboard, (db.PROPIETARIO,), "ver sus permisos")
    try:
        return {"miembros": db.permisos_dashboard(id_dashboard)}
    except pyodbc.Error as e:
        raise _error_bd(e) from e


@app.post("/api/dashboards/{id_dashboard}/permisos")
def guardar_permiso_dashboard(id_dashboard: int, datos: PermisoDashboard, usuario: str = Depends(usuario_autenticado)):
    _dashboard_y_rol(usuario, id_dashboard, (db.PROPIETARIO,), "cambiar sus permisos")
    cod = datos.usuario.strip().upper()
    try:
        guardado = db.guardar_permiso_dashboard(id_dashboard, cod, datos.rol or None)
    except pyodbc.Error as e:
        raise _error_bd(e) from e
    if not guardado:
        raise HTTPException(status_code=400, detail=f"{cod} no es miembro de la carpeta: agrégalo primero desde «Compartir».")
    accion = f"da rol {datos.rol} a" if datos.rol else "devuelve el rol de la carpeta a"
    db.registrar_consulta(usuario, f"[dashboard {id_dashboard}] {accion} {cod}", "validado")
    return {"ok": True}


# --- Proyecciones -----------------------------------------------------------------
# Módulo del menú lateral: suavizamiento exponencial (Holt) sobre la serie mensual completa de una
# métrica, calculada con los datos reales (analisis.proyectar).

class SolicitudProyeccion(BaseModel):
    dominio: str = Field(min_length=1, max_length=10)
    metrica: str = Field(min_length=1, max_length=50)


@app.get("/api/proyecciones")
def ver_proyecciones(usuario: str = Depends(usuario_autenticado)):
    """Series que el usuario puede proyectar: primero las recomendadas, con su para qué."""
    dominios_usuario, cat = _contexto_usuario(usuario)
    series = []
    for cod, d in cat.disponibles.items():
        if cod not in dominios_usuario:
            continue
        recomendadas = catalogo.PROYECCIONES.get(cod, {})
        claves = [k for k in recomendadas if k in d.medidas] + [k for k in d.medidas if k not in recomendadas]
        series += [
            {"dominio": cod, "area": cat.dominios[cod], "metrica": k, "etiqueta": d.medidas[k].etiqueta,
             "moneda": d.medidas[k].moneda, "motivo": recomendadas.get(k, ""), "recomendada": k in recomendadas}
            for k in claves if catalogo.proyectable(d, k)
        ]
    return {"series": series}


@app.post("/api/proyecciones")
def calcular_proyeccion(solicitud: SolicitudProyeccion, usuario: str = Depends(usuario_autenticado)):
    """El plan lo arma el backend (toda la historia, por mes): no se acepta uno del navegador."""
    dominios_usuario, cat = _contexto_usuario(usuario)
    dominio = cat.disponibles.get(solicitud.dominio)
    if solicitud.dominio not in dominios_usuario or dominio is None:
        raise HTTPException(status_code=403, detail="No tienes acceso a esa área.")
    if not catalogo.proyectable(dominio, solicitud.metrica):
        raise HTTPException(status_code=400, detail="Esa métrica no se puede proyectar.")
    etiqueta = dominio.medidas[solicitud.metrica].etiqueta
    plan = PlanConsulta(
        accion="consultar", motivo_rechazo="", dominio=solicitud.dominio, titulo=f"Proyección: {etiqueta}",
        metrica=solicitud.metrica, agrupar_por=catalogo.MES, filtros=[], desde="", hasta="",
        tipo_salida="grafico_lineas",
    )
    return _ejecutar_plan(usuario, f"[proyección] {etiqueta}", plan, cat, dominios_usuario, None)
