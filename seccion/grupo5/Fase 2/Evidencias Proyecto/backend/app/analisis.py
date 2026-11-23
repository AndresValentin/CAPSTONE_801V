"""Comparación con otro período y proyección de series mensuales.

Las dos funciones trabajan sobre los resultados reales de SQL Server, nunca sobre
datos inventados, y se niegan a calcular cuando el resultado sería engañoso:

- Comparar: solo métricas que miden lo ocurrido en un período (un flujo). Las que
  reflejan el estado de hoy (reserva, cuotas pendientes o vencidas) no se comparan:
  su "período anterior" no muestra cómo estaban las cosas en ese momento. Las reglas
  están en catalogo.Medida.comparable.
- Proyectar: regresión lineal por mínimos cuadrados sobre los meses completos, con
  un rango de ±2 errores estándar y detección de meses atípicos. Solo para métricas
  que se pueden comparar sin advertencias.
"""

import math
from datetime import date
from statistics import median

from . import catalogo
from .ia import PlanConsulta

TITULOS = {"periodo_anterior": "Período anterior", "anio_anterior": "Mismo período del año anterior"}
VENTANA_SIN_PERIODO = 12   # meses que se comparan cuando el gráfico no tiene período
MIN_MESES_PROYECCION = 6
MESES_PROYECCION = 3
UMBRAL_ATIPICO = 2.5       # desvíos robustos (MAD) para marcar un mes como atípico
R2_DEBIL = 0.3


def _indice(mes: str) -> int:
    anio, numero = mes.split("-")
    return int(anio) * 12 + int(numero) - 1


def _mes(indice: int) -> str:
    return f"{indice // 12:04d}-{indice % 12 + 1:02d}"


def mes_actual(hoy: date | None = None) -> str:
    hoy = hoy or date.today()
    return f"{hoy.year:04d}-{hoy.month:02d}"


def _advertencias_estado(plan: PlanConsulta, dominio: catalogo.DominioDisponible) -> list[str]:
    """Filtros o agrupaciones por un estado que solo existe tal como está hoy."""
    campos = [f.campo for f in plan.filtros] + [plan.agrupar_por]
    etiquetas = dict.fromkeys(
        dominio.atributos[c].etiqueta for c in campos
        if c in dominio.atributos and dominio.atributos[c].estado_actual
    )
    return [f"«{e}» usa el estado de hoy, no el que tenía cada registro en el período anterior." for e in etiquetas]


def preparar_comparacion(plan: PlanConsulta, dominio: catalogo.DominioDisponible,
                         hoy: date | None = None) -> tuple[PlanConsulta, PlanConsulta | None, dict | None]:
    """Devuelve (plan a ejecutar, plan del período anterior, información de la comparación).

    Si la comparación no es válida, el plan anterior es None y la información trae
    "omitida" con el motivo, para mostrárselo al usuario en vez de un número engañoso.
    Sin período elegido se comparan los últimos 12 meses con datos, y ese período
    queda en el plan para que la pantalla muestre exactamente lo que se comparó."""
    if not plan.comparar:
        return plan, None, None
    medida = dominio.medidas[plan.metrica]
    base = {"tipo": plan.comparar, "titulo": TITULOS[plan.comparar]}

    if medida.comparable == "no":
        return plan, None, {**base, "omitida": f"{medida.etiqueta} no se compara entre períodos. {medida.nota}"}
    if not dominio.con_fecha or not dominio.rango_meses:
        return plan, None, {**base, "omitida": "Esta área no tiene fechas para comparar períodos."}

    primero, ultimo = dominio.rango_meses
    advertencias = []
    # Un "hasta" posterior a los datos alargaría el período con meses vacíos y
    # desplazaría de más el período anterior: se mide hasta el último mes con datos
    hasta = min(plan.hasta or ultimo, ultimo)
    if plan.desde:
        desde = plan.desde
    else:
        desde = max(primero, _mes(_indice(hasta) - VENTANA_SIN_PERIODO + 1))
        if not plan.hasta:
            advertencias.append(f"Sin un período elegido, se comparan los últimos meses con datos ({desde} a {hasta}).")
    if desde > hasta:
        return plan, None, {**base, "omitida": f"No hay datos en el período elegido (hay datos entre {primero} y {ultimo})."}

    meses = _indice(hasta) - _indice(desde) + 1
    desplazamiento = meses if plan.comparar == "periodo_anterior" else 12
    desde_ant, hasta_ant = _mes(_indice(desde) - desplazamiento), _mes(_indice(hasta) - desplazamiento)

    if hasta_ant < primero:
        return plan, None, {**base, "omitida": f"No hay datos del período anterior ({desde_ant} a {hasta_ant}): los datos parten en {primero}."}
    if desde_ant < primero:
        advertencias.append(f"El período anterior está incompleto: los datos parten en {primero}.")
    if meses > desplazamiento:
        advertencias.append("Los dos períodos se superponen, porque el período elegido es más largo que un año.")
    if hasta >= mes_actual(hoy):
        advertencias.append(f"El período incluye {mes_actual(hoy)}, que aún no termina.")
    if medida.nota:
        advertencias.append(medida.nota)
    advertencias += _advertencias_estado(plan, dominio)

    info = {
        **base,
        "desde": desde_ant,
        "hasta": hasta_ant,
        "desplazamiento": desplazamiento,
        "advertencias": advertencias,
        "mejorSiBaja": medida.mejor_si_baja,
    }
    actual = plan.model_copy(update={"desde": desde, "hasta": plan.hasta or hasta})
    anterior = plan.model_copy(update={"desde": desde_ant, "hasta": hasta_ant, "comparar": ""})
    return actual, anterior, info


