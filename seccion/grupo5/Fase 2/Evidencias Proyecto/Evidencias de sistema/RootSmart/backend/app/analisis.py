"""Comparación con otro período y proyección de series mensuales.

Las dos funciones trabajan sobre los resultados reales de SQL Server, nunca sobre
datos inventados, y se niegan a calcular cuando el resultado sería engañoso:

- Comparar: solo métricas que miden lo ocurrido en un período (un flujo). Las que
  reflejan el estado de hoy (reserva, cuotas pendientes o vencidas) no se comparan:
  su "período anterior" no muestra cómo estaban las cosas en ese momento. Las reglas
  están en catalogo.Medida.comparable.
- Proyectar: suavizamiento exponencial con tendencia amortiguada (Holt) sobre los
  meses completos, con parámetros elegidos con los datos, un rango de ±2 errores
  típicos y aviso de meses atípicos. Parte del último nivel y sigue la dirección de
  la tendencia reciente. Solo para métricas que se pueden comparar sin advertencias.
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
UMBRAL_ATIPICO = 3.0       # desvíos robustos (MAD) del error de un mes para marcarlo como atípico
VARIACION_ALTA = 0.25      # error típico sobre el nivel de los últimos 12 meses
# Valores que se prueban al entrenar el modelo (ver _entrenar)
ALFAS = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
BETAS = (0.05, 0.1, 0.2, 0.3, 0.5)
PHIS = (0.8, 0.9, 0.98)
CALENTAMIENTO = 2          # pronósticos iniciales que no cuentan al elegir los valores
UMBRAL_SALTO = 5.0         # veces el cambio mensual típico para considerar un salto de nivel
MIN_MESES_TRAS_CAMBIO = 4  # meses desde un cambio de nivel para proyectar el nivel nuevo
MIN_MESES_TENDENCIA = 8    # con menos meses se proyecta el nivel, sin tendencia
MESES_ACIERTO = 6          # meses recientes con que se mide cuánto acierta el pronóstico


def _indice(mes: str) -> int:
    anio, numero = mes.split("-")
    return int(anio) * 12 + int(numero) - 1


def _mes(indice: int) -> str:
    return f"{indice // 12:04d}-{indice % 12 + 1:02d}"


def mes_actual(hoy: date | None = None) -> str:
    hoy = hoy or date.today()
    return f"{hoy.year:04d}-{hoy.month:02d}"


def sumar_meses(mes: str, n: int) -> str:
    return _mes(_indice(mes) + n)


def ultimo_mes_completo(rango_meses: tuple[str, str], hoy: date | None = None) -> str:
    """El último mes con datos que ya terminó (el mes en curso aún está incompleto)."""
    return min(rango_meses[1], sumar_meses(mes_actual(hoy), -1))


def completar_meses(serie: list[dict], plan: PlanConsulta, dominio: catalogo.DominioDisponible) -> list[dict]:
    """Agrega con valor 0 los meses sin registros entre el primero y el último de la serie.
    SQL solo devuelve los meses que tienen filas: sin esto, en un gráfico de líneas
    2025-05 quedaba pegado a 2026-01 como si fuera el mes siguiente. En un promedio un
    mes sin registros no vale 0, así que esa serie se deja como está."""
    if plan.agrupar_por != catalogo.MES or "AVG(" in dominio.medidas[plan.metrica].sql:
        return serie
    por_mes = {f["categoria"]: f for f in serie if f["categoria"]}
    if not por_mes:
        return serie
    sin_mes = [f for f in serie if not f["categoria"]]
    inicio, fin = _indice(min(por_mes)), _indice(max(por_mes))
    return sin_mes + [por_mes.get(_mes(i)) or {"categoria": _mes(i), "valor": 0} for i in range(inicio, fin + 1)]


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


def _holt(ys: list[float], alfa: float, beta: float, phi: float, con_tendencia: bool = True) -> tuple[float, float, list[float]]:
    """Suavizamiento exponencial con tendencia amortiguada (Holt). Recorre la serie mes a
    mes: pronostica el mes siguiente con el nivel y la tendencia que lleva, compara con el
    valor real y corrige ambos. Devuelve el nivel y la tendencia del último mes y los
    errores de cada pronóstico de un mes (real - pronosticado).
    Sin tendencia (beta 0, phi 1) es un suavizamiento simple: solo sigue el nivel."""
    paso = min(3, len(ys) - 1)
    # El punto de partida es la mediana de los primeros meses: un mes raro al inicio no lo tuerce
    nivel = median(ys[:3])
    tendencia = (median(ys[paso:paso + 3]) - nivel) / paso if con_tendencia else 0.0
    errores = []
    for y in ys[1:]:
        pronostico = nivel + phi * tendencia
        errores.append(y - pronostico)
        nivel_anterior = nivel
        nivel = alfa * y + (1 - alfa) * pronostico
        tendencia = beta * (nivel - nivel_anterior) + (1 - beta) * phi * tendencia
    return nivel, tendencia, errores


def _entrenar(ys: list[float], con_tendencia: bool) -> dict:
    """Elige alfa (cuánto pesa el último mes en el nivel), beta (qué tan rápido cambia la
    tendencia) y phi (cuánto se frena la tendencia hacia adelante) con los datos: la
    combinación cuyos pronósticos de un mes habrían errado menos en la historia."""
    mejor = None
    for alfa in ALFAS:
        for beta in BETAS if con_tendencia else (0.0,):
            for phi in PHIS if con_tendencia else (1.0,):
                nivel, tendencia, errores = _holt(ys, alfa, beta, phi, con_tendencia)
                evaluados = errores[CALENTAMIENTO:]  # los primeros meses aún no se ajustan
                sse = sum(e * e for e in evaluados)
                if mejor is None or sse < mejor["sse"]:
                    mejor = {"alfa": alfa, "beta": beta, "phi": phi, "nivel": nivel, "tendencia": tendencia,
                             "errores": errores, "sse": sse, "evaluados": len(evaluados)}
    # Error típico de un pronóstico a un mes (3 parámetros elegidos con los datos)
    mejor["error"] = math.sqrt(mejor["sse"] / max(mejor["evaluados"] - 3, 1))
    return mejor


def _cambio_de_nivel(ys: list[float]) -> int | None:
    """Posición del último salto brusco que se mantuvo (por ejemplo, de ~650 M a ~2 M y
    luego plano), o None. Antes de un salto así hay otra realidad: entrenar con esos meses
    arrastraría la proyección. Se distingue de una tendencia: en una caída pareja los
    promedios de antes y después difieren varias veces el salto de un mes; en un cambio
    de nivel difieren lo mismo que el salto. Hacen falta 2 meses después para saber que se mantuvo."""
    cambios = [abs(b - a) for a, b in zip(ys, ys[1:])]
    tipico = median(cambios)
    for t in range(len(ys) - 2, 2, -1):  # t = primer mes del nivel nuevo, del más reciente hacia atrás
        salto = ys[t] - ys[t - 1]
        antes, despues = ys[t - 3:t], ys[t:t + 3]
        nivel_antes = sum(antes) / len(antes)
        diferencia = sum(despues) / len(despues) - nivel_antes
        if (salto and abs(salto) > UMBRAL_SALTO * tipico and abs(salto) > 0.3 * abs(nivel_antes)
                and 0.6 <= diferencia / salto <= 1.6):
            return t
    return None


def _anomalias(meses: list[str], ys: list[float], errores: list[float]) -> list[dict]:
    """Meses puntuales muy distintos de lo que se esperaba un mes antes y que luego
    volvieron a lo normal (un peak o una caída aislada). Un cambio que se mantiene no es
    atípico: es la tendencia, y así se trata. Solo se informan; no se quitan del cálculo."""
    if len(errores) < 3:
        return []
    centro = median(errores)
    mad = 1.4826 * median(abs(e - centro) for e in errores)
    if mad == 0:
        return []
    salida = []
    # Ni los primeros pronósticos (el modelo aún no se ajusta) ni el último mes (aún no se
    # sabe si fue puntual)
    for i, e in enumerate(errores[:-1]):
        if i < CALENTAMIENTO:
            continue
        extremo = abs(e - centro) / mad > UMBRAL_ATIPICO
        # Volvió: el mes siguiente se equivocó claramente hacia el otro lado (no es el inicio de una tendencia)
        siguiente = errores[i + 1] - centro
        volvio = (e - centro) * siguiente < 0 and abs(siguiente) / mad > 1.0
        if extremo and volvio:
            salida.append({"mes": meses[i + 1], "valor": round(ys[i + 1], 2), "esperado": round(ys[i + 1] - e, 2)})
    return salida


def proyectar(serie: list[dict], plan: PlanConsulta, dominio: catalogo.DominioDisponible,
              hoy: date | None = None) -> dict | None:
    """Proyección de los próximos meses para un gráfico agrupado por mes.

    Usa suavizamiento exponencial con tendencia amortiguada (Holt), el mismo tipo de
    método del pronóstico de Power BI, con parámetros elegidos con los datos. A diferencia
    de una recta sobre toda la historia, pesa más los meses recientes y parte del último
    nivel: si la serie viene bajando, la proyección sigue bajando (y se va frenando), no
    salta de vuelta al promedio histórico.

    None si el gráfico no es por mes. Si no corresponde proyectar, devuelve
    {"omitida": motivo} para que la pantalla explique por qué."""
    if plan.agrupar_por != catalogo.MES:
        return None
    medida = dominio.medidas[plan.metrica]
    if dominio.definicion.sin_proyeccion:
        return {"omitida": dominio.definicion.sin_proyeccion}
    if medida.comparable != "si":
        return {"omitida": f"{medida.etiqueta} no se proyecta. {medida.nota}"}
    # Un gráfico que termina antes de los últimos datos (por ejemplo, el dashboard de abril
    # cuando ya hay datos de septiembre) "proyectaría" meses que ya ocurrieron: no se
    # proyecta ni se muestra aviso, porque mira el pasado a propósito
    if plan.hasta and dominio.rango_meses and plan.hasta < ultimo_mes_completo(dominio.rango_meses, hoy):
        return None

    # Solo meses completos: el mes en curso (y cualquier fecha futura) quedaría bajo
    actual = mes_actual(hoy)
    valores = {f["categoria"]: float(f["valor"] or 0) for f in serie if f["categoria"] and f["categoria"] < actual}
    excluidos = sorted(f["categoria"] for f in serie if f["categoria"] and f["categoria"] >= actual)
    if not valores:
        return {"omitida": "No hay meses completos para proyectar."}

    inicio, fin = _indice(min(valores)), _indice(max(valores))
    meses = [_mes(i) for i in range(inicio, fin + 1)]
    # En sumas y conteos, un mes sin registros vale 0; un promedio sin registros no existe
    if "AVG(" in medida.sql:
        meses = [m for m in meses if m in valores]
    if len(meses) < MIN_MESES_PROYECCION:
        return {"omitida": f"Se necesitan al menos {MIN_MESES_PROYECCION} meses completos para proyectar (hay {len(meses)})."}

    ys = [valores.get(m, 0.0) for m in meses]
    sin_negativos = min(ys) >= 0
    notas = []
    corte = _cambio_de_nivel(ys)
    if corte is not None:
        quedan = len(ys) - corte
        if quedan < MIN_MESES_TRAS_CAMBIO:
            return {"omitida": f"La serie cambió bruscamente de nivel en {meses[corte]} y desde entonces hay "
                               f"{quedan} meses: se necesitan {MIN_MESES_TRAS_CAMBIO} para proyectar el nivel nuevo."}
        notas.append(f"La serie cambió bruscamente de nivel en {meses[corte]}: la proyección usa solo los meses "
                     "desde ese cambio, porque los anteriores muestran otra realidad.")
        meses, ys = meses[corte:], ys[corte:]

    # Con pocos meses una "tendencia" es más ruido que señal: se proyecta el nivel actual
    con_tendencia = len(ys) >= MIN_MESES_TENDENCIA
    if not con_tendencia:
        notas.append(f"Con {len(ys)} meses no alcanza para estimar una tendencia: se proyecta el nivel actual.")
    modelo = _entrenar(ys, con_tendencia)
    alfa, beta, phi = modelo["alfa"], modelo["beta"], modelo["phi"]
    nivel, tendencia, error = modelo["nivel"], modelo["tendencia"], modelo["error"]

    proyeccion = []
    acumulado_phi, varianza = 0.0, 0.0
    for paso in range(1, MESES_PROYECCION + 1):
        acumulado_phi += phi ** paso
        valor = nivel + acumulado_phi * tendencia
        # Incertidumbre del pronóstico a `paso` meses: crece con la distancia
        if paso > 1:
            varianza += (alfa * (1 + beta * (acumulado_phi - phi ** paso))) ** 2
        margen = 2 * error * math.sqrt(1 + varianza)
        minimo, maximo = valor - margen, valor + margen
        if sin_negativos:
            valor, minimo, maximo = max(valor, 0), max(minimo, 0), max(maximo, 0)
        proyeccion.append({"mes": _mes(fin + paso), "valor": round(valor, 2), "min": round(minimo, 2), "max": round(maximo, 2)})

    # Una caída que se acelera al final puede ser carga incompleta: la proyección la sigue igual
    previos = sum(ys[-6:-3]) / 3 if len(ys) >= 6 else 0
    datos_dudosos = previos > 0 and sum(ys[-3:]) / 3 < 0.5 * previos
    if datos_dudosos:
        notas.append("Los últimos 3 meses cayeron a menos de la mitad de los 3 anteriores y la proyección sigue esa "
                     "caída. Si esos meses aún no están completos en la base, revisa la carga antes de usar esta cifra.")
    if sin_negativos and max(ys) > 0 and any(m["valor"] == 0 for m in proyeccion):
        notas.append("La tendencia llega a cero en los meses proyectados.")
    referencia = sum(abs(y) for y in ys[-12:]) / len(ys[-12:])
    if referencia and error / referencia > VARIACION_ALTA:
        notas.append("La serie varía mucho de un mes a otro: toma la proyección solo como referencia y mira el rango.")
    if excluidos:
        notas.append(f"No se usan {', '.join(excluidos)}: son meses que aún no terminan.")
    if meses[-1] < _mes(_indice(actual) - 1) and not (plan.hasta and plan.hasta <= meses[-1]):
        notas.append(f"Los datos llegan hasta {meses[-1]}: la proyección parte del mes siguiente, no de hoy.")

    # Cuánto acertó en los últimos meses: el modelo pronosticó cada mes solo con los datos
    # que había hasta el mes anterior, igual que hará con los próximos
    recientes = list(zip(meses[1:], ys[1:], modelo["errores"]))[-MESES_ACIERTO:]
    nivel_reciente = sum(abs(y) for _, y, _ in recientes) / len(recientes) if recientes else 0
    error_relativo = (sum(abs(e) for _, _, e in recientes) / len(recientes) / nivel_reciente) if nivel_reciente else None
    return {
        "metodo": "Suavizamiento exponencial con tendencia (Holt)",
        "meses": proyeccion,
        "tendencia": round(phi * tendencia, 2),  # cambio esperado para el próximo mes
        "error": round(error, 2),                 # error típico de un pronóstico a un mes
        "parametros": {"alfa": alfa, "beta": beta, "phi": phi},
        "base": {"desde": meses[0], "hasta": meses[-1], "meses": len(meses)},
        "anomalias": _anomalias(meses, ys, modelo["errores"]),
        "notas": notas,
        # Error promedio de esos pronósticos sobre lo real (0,12 = se equivocó un 12 %)
        "acierto": {
            "meses": len(recientes),
            # Los últimos meses cayeron de golpe: puede ser carga incompleta, no una tendencia real
            "datos_dudosos": datos_dudosos,
            "error_relativo": round(error_relativo, 3) if error_relativo is not None else None,
            "detalle": [{"mes": m, "real": round(y, 2), "esperado": round(y - e, 2)} for m, y, e in recientes],
        },
    }
