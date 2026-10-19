"""Pasos 2 y 3 del flujo: validar el plan de la IA y convertirlo en SQL seguro.

Aunque el schema ya restringe a la IA, aquí se vuelve a validar todo: el
backend no confía en lo que devuelve el modelo (defensa en profundidad).
"""

import re
from datetime import date

from . import catalogo
from .ia import FiltroPlan, PlanConsulta

OPERACION_ESCRITURA = re.compile(
    r"\b(insert|update|delete|drop|alter|create|exec|truncate|grant"
    r"|elimina|eliminar|borra|borrar|modifica|modificar|actualiza|actualizar|inserta|insertar)\b",
    re.IGNORECASE,
)
FORMATO_MES = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
LIMITE_FILAS = 500
LIMITE_DETALLE = 50


def rechazo_previo(pregunta: str) -> str | None:
    """Regla determinista antes de gastar una llamada a la IA (RN-02)."""
    if OPERACION_ESCRITURA.search(pregunta):
        return "RN-02: la solicitud parece inducir una operación de escritura. Solo se permiten consultas de lectura."
    return None


def validar_plan(plan: PlanConsulta, cat: catalogo.Catalogo, dominios_usuario: set[str]) -> str | None:
    """Devuelve el motivo de rechazo, o None si el plan es ejecutable."""
    if plan.accion in ("rechazar", "aclarar"):
        return plan.motivo_rechazo or "La solicitud está fuera del catálogo autorizado."

    # Control de acceso: la IA solo dice de qué dominio es la pregunta;
    # el permiso se decide aquí, con seguridad.SEG_USUARIO_DOMINIO.
    nombre = cat.dominios.get(plan.dominio, plan.dominio)
    if plan.dominio not in dominios_usuario:
        return f"Acceso no autorizado al dominio {plan.dominio} ({nombre})."
    dominio = cat.disponibles.get(plan.dominio)
    if dominio is None:
        return f"El dominio {nombre} todavía no tiene tablas disponibles para consultar."

    if plan.metrica not in dominio.medidas:
        return f"RF-03: la métrica '{plan.metrica}' no está en el catálogo de {nombre}."
    if plan.agrupar_por not in dominio.dimensiones():
        return f"RF-03: no se puede agrupar por '{plan.agrupar_por}' en {nombre}."

    for f in plan.filtros:
        if f.campo not in dominio.atributos:
            return f"RF-03: no se puede filtrar por '{f.campo}' en {nombre}."
        if f.valor not in dominio.valores[f.campo]:
            return f"RF-03: el valor '{f.valor}' no es válido para {dominio.atributos[f.campo].etiqueta.lower()}."

    for valor in (plan.desde, plan.hasta):
        if valor and not FORMATO_MES.match(valor):
            return f"El período '{valor}' debe tener formato AAAA-MM."
    if (plan.desde or plan.hasta) and not dominio.con_fecha:
        return f"RF-03: el filtro por fecha no está disponible en {nombre}."
    if plan.desde and plan.hasta and plan.desde > plan.hasta:
        return "El inicio del período es posterior al término."
    return None


def _primer_dia(mes: str) -> date:
    anio, numero = mes.split("-")
    return date(int(anio), int(numero), 1)


def construir_sql(plan: PlanConsulta, cat: catalogo.Catalogo) -> dict[str, tuple[str, list]]:
    """Arma las consultas del reporte solo con fragmentos del catálogo; los
    valores van como parámetros. Devuelve {nombre: (sql, params)}:
    serie (para el gráfico), total (KPI) y detalle (tabla de registros)."""
    dominio = cat.disponibles[plan.dominio]
    metrica = dominio.sql_medida(plan.metrica)
    dimension = dominio.sql_dimension(plan.agrupar_por)
    fecha = catalogo.sql_columna(dominio.definicion.fecha.columna)

    condiciones, params = [], []
    for f in plan.filtros:
        condiciones.append(f"{catalogo.sql_columna(dominio.atributos[f.campo].columna)} = ?")
        params.append(f.valor)
    if plan.desde:
        condiciones.append(f"{fecha} >= ?")
        params.append(_primer_dia(plan.desde))
    if plan.hasta:
        condiciones.append(f"{fecha} < DATEADD(MONTH, 1, ?)")
        params.append(_primer_dia(plan.hasta))
    where = " WHERE " + " AND ".join(condiciones) if condiciones else ""
    origen = dominio.sql_from()

    consultas = {
        "total": (f"SELECT {metrica} AS valor, COUNT(*) AS cantidad FROM {origen}{where}", params),
    }
    if dimension:
        consultas["serie"] = (
            f"SELECT TOP ({LIMITE_FILAS}) {dimension} AS categoria, {metrica} AS valor FROM {origen}{where}"
            f" GROUP BY {dimension} ORDER BY categoria",
            params,
        )
    if dominio.detalle:
        columnas = ", ".join(f"{catalogo.sql_columna(a.columna)} AS [{a.etiqueta}]" for a in dominio.detalle)
        consultas["detalle"] = (
            f"SELECT TOP ({LIMITE_DETALLE}) {columnas} FROM {origen}{where} ORDER BY {fecha} DESC",
            params,
        )
    return consultas


def aplicar_filtros_panel(plan: PlanConsulta, cat: catalogo.Catalogo, filtros: dict[str, str],
                          desde: str, hasta: str) -> PlanConsulta:
    """Suma al plan los filtros elegidos en el panel del dashboard. Mandan sobre lo
    que haya entendido la IA para el mismo campo. Los campos que no existen en el
    dominio del plan se ignoran (por ejemplo, un filtro de siniestros en una
    pregunta de primas); los valores se validan después en validar_plan()."""
    dominio = cat.disponibles.get(plan.dominio)
    if dominio is None:
        return plan
    del_panel = {campo: valor for campo, valor in filtros.items() if campo in dominio.atributos and valor}
    combinados = [f for f in plan.filtros if f.campo not in del_panel]
    combinados += [FiltroPlan(campo=campo, valor=valor) for campo, valor in del_panel.items()]
    return plan.model_copy(update={
        "filtros": combinados,
        "desde": desde or plan.desde,
        "hasta": hasta or plan.hasta,
    })