def completar_comparacion(info: dict, total_actual, total_anterior, serie_actual: list[dict],
                          serie_anterior: list[dict], agrupar_por: str) -> None:
    """Agrega a `info` el total anterior, la variación y, en cada fila de la serie
    actual, su valor en el período anterior. Por mes se alinea mes a mes (marzo con
    el marzo anterior), no por posición."""
    total_actual, total_anterior = total_actual or 0, total_anterior or 0
    info["total"] = total_anterior
    info["variacion"] = (round((total_actual - total_anterior) / abs(total_anterior) * 100, 1)
                         if total_anterior else None)

    if agrupar_por == catalogo.MES:
        anteriores = {_mes(_indice(f["categoria"]) + info["desplazamiento"]): f["valor"]
                      for f in serie_anterior if f["categoria"]}
    else:
        anteriores = {f["categoria"]: f["valor"] for f in serie_anterior}
    for fila in serie_actual:
        fila["anterior"] = anteriores.get(fila["categoria"])


def _ajustar(xs: list[float], ys: list[float]) -> dict:
    """Regresión lineal simple por mínimos cuadrados."""
    n = len(xs)
    media_x, media_y = sum(xs) / n, sum(ys) / n
    sxx = sum((x - media_x) ** 2 for x in xs)
    pendiente = sum((x - media_x) * (y - media_y) for x, y in zip(xs, ys)) / sxx
    intercepto = media_y - pendiente * media_x
    sse = sum((y - intercepto - pendiente * x) ** 2 for x, y in zip(xs, ys))
    sst = sum((y - media_y) ** 2 for y in ys)
    return {
        "n": n,
        "media_x": media_x,
        "sxx": sxx,
        "pendiente": pendiente,
        "r2": 1 - sse / sst if sst else 1.0,
        "error": math.sqrt(sse / (n - 2)) if n > 2 else 0.0,  # error estándar de la estimación
        "predecir": lambda x: intercepto + pendiente * x,
    }


