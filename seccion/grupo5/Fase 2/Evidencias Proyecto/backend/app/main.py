"""API de BI Copilot.

Flujo de POST /api/consultas:
  usuario + pregunta + filtros del panel -> permisos del usuario (seguridad.*)
  -> reglas previas -> catálogo (meta.*) -> IA arma plan -> se suman los filtros
  del panel -> validar plan y dominio -> SQL parametrizado
  -> BD como bi_lector (solo lectura) -> resultado + traza en seguridad.SEG_LOG_CONSULTA

POST /api/reportes vuelve a ejecutar un plan ya armado con otros filtros, sin
llamar a la IA (cambiar un filtro en el panel no gasta tokens).
"""

import os
import secrets

from dotenv import load_dotenv

load_dotenv()  # lee backend/.env antes de crear el cliente de Anthropic

import pyodbc  # noqa: E402
from fastapi import Depends, FastAPI, Header, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from . import catalogo, claves, db, sesion  # noqa: E402
from .consultas import aplicar_filtros_panel, construir_sql, rechazo_previo, validar_plan  # noqa: E402
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
    return dominios_usuario, cat


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


@app.get("/api/catalogo")
def ver_catalogo(usuario: str = Depends(usuario_autenticado)):
    """Filtros disponibles para el panel: solo los dominios que el usuario puede consultar,
    con los valores reales de la BD."""
    dominios_usuario, cat = _contexto_usuario(usuario)
    return {
        "dominios": [
            {
                "codigo": cod,
                "nombre": cat.dominios[cod],
                "filtros": [
                    {"campo": campo, "etiqueta": a.etiqueta, "valores": d.valores[campo]}
                    for campo, a in d.atributos.items()
                ],
                "fecha": {"etiqueta": d.definicion.fecha.etiqueta, "desde": d.rango_meses[0], "hasta": d.rango_meses[1]}
                if d.rango_meses else None,
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
        plan, uso = interpretar_con_ia(pregunta, cat, dominios_usuario, _describir_panel(solicitud.panel))
    except ErrorIA as e:
        db.registrar_consulta(usuario, pregunta, "error", str(e))
        raise HTTPException(status_code=502, detail=str(e)) from e

    if plan.accion == "consultar":
        plan = aplicar_filtros_panel(plan, cat, solicitud.panel.filtros, solicitud.panel.desde, solicitud.panel.hasta)
    return _ejecutar_plan(usuario, pregunta, plan, cat, dominios_usuario, uso)


@app.post("/api/reportes")
def reejecutar(solicitud: SolicitudReporte, usuario: str = Depends(usuario_autenticado)):
    """Vuelve a ejecutar un plan con otros filtros sin llamar a la IA. El plan viene
    del navegador, así que pasa por la misma validación que uno recién armado."""
    dominios_usuario, cat = _contexto_usuario(usuario)
    plan = solicitud.plan.model_copy(update={"accion": "consultar"})
    return _ejecutar_plan(usuario, f"[filtros] {solicitud.pregunta.strip()}", plan, cat, dominios_usuario, None)
