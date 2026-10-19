"""Paso 1 del flujo: la IA traduce la pregunta a un PLAN de consulta.

La IA nunca escribe SQL. Devuelve un JSON restringido por un schema cuyos
valores posibles salen del catálogo (structured outputs), y luego
consultas.py valida ese plan y arma el SQL parametrizado.
"""

import os
from typing import Literal

import anthropic
from pydantic import BaseModel, ValidationError

from . import catalogo

# Haiku 5.5: el modelo más barato de Claude, suficiente para traducir una
# pregunta a un plan JSON. Se puede cambiar por variable de entorno.
MODELO = os.getenv("CLAUDE_MODEL", "claude-haiku-5-5")


class FiltroPlan(BaseModel):
    campo: str
    valor: str


class PlanConsulta(BaseModel):
    accion: Literal["consultar", "rechazar", "aclarar"]
    motivo_rechazo: str
    dominio: str
    titulo: str
    metrica: str
    agrupar_por: str
    filtros: list[FiltroPlan]
    desde: str
    hasta: str
    tipo_salida: str


class ErrorIA(Exception):
    """La IA no respondió o respondió algo inutilizable."""


def _schema_plan(cat: catalogo.Catalogo, dominios_usuario: set[str]) -> dict:
    """Los enum obligan a la IA a elegir solo métricas, agrupaciones y campos
    de los dominios que el usuario puede consultar. Los valores de los
    filtros se validan después en consultas.py."""
    visibles = [d for cod, d in cat.disponibles.items() if cod in dominios_usuario]
    metricas = list(dict.fromkeys(k for d in visibles for k in d.medidas)) or ["ninguna"]
    dimensiones = list(dict.fromkeys(k for d in visibles for k in d.dimensiones())) or [catalogo.NINGUNO]
    campos = list(dict.fromkeys(k for d in visibles for k in d.atributos)) or ["ninguno"]
    return {
        "type": "object",
        "properties": {
            "accion": {"type": "string", "enum": ["consultar", "rechazar", "aclarar"]},
            "motivo_rechazo": {"type": "string"},
            "dominio": {"type": "string", "enum": list(cat.dominios)},
            "titulo": {"type": "string"},
            "metrica": {"type": "string", "enum": metricas},
            "agrupar_por": {"type": "string", "enum": dimensiones},
            "filtros": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "campo": {"type": "string", "enum": campos},
                        "valor": {"type": "string"},
                    },
                    "required": ["campo", "valor"],
                    "additionalProperties": False,
                },
            },
            "desde": {"type": "string"},
            "hasta": {"type": "string"},
            "tipo_salida": {"type": "string", "enum": catalogo.TIPOS_SALIDA},
        },
        "required": ["accion", "motivo_rechazo", "dominio", "titulo", "metrica", "agrupar_por",
                     "filtros", "desde", "hasta", "tipo_salida"],
        "additionalProperties": False,
    }


def _system_prompt(cat: catalogo.Catalogo, dominios_usuario: set[str]) -> str:
    return f"""Eres el intérprete de consultas de BI Ruta Smart, una herramienta de reportes para una aseguradora.
Tu trabajo es convertir la pregunta del usuario en un plan de consulta en JSON. Otro componente valida el plan y ejecuta la consulta: tú no ves los datos ni escribes SQL.

Catálogo:
{cat.descripcion_para_ia(dominios_usuario)}

Cómo armar el plan:
- En "dominio" indica a qué dominio de negocio pertenece la pregunta (siniestros, reservas o recuperos -> SIN; primas o comisiones -> FIN; pólizas, clientes, cartera o montos asegurados -> SEG), aunque ese dominio no tenga detalle en el catálogo. Otro componente revisa si el usuario tiene acceso.
- Si la pregunta es de un dominio sin detalle en el catálogo, usa "accion": "consultar" igual y completa el resto con cualquier valor válido.
- Usa solo métricas, agrupaciones y campos de filtro del dominio elegido.
- "filtros" lleva solo las restricciones que menciona la pregunta (lista vacía si no hay). "valor" debe ser exactamente uno de los valores listados para ese campo; si el usuario escribe distinto (por ejemplo "autos" o "abiertos"), usa el valor del catálogo equivalente.
- "desde" y "hasta" van en formato AAAA-MM, o "" si la pregunta no menciona un período. Un mes puntual usa el mismo valor en ambos.
- Elige "agrupar_por" según lo que se quiera comparar ("por región" -> region, "por mes" o evolución -> mes); si se pide un único número, "ninguno".
- Elige "tipo_salida" acorde: un número -> kpi; comparación entre categorías -> grafico_barras; evolución en el tiempo -> grafico_lineas; distribución -> grafico_torta; listado -> tabla.
- "titulo" es un título breve en español para el reporte.
- Usa "accion": "rechazar" cuando la pregunta pida modificar o borrar datos, pida campos no autorizados (en especial datos personales de clientes) o no tenga relación con el negocio.
- Usa "accion": "aclarar" cuando la pregunta sea tan vaga que no se pueda saber qué medir (por ejemplo un saludo). En "motivo_rechazo" pregunta qué quiere medir, con qué filtros y cómo quiere verlo (barras, líneas, torta, KPI o tabla).
- Si la pregunta indica qué medir pero no cómo verlo, no pidas aclaración: elige tú la visualización más adecuada.
- En "rechazar" y "aclarar" escribe "motivo_rechazo" en español, dirigido al usuario, y completa el resto de campos con cualquier valor válido. Si la acción es "consultar", deja "motivo_rechazo" vacío."""