def proyectar(serie: list[dict], plan: PlanConsulta, dominio: catalogo.DominioDisponible,
              hoy: date | None = None) -> dict | None:
    """Proyección de los próximos meses para un gráfico agrupado por mes.

    None si el gráfico no es por mes. Si no corresponde proyectar, devuelve
    {"omitida": motivo} para que la pantalla explique por qué."""
    if plan.agrupar_por != catalogo.MES:
        return None
    medida = dominio.medidas[plan.metrica]
    if dominio.definicion.sin_proyeccion:
        return {"omitida": dominio.definicion.sin_proyeccion}
    if medida.comparable != "si":
        return {"omitida": f"{medida.etiqueta} no se proyecta. {medida.nota}"}

    # Solo meses completos: el mes en curso (y cualquier fecha futura) quedaría bajo
    actual = mes_actual(hoy)
    valores = {f["categoria"]: float(f["valor"] or 0) for f in serie if f["categoria"] and f["categoria"] < actual}
    excluidos = sorted(f["categoria"] for f in serie if f["categoria"] and f["categoria"] >= actual)
    if not valores:
        return {"omitida": "No hay meses completos para proyectar."}

    inicio, fin = _indice(min(valores)), _indice(max(valores))
    es_promedio = "AVG(" in medida.sql
    meses = [_mes(i) for i in range(inicio, fin + 1)]
    # En sumas y conteos, un mes sin registros vale 0; un promedio sin registros no existe
    if es_promedio:
        meses = [m for m in meses if m in valores]
    if len(meses) < MIN_MESES_PROYECCION:
        return {"omitida": f"Se necesitan al menos {MIN_MESES_PROYECCION} meses completos para proyectar (hay {len(meses)})."}

    xs = [_indice(m) - inicio for m in meses]
    ys = [valores.get(m, 0.0) for m in meses]
    recta = _ajustar(xs, ys)

    # Atípicos con un desvío robusto (MAD): un mes extremo no infla el criterio que lo detecta
    residuos = [y - recta["predecir"](x) for x, y in zip(xs, ys)]
    centro = median(residuos)
    mad = 1.4826 * median(abs(r - centro) for r in residuos)
    atipicos = {i for i, r in enumerate(residuos) if mad > 0 and abs(r - centro) / mad > UMBRAL_ATIPICO}

    notas = []
    # Un mes atípico (un evento puntual) no debe torcer la tendencia: se ajusta sin él
    if atipicos and len(xs) - len(atipicos) >= MIN_MESES_PROYECCION:
        recta = _ajustar([x for i, x in enumerate(xs) if i not in atipicos],
                         [y for i, y in enumerate(ys) if i not in atipicos])
        notas.append("La tendencia se calculó sin los meses atípicos.")
    anomalias = [
        {"mes": meses[i], "valor": round(ys[i], 2), "esperado": round(recta["predecir"](xs[i]), 2)}
        for i in sorted(atipicos)
    ]

    n, media_x, sxx, error = recta["n"], recta["media_x"], recta["sxx"], recta["error"]
    pendiente, r2 = recta["pendiente"], recta["r2"]
    sin_negativos = min(ys) >= 0
    proyeccion = []
    for paso in range(1, MESES_PROYECCION + 1):
        x = fin - inicio + paso
        valor = recta["predecir"](x)
        margen = 2 * error * math.sqrt(1 + 1 / n + (x - media_x) ** 2 / sxx)
        minimo, maximo = valor - margen, valor + margen
        if sin_negativos:
            valor, minimo, maximo = max(valor, 0), max(minimo, 0), max(maximo, 0)
        proyeccion.append({"mes": _mes(fin + paso), "valor": round(valor, 2), "min": round(minimo, 2), "max": round(maximo, 2)})

    # Una caída brusca al final suele ser carga incompleta, no una tendencia real
    habitual = median(ys[:-3])
    if habitual > 0 and sum(ys[-3:]) / 3 < 0.5 * habitual:
        notas.append("Los últimos 3 meses están muy por debajo de lo habitual. Si los datos de esos meses aún no "
                     "están completos, la proyección se verá más baja de lo real.")
    if sin_negativos and max(ys) > 0 and any(m["valor"] == 0 for m in proyeccion):
        notas.append("La tendencia llega a cero en los meses proyectados: revisa los últimos meses antes de usar esta cifra.")
    if r2 < R2_DEBIL:
        r2_texto = f"{r2:.2f}".replace(".", ",")
        notas.append(f"La tendencia explica poco de la variación mensual (R² {r2_texto}): toma la proyección solo como referencia.")
    if excluidos:
        notas.append(f"No se usan {', '.join(excluidos)}: son meses que aún no terminan.")
    return {
        "meses": proyeccion,
        "pendiente": round(pendiente, 2),
        "r2": round(r2, 3),
        "base": {"desde": meses[0], "hasta": meses[-1], "meses": n},
        "anomalias": anomalias,
        "notas": notas,
    }