def _mensaje_usuario(pregunta: str, filtros_panel: str) -> str:
    if not filtros_panel:
        return pregunta
    return (f"{pregunta}\n\n(Filtros ya seleccionados en el panel del dashboard, que se aplican "
            f"automáticamente: {filtros_panel}. No pidas aclaración por ellos.)")


_cliente: anthropic.Anthropic | None = None


def _cliente_anthropic() -> anthropic.Anthropic:
    global _cliente
    if _cliente is None:
        _cliente = anthropic.Anthropic()  # lee ANTHROPIC_API_KEY del entorno
    return _cliente


def interpretar_con_ia(pregunta: str, cat: catalogo.Catalogo, dominios_usuario: set[str],
                      filtros_panel: str = "") -> tuple[PlanConsulta, dict]:
    """Devuelve el plan y los tokens usados (para medir el costo real).
    `filtros_panel` describe los filtros ya elegidos en el dashboard: se informan
    a la IA como contexto, pero el backend los aplica igual por su cuenta."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise ErrorIA("Falta ANTHROPIC_API_KEY en backend/.env.")
    try:
        respuesta = _cliente_anthropic().messages.create(
            model=MODELO,
            max_tokens=4000,  # el plan ocupa ~150 tokens; el resto es margen para el razonamiento
            system=_system_prompt(cat, dominios_usuario),
            messages=[{"role": "user", "content": _mensaje_usuario(pregunta, filtros_panel)}],
            output_config={
                "effort": "low",  # tarea simple: menos razonamiento = más rápido y barato
                "format": {"type": "json_schema", "schema": _schema_plan(cat, dominios_usuario)},
            },
        )
    except anthropic.AuthenticationError as e:
        raise ErrorIA("La API key de Anthropic no es válida o no está configurada.") from e
    except anthropic.RateLimitError as e:
        raise ErrorIA("Se alcanzó el límite de uso de la IA. Intenta en unos segundos.") from e
    except anthropic.APIStatusError as e:
        raise ErrorIA(f"La IA respondió con error {e.status_code}.") from e
    except anthropic.APIConnectionError as e:
        raise ErrorIA("No se pudo conectar con la IA.") from e

    uso = {"entrada": respuesta.usage.input_tokens, "salida": respuesta.usage.output_tokens}

    # Haiku no tiene respaldo automático: si sus filtros de seguridad rechazan
    # la pregunta, se responde como solicitud rechazada.
    if respuesta.stop_reason == "refusal":
        return PlanConsulta(
            accion="rechazar",
            motivo_rechazo="La solicitud fue rechazada por las políticas de seguridad del modelo.",
            dominio="", titulo="", metrica="", agrupar_por=catalogo.NINGUNO,
            filtros=[], desde="", hasta="", tipo_salida="kpi",
        ), uso
    if respuesta.stop_reason == "max_tokens":
        raise ErrorIA("La respuesta de la IA quedó incompleta.")

    texto = next((b.text for b in respuesta.content if b.type == "text"), "")
    try:
        return PlanConsulta.model_validate_json(texto), uso
    except ValidationError as e:
        raise ErrorIA("La IA devolvió un plan con formato inválido.") from e
