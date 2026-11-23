"""Catálogo autorizado: qué puede consultarse y cómo se traduce a SQL.

Hay dos partes:
- La capa semántica (este archivo): para cada dominio, las métricas y
  agrupaciones que entiende el copiloto y las columnas físicas que usa cada
  una. Es la única fuente de fragmentos SQL; nunca se usa texto escrito por
  la IA o el usuario.
- Los metadatos de la BD (meta.MET_TABLA / MET_COLUMNA / MET_RELACION):
  deciden qué de lo anterior está habilitado. Si una tabla, columna o
  relación no está activa o no está disponible para la IA, lo que dependa de
  ella desaparece del catálogo. Los valores de los filtros salen de la BD.
"""

import time
from dataclasses import dataclass, field

import pyodbc

from . import db

VERSION = "catalogo-v0.9"

Columna = tuple[str, str]  # (tabla, columna) tal como aparecen en meta.MET_COLUMNA


@dataclass(frozen=True)
class Medida:
    etiqueta: str
    sql: str
    columnas: tuple[Columna, ...] = ()
    moneda: bool = False
    # Si tiene sentido compararla con otro período y proyectarla (ver analisis.py):
    # "si", "advertencia" (se compara, con una nota) o "no" (refleja el estado de hoy).
    comparable: str = "si"
    nota: str = ""
    mejor_si_baja: bool = False  # para pintar una variación como buena o mala


@dataclass(frozen=True)
class Atributo:
    etiqueta: str
    columna: Columna
    moneda: bool = False  # solo para columnas de detalle con montos
    estado_actual: bool = False  # guarda el estado de hoy, no el que tenía en el pasado


@dataclass(frozen=True)
class Union:
    """JOIN hacia una tabla de atributos. Debe existir en meta.MET_RELACION."""
    tabla: str
    columna_origen: str
    columna_destino: str
    origen: str | None = None  # tabla desde la que se une; None = la tabla de hechos


@dataclass(frozen=True)
class DefinicionDominio:
    tabla: str                       # tabla de hechos (schema ods)
    uniones: tuple[Union, ...]
    fecha: Atributo                  # columna para "por mes" y para desde/hasta
    medidas: dict[str, Medida]
    atributos: dict[str, Atributo]   # sirven para agrupar y para filtrar
    detalle: tuple[Atributo, ...]    # columnas de la tabla de detalle del reporte
    permiso: str | None = None       # dominio de seguridad que da acceso, si no es el propio
    # Por qué no se proyecta la serie mensual del dominio ("" = sí se proyecta)
    sin_proyeccion: str = ""


SIN, FIN, SEG = "ODS_SIN_SINIESTRO", "ODS_FIN_PRIMA", "ODS_SEG_SEGURO"
CLIENTE = "ODS_SEG_CLIENTE"
CUOTA = "ODS_FIN_CUOTA_PRIMA"

# Áreas de consulta que no existen en seguridad.SEG_DOMINIO: usan el permiso de otro dominio
AREAS_PROPIAS = {"CUO": "Cobranza de cuotas"}

# Atributos de la póliza, compartidos por los dominios que se unen a ODS_SEG_SEGURO
_PRODUCTO = Atributo("Producto", (SEG, "DESC_PRODUCTO"))
_REGION = Atributo("Región", (SEG, "DESC_REGION"))
_POLIZA = Atributo("Póliza", (SEG, "COD_POLIZA"))


def _medida_prima(etiqueta: str, columna: str) -> Medida:
    """Las columnas de prima guardan montos positivos incluso en las anulaciones
    (15_ALTER_ODS_FIN_PRIMA.sql), así que el neto debe restarlas."""
    return Medida(
        etiqueta,
        f"SUM(CASE WHEN {{FIN}}.DESC_TIPO_MOVIMIENTO = 'ANULACION' THEN -{{FIN}}.{columna} ELSE {{FIN}}.{columna} END)",
        ((FIN, columna), (FIN, "DESC_TIPO_MOVIMIENTO")),
        True,
    )


def _medida_cuota(etiqueta: str, condicion: str, **reglas) -> Medida:
    return Medida(
        etiqueta,
        f"SUM(CASE WHEN {condicion} THEN {{CUOTA}}.MNT_CUOTA ELSE 0 END)",
        ((CUOTA, "MNT_CUOTA"), (CUOTA, "DESC_ESTADO_CUOTA"), (CUOTA, "DT_FECHA_VENCIMIENTO")),
        True,
        **reglas,
    )


# Reglas de negocio para comparar períodos (validar con el responsable de datos)
_MADURACION_PAGOS = ("Los siniestros recientes aún pueden recibir pagos, así que el período más "
                     "reciente tiende a verse menor.")
_SALDO_RESERVA = ("Es el saldo de hoy: los siniestros antiguos ya se cerraron y su reserva bajó, "
                  "así que compararla con otro período lleva a una conclusión falsa.")
_EMITIDO = "Cuenta lo emitido en cada período (ventas nuevas), no la cartera vigente."


DEFINICIONES: dict[str, DefinicionDominio] = {
    "SIN": DefinicionDominio(
        tabla=SIN,
        uniones=(Union(SEG, "ID_ITEM", "ID_ITEM"),),
        fecha=Atributo("Fecha de ocurrencia", (SIN, "DT_FECHA_OCURRENCIA")),
        medidas={
            "cantidad_siniestros": Medida("Cantidad de siniestros", "COUNT(*)", mejor_si_baja=True),
            "monto_pagado": Medida("Monto pagado", "SUM({SIN}.MNT_PAGADO)", ((SIN, "MNT_PAGADO"),), True,
                                   comparable="advertencia", nota=_MADURACION_PAGOS, mejor_si_baja=True),
            "monto_pagado_promedio": Medida("Monto pagado promedio", "AVG({SIN}.MNT_PAGADO)", ((SIN, "MNT_PAGADO"),), True,
                                            comparable="advertencia", nota=_MADURACION_PAGOS, mejor_si_baja=True),
            "monto_denunciado": Medida("Monto denunciado", "SUM({SIN}.MNT_DENUNCIADO)", ((SIN, "MNT_DENUNCIADO"),), True,
                                       mejor_si_baja=True),
            "monto_reserva": Medida("Monto en reserva", "SUM({SIN}.MNT_RESERVA)", ((SIN, "MNT_RESERVA"),), True,
                                    comparable="no", nota=_SALDO_RESERVA, mejor_si_baja=True),
            "monto_recuperado": Medida("Monto recuperado", "SUM({SIN}.MNT_RECUPERADO)", ((SIN, "MNT_RECUPERADO"),), True,
                                       comparable="advertencia",
                                       nota="Los recuperos llegan meses después del siniestro: el período más reciente tiende a verse menor."),
        },
        atributos={
            "tipo_siniestro": Atributo("Tipo de siniestro", (SIN, "DESC_TIPO_SINIESTRO")),
            "estado_siniestro": Atributo("Estado del siniestro", (SIN, "DESC_ESTADO_SINIESTRO"), estado_actual=True),
            "producto": _PRODUCTO,
            "region": _REGION,
        },
        detalle=(
            Atributo("Siniestro", (SIN, "COD_SINIESTRO")),
            _POLIZA,
            Atributo("Ocurrencia", (SIN, "DT_FECHA_OCURRENCIA")),
            Atributo("Tipo", (SIN, "DESC_TIPO_SINIESTRO")),
            Atributo("Estado", (SIN, "DESC_ESTADO_SINIESTRO")),
            _PRODUCTO,
            _REGION,
            Atributo("Denunciado", (SIN, "MNT_DENUNCIADO"), True),
            Atributo("Reserva", (SIN, "MNT_RESERVA"), True),
            Atributo("Pagado", (SIN, "MNT_PAGADO"), True),
            Atributo("Recuperado", (SIN, "MNT_RECUPERADO"), True),
        ),
    ),
    "FIN": DefinicionDominio(
        tabla=FIN,
        uniones=(Union(SEG, "ID_ITEM", "ID_ITEM"),),
        fecha=Atributo("Fecha del movimiento", (FIN, "DT_FECHA_MOVIMIENTO")),
        medidas={
            "prima_total": _medida_prima("Prima directa neta", "MNT_PRIMA_DIRECTA"),
            "prima_cedida": _medida_prima("Prima cedida neta", "MNT_PRIMA_CEDIDA"),
            "prima_retenida": _medida_prima("Prima retenida neta", "MNT_PRIMA_RETENIDA"),
            "comision_total": Medida("Comisión total", "SUM({FIN}.MNT_COMISION)", ((FIN, "MNT_COMISION"),), True),
            "cantidad_movimientos": Medida("Cantidad de movimientos de prima", "COUNT(*)"),
        },
        atributos={
            "tipo_movimiento": Atributo("Tipo de movimiento", (FIN, "DESC_TIPO_MOVIMIENTO")),
            "producto": _PRODUCTO,
            "region": _REGION,
        },
        detalle=(
            _POLIZA,
            Atributo("Código", (FIN, "COD_MOVIMIENTO_PRIMA")),
            Atributo("Movimiento", (FIN, "NRO_MOVIMIENTO")),
            Atributo("Fecha", (FIN, "DT_FECHA_MOVIMIENTO")),
            Atributo("Tipo", (FIN, "DESC_TIPO_MOVIMIENTO")),
            Atributo("Cuotas", (FIN, "Q_CUOTAS")),
            _PRODUCTO,
            Atributo("Prima directa", (FIN, "MNT_PRIMA_DIRECTA"), True),
            Atributo("Prima cedida", (FIN, "MNT_PRIMA_CEDIDA"), True),
            Atributo("Prima retenida", (FIN, "MNT_PRIMA_RETENIDA"), True),
            Atributo("Comisión", (FIN, "MNT_COMISION"), True),
        ),
    ),
    "SEG": DefinicionDominio(
        tabla=SEG,
        uniones=(Union(CLIENTE, "ID_CLIENTE", "ID_CLIENTE"),),
        fecha=Atributo("Fecha de emisión", (SEG, "DT_FECHA_EMISION")),
        medidas={
            "cantidad_items": Medida("Cantidad de ítems asegurados", "COUNT(*)", nota=_EMITIDO),
            "cantidad_polizas": Medida("Cantidad de pólizas", "COUNT(DISTINCT {SEG}.COD_POLIZA)", ((SEG, "COD_POLIZA"),),
                                       nota=_EMITIDO),
            "monto_asegurado": Medida("Monto asegurado", "SUM({SEG}.MNT_MONTO_ASEGURADO)", ((SEG, "MNT_MONTO_ASEGURADO"),), True,
                                      nota=_EMITIDO),
        },
        atributos={
            "producto": _PRODUCTO,
            "region": _REGION,
            "estado_poliza": Atributo("Estado de la póliza", (SEG, "DESC_ESTADO_POLIZA"), estado_actual=True),
            "segmento": Atributo("Segmento del cliente", (CLIENTE, "DESC_SEGMENTO")),
            "tipo_cliente": Atributo("Tipo de cliente", (CLIENTE, "DESC_TIPO_CLIENTE")),
        },
        detalle=(
            _POLIZA,
            Atributo("Certificado", (SEG, "COD_CERTIFICADO")),
            _PRODUCTO,
            _REGION,
            Atributo("Emisión", (SEG, "DT_FECHA_EMISION")),
            Atributo("Inicio de vigencia", (SEG, "DT_FECHA_INICIO_VIGENCIA")),
            Atributo("Fin de vigencia", (SEG, "DT_FECHA_FIN_VIGENCIA")),
            Atributo("Estado", (SEG, "DESC_ESTADO_POLIZA")),
            Atributo("Monto asegurado", (SEG, "MNT_MONTO_ASEGURADO"), True),
        ),
    ),
    "CUO": DefinicionDominio(
        tabla=CUOTA,
        permiso="FIN",
        sin_proyeccion="Las cuotas de los próximos meses ya están programadas: no hace falta proyectarlas.",
        uniones=(
            Union(FIN, "ID_MOVIMIENTO_PRIMA", "ID_MOVIMIENTO_PRIMA"),
            Union(SEG, "ID_ITEM", "ID_ITEM", origen=FIN),
        ),
        fecha=Atributo("Fecha de vencimiento", (CUOTA, "DT_FECHA_VENCIMIENTO")),
        medidas={
            "monto_cuotas": Medida("Monto total de cuotas", "SUM({CUOTA}.MNT_CUOTA)", ((CUOTA, "MNT_CUOTA"),), True),
            "monto_cuotas_pagadas": _medida_cuota(
                "Monto de cuotas pagadas", "{CUOTA}.DESC_ESTADO_CUOTA = 'PAGADA'",
                comparable="advertencia",
                nota="Algunas cuotas se pagan tarde: el período más reciente tiende a verse menor.",
            ),
            "monto_cuotas_pendientes": _medida_cuota(
                "Monto de cuotas pendientes", "{CUOTA}.DESC_ESTADO_CUOTA = 'PENDIENTE'",
                comparable="no", mejor_si_baja=True,
                nota="Usa el estado de hoy: el período anterior no muestra lo que estaba pendiente en esa fecha.",
            ),
            "monto_cuotas_vencidas": _medida_cuota(
                "Monto de cuotas vencidas sin pagar",
                "{CUOTA}.DESC_ESTADO_CUOTA = 'PENDIENTE' AND {CUOTA}.DT_FECHA_VENCIMIENTO < CAST(GETDATE() AS DATE)",
                comparable="no", mejor_si_baja=True,
                nota="Se calcula con la fecha de hoy: el período anterior no muestra la morosidad que existía en ese momento.",
            ),
            "cantidad_cuotas": Medida("Cantidad de cuotas", "COUNT(*)"),
        },
        atributos={
            "estado_cuota": Atributo("Estado de la cuota", (CUOTA, "DESC_ESTADO_CUOTA"), estado_actual=True),
            "producto": _PRODUCTO,
            "region": _REGION,
        },
        detalle=(
            _POLIZA,
            Atributo("Movimiento", (FIN, "COD_MOVIMIENTO_PRIMA")),
            Atributo("Cuota", (CUOTA, "NRO_CUOTA")),
            Atributo("Vencimiento", (CUOTA, "DT_FECHA_VENCIMIENTO")),
            Atributo("Estado", (CUOTA, "DESC_ESTADO_CUOTA")),
            Atributo("Fecha de pago", (CUOTA, "DT_FECHA_PAGO")),
            _PRODUCTO,
            _REGION,
            Atributo("Monto", (CUOTA, "MNT_CUOTA"), True),
        ),
    ),
}

MES = "mes"
NINGUNO = "ninguno"
TIPOS_SALIDA = ["kpi", "grafico_barras", "grafico_lineas", "grafico_torta", "grafico_mapa", "tabla"]


@dataclass(frozen=True)
class Recomendacion:
    pregunta: str
    metrica: str
    agrupar_por: str
    motivo: str


# Gráficos sugeridos en el chat: los que responden una pregunta del negocio, del más
# útil al menos útil. El texto es lo que se envía a la IA, así que va en palabras simples;
# el tipo sigue lo que hay que leer: líneas para tendencias (con el año anterior al lado,
# para saber si se está mejor o peor), barras o mapa para comparar dónde se concentra y
# torta solo para repartos de pocas partes.
RECOMENDACIONES: dict[str, tuple[Recomendacion, ...]] = {
    "SIN": (
        Recomendacion("Monto pagado por región en mapa", "monto_pagado", "region", "Dónde se concentra el gasto en siniestros"),
        Recomendacion("Siniestros por mes comparado con el año anterior", "cantidad_siniestros", MES, "¿Llegan más o menos casos que hace un año?"),
        Recomendacion("Monto pagado por tipo de siniestro", "monto_pagado", "tipo_siniestro", "Qué tipo de siniestro explica el gasto"),
        Recomendacion("Reserva pendiente por producto", "monto_reserva", "producto", "Dónde está el costo que aún falta pagar"),
        Recomendacion("Siniestros por producto", "cantidad_siniestros", "producto", "Qué línea de negocio genera más casos"),
        Recomendacion("Monto recuperado por mes", "monto_recuperado", MES, "Cuánto vuelve por deducibles y terceros"),
    ),
    "FIN": (
        Recomendacion("Prima directa neta por mes comparada con el año anterior", "prima_total", MES, "¿Crecen los ingresos frente al año pasado?"),
        Recomendacion("Prima directa neta por producto", "prima_total", "producto", "Qué productos aportan más ingresos"),
        Recomendacion("Emisiones y anulaciones en torta", "cantidad_movimientos", "tipo_movimiento", "Qué parte de los movimientos son anulaciones"),
        Recomendacion("Prima cedida por producto", "prima_cedida", "producto", "Cuánto riesgo se traspasa a reaseguradoras"),
        Recomendacion("Comisiones por producto", "comision_total", "producto", "Cuánto cuesta vender cada producto"),
        Recomendacion("Prima retenida neta por región", "prima_retenida", "region", "Lo que queda en la compañía en cada región"),
    ),
    "SEG": (
        Recomendacion("Pólizas emitidas por mes comparado con el año anterior", "cantidad_polizas", MES, "¿Se vende más o menos que hace un año?"),
        Recomendacion("Pólizas emitidas por región en mapa", "cantidad_polizas", "region", "Dónde se vende más"),
        Recomendacion("Monto asegurado por producto", "monto_asegurado", "producto", "Dónde se concentra la exposición"),
        Recomendacion("Ítems asegurados por segmento en torta", "cantidad_items", "segmento", "A qué tipo de cliente se vende"),
    ),
    "CUO": (
        Recomendacion("Morosidad por producto", "monto_cuotas_vencidas", "producto", "Dónde se concentran las cuotas vencidas sin pagar"),
        Recomendacion("Monto de cuotas por estado en torta", "monto_cuotas", "estado_cuota", "Qué parte está pagada, pendiente o vencida"),
        Recomendacion("Morosidad por región en mapa", "monto_cuotas_vencidas", "region", "Dónde está la deuda atrasada"),
        Recomendacion("Cobranza por mes", "monto_cuotas_pagadas", MES, "Cuánto se cobra cada mes"),
    ),
}


@dataclass(frozen=True)
class GraficoPaquete:
    titulo: str
    metrica: str
    agrupar_por: str
    tipo: str
    lectura: str             # la pregunta de negocio que responde
    tendencia: bool = False  # True: los 12 meses que terminan en el período, para dar contexto
    comparar: str = ""


@dataclass(frozen=True)
class Paquete:
    nombre: str
    para_que: str
    graficos: tuple[GraficoPaquete, ...]


# Dashboards completos de un área para un período ("dashboard de siniestros de abril").
# Siguen el orden en que se lee un informe: primero las cifras clave contra el período
# anterior, luego la tendencia del último año para dar contexto, y al final dónde y en
# qué se concentra. Lo arma el backend sin IA: siempre sale igual de completo.
PAQUETES: dict[str, Paquete] = {
    "SIN": Paquete("Resumen de siniestros", "Cuántos casos llegaron, cuánto se pagó, la tendencia del último año, "
                   "y dónde y en qué tipo de siniestro se concentra el gasto.", (
        GraficoPaquete("Siniestros del período", "cantidad_siniestros", NINGUNO, "kpi",
                       "¿Llegaron más o menos casos que en el período anterior?", comparar="periodo_anterior"),
        GraficoPaquete("Monto pagado del período", "monto_pagado", NINGUNO, "kpi",
                       "¿Cuánto se pagó y cómo se compara con el período anterior?", comparar="periodo_anterior"),
        GraficoPaquete("Siniestros por mes · últimos 12 meses", "cantidad_siniestros", MES, "grafico_lineas",
                       "¿El período es normal o se sale de la tendencia del último año?", tendencia=True),
        GraficoPaquete("Monto pagado por región", "monto_pagado", "region", "grafico_mapa",
                       "¿En qué regiones se concentra el gasto?"),
        GraficoPaquete("Monto pagado por tipo de siniestro", "monto_pagado", "tipo_siniestro", "grafico_barras",
                       "¿Qué tipo de siniestro explica la mayor parte del gasto?"),
        GraficoPaquete("Siniestros por producto", "cantidad_siniestros", "producto", "grafico_barras",
                       "¿Qué línea de negocio genera más casos?"),
    )),
    "FIN": Paquete("Resumen de primas", "Cuánto ingresó por primas y comisiones, la tendencia del último año y qué "
                   "productos y regiones aportan más.", (
        GraficoPaquete("Prima directa neta del período", "prima_total", NINGUNO, "kpi",
                       "¿Cuánto ingresó por primas, ya descontadas las anulaciones?", comparar="periodo_anterior"),
        GraficoPaquete("Comisiones del período", "comision_total", NINGUNO, "kpi",
                       "¿Cuánto costó la intermediación?", comparar="periodo_anterior"),
        GraficoPaquete("Prima directa neta por mes · últimos 12 meses", "prima_total", MES, "grafico_lineas",
                       "¿El período es normal o se sale de la tendencia del último año?", tendencia=True),
        GraficoPaquete("Prima directa neta por producto", "prima_total", "producto", "grafico_barras",
                       "¿Qué productos aportan más ingresos?"),
        GraficoPaquete("Prima retenida neta por región", "prima_retenida", "region", "grafico_barras",
                       "¿Cuánto queda en la compañía, tras el reaseguro, en cada región?"),
        GraficoPaquete("Movimientos de prima por tipo", "cantidad_movimientos", "tipo_movimiento", "grafico_torta",
                       "¿Cuántas emisiones y cuántas anulaciones hubo?"),
    )),
    "SEG": Paquete("Cartera de pólizas", "Cuántas pólizas se emitieron, cuánta exposición entró, la tendencia del "
                   "último año y cómo se reparte la cartera.", (
        GraficoPaquete("Pólizas emitidas en el período", "cantidad_polizas", NINGUNO, "kpi",
                       "¿Se emitieron más o menos pólizas que en el período anterior?", comparar="periodo_anterior"),
        GraficoPaquete("Monto asegurado emitido", "monto_asegurado", NINGUNO, "kpi",
                       "¿Cuánta exposición nueva entró a la cartera?", comparar="periodo_anterior"),
        GraficoPaquete("Pólizas emitidas por mes · últimos 12 meses", "cantidad_polizas", MES, "grafico_lineas",
                       "¿El ritmo de ventas es normal o se sale de la tendencia?", tendencia=True),
        GraficoPaquete("Monto asegurado por producto", "monto_asegurado", "producto", "grafico_barras",
                       "¿En qué productos se concentra la exposición?"),
        GraficoPaquete("Pólizas emitidas por región", "cantidad_polizas", "region", "grafico_barras",
                       "¿Dónde se vende más?"),
        GraficoPaquete("Ítems asegurados por segmento", "cantidad_items", "segmento", "grafico_torta",
                       "¿A qué segmento de clientes se vende?"),
    )),
    "CUO": Paquete("Cobranza de cuotas", "Lo vencido sin pagar, lo cobrado, cómo se reparten las cuotas por estado "
                   "y dónde está la morosidad.", (
        GraficoPaquete("Cuotas vencidas sin pagar", "monto_cuotas_vencidas", NINGUNO, "kpi",
                       "¿Cuánta morosidad hay en las cuotas que vencían en el período?"),
        GraficoPaquete("Cuotas pagadas", "monto_cuotas_pagadas", NINGUNO, "kpi",
                       "¿Cuánto se cobró de lo que vencía en el período?", comparar="periodo_anterior"),
        GraficoPaquete("Cuotas por estado", "monto_cuotas", "estado_cuota", "grafico_torta",
                       "¿Qué parte está pagada, pendiente o vencida?"),
        GraficoPaquete("Cuotas vencidas por producto", "monto_cuotas_vencidas", "producto", "grafico_barras",
                       "¿En qué productos se concentra la morosidad?"),
        GraficoPaquete("Cuotas pagadas por mes · últimos 12 meses", "monto_cuotas_pagadas", MES, "grafico_lineas",
                       "¿La cobranza viene mejor o peor que en el último año?", tendencia=True),
    )),
}


def graficos_paquete(dominio: "DominioDisponible", cod: str) -> list[GraficoPaquete]:
    """Los gráficos del dashboard del área que el catálogo actual permite armar."""
    paquete = PAQUETES.get(cod)
    if not paquete:
        return []
    return [g for g in paquete.graficos if g.metrica in dominio.medidas and g.agrupar_por in dominio.dimensiones()]


# Series que conviene proyectar (módulo "Proyecciones"), con la decisión que apoyan.
# Las demás métricas proyectables también se ofrecen, sin recomendación.
PROYECCIONES: dict[str, dict[str, str]] = {
    "SIN": {
        "cantidad_siniestros": "Cuántos casos van a llegar: sirve para planificar liquidadores y reservas.",
        "monto_denunciado": "Cuánto se va a reclamar: anticipa el costo que viene.",
    },
    "FIN": {
        "prima_total": "Cuánto va a ingresar por primas: la base del presupuesto de ingresos.",
        "prima_retenida": "Cuánto de esa prima se queda en la compañía después del reaseguro.",
    },
    "SEG": {
        "cantidad_polizas": "Cuántas pólizas se van a vender: el ritmo comercial.",
        "monto_asegurado": "Cuánta exposición nueva va a entrar a la cartera.",
    },
}


def proyectable(dominio: "DominioDisponible", clave: str) -> bool:
    """Misma regla que analisis.proyectar: serie mensual de un flujo, sin advertencias."""
    medida = dominio.medidas.get(clave)
    return bool(medida and dominio.con_fecha and dominio.rango_meses and medida.comparable == "si"
                and not dominio.definicion.sin_proyeccion)


# Datos personales que nunca se exponen, existan o no en la BD (RN-06 / RF-03)
CAMPOS_SENSIBLES = ["rut", "correo", "email", "telefono", "tarjeta", "nombre del cliente", "direccion"]

_DURACION_CACHE = 300  # segundos


def sql_columna(col: Columna) -> str:
    """ods.TABLA.COLUMNA: las tablas se referencian con su nombre, sin alias."""
    return f"ods.{col[0]}.{col[1]}"


@dataclass
class DominioDisponible:
    """La parte de una DefinicionDominio que los metadatos dejan usar."""
    definicion: DefinicionDominio
    medidas: dict[str, Medida]
    atributos: dict[str, Atributo]
    detalle: tuple[Atributo, ...]
    usa_union: bool
    con_fecha: bool
    valores: dict[str, list[str]] = field(default_factory=dict)  # atributo -> valores posibles
    rango_meses: tuple[str, str] | None = None
    registros_por_mes: dict[str, int] = field(default_factory=dict)  # AAAA-MM -> cantidad de registros

    def mes_recomendado(self, ultimo_completo: str) -> str:
        """Mes que se propone para su dashboard: el último ya terminado con un volumen normal
        (al menos la mitad del mes típico). Si los últimos meses casi no tienen registros
        (carga incompleta), un dashboard de ellos se calcularía sobre 1 o 2 filas."""
        conteos = {m: n for m, n in self.registros_por_mes.items() if m <= ultimo_completo}
        if not conteos:
            return ultimo_completo
        tipico = sorted(conteos.values())[len(conteos) // 2]
        normales = [m for m, n in conteos.items() if n >= tipico / 2]
        return max(normales) if normales else ultimo_completo

    def dimensiones(self) -> list[str]:
        return [NINGUNO, *self.atributos, *([MES] if self.con_fecha else [])]

    def sql_from(self) -> str:
        d = self.definicion
        sql = f"ods.{d.tabla}"
        if self.usa_union:
            for u in d.uniones:
                sql += f" JOIN ods.{u.tabla} ON ods.{u.tabla}.{u.columna_destino} = ods.{u.origen or d.tabla}.{u.columna_origen}"
        return sql

    def sql_dimension(self, clave: str) -> str | None:
        if clave == NINGUNO:
            return None
        if clave == MES:
            return f"CONVERT(CHAR(7), {sql_columna(self.definicion.fecha.columna)}, 120)"
        return sql_columna(self.atributos[clave].columna)

    def sql_medida(self, clave: str) -> str:
        return self.medidas[clave].sql.format(SIN=f"ods.{SIN}", FIN=f"ods.{FIN}", SEG=f"ods.{SEG}", CUOTA=f"ods.{CUOTA}")

    def etiqueta_dimension(self, clave: str) -> str:
        if clave == NINGUNO:
            return "Sin agrupar"
        if clave == MES:
            return "Mes"
        return self.atributos[clave].etiqueta


@dataclass
class Catalogo:
    dominios: dict[str, str]                       # COD_DOMINIO -> descripción
    disponibles: dict[str, DominioDisponible]      # solo dominios con datos habilitados

    def descripcion_para_ia(self, dominios_usuario: set[str]) -> str:
        """Resumen que va en el system prompt. Solo incluye el detalle de los
        dominios que el usuario puede consultar."""
        lineas = ["Dominios de negocio:"]
        lineas += [f"- {cod}: {desc}" for cod, desc in self.dominios.items()]

        visibles = [cod for cod in self.disponibles if cod in dominios_usuario]
        if not visibles:
            lineas.append("\nEl usuario no tiene dominios con datos disponibles para consultar.")
        for cod in visibles:
            d = self.disponibles[cod]
            lineas.append(f"\nDominio {cod} ({self.dominios[cod]}), {VERSION}:")
            lineas.append("Métricas: " + "; ".join(f"{k} ({m.etiqueta})" for k, m in d.medidas.items()))
            lineas.append("Agrupaciones: " + "; ".join(f"{k} ({d.etiqueta_dimension(k)})" for k in d.dimensiones()))
            for clave, valores in d.valores.items():
                lineas.append(f"Valores de {clave}: {', '.join(valores)}")
            if d.rango_meses:
                lineas.append(
                    f"Fechas ({d.definicion.fecha.etiqueta.lower()}): formato AAAA-MM, "
                    f"hay datos entre {d.rango_meses[0]} y {d.rango_meses[1]}."
                )
        lineas.append(f"\nCampos NO autorizados (datos personales): {', '.join(CAMPOS_SENSIBLES)}")
        return "\n".join(lineas)


def _cargar_dominio(definicion: DefinicionDominio, columnas: dict[str, set[str]],
                    relaciones: set[tuple]) -> DominioDisponible | None:
    # O se pueden usar todas las uniones o ninguna: una cadena a medias no sirve
    usa_union = bool(definicion.uniones) and all(
        u.tabla in columnas and (u.origen or definicion.tabla, u.columna_origen, u.tabla, u.columna_destino) in relaciones
        for u in definicion.uniones
    )
    unidas = {u.tabla for u in definicion.uniones} if usa_union else set()

    def habilitada(col: Columna) -> bool:
        tabla, nombre = col
        if tabla != definicion.tabla and tabla not in unidas:
            return False
        return nombre in columnas.get(tabla, set())

    medidas = {k: m for k, m in definicion.medidas.items() if all(habilitada(c) for c in m.columnas)}
    if not medidas:
        return None
    dominio = DominioDisponible(
        definicion=definicion,
        medidas=medidas,
        atributos={k: a for k, a in definicion.atributos.items() if habilitada(a.columna)},
        detalle=tuple(a for a in definicion.detalle if habilitada(a.columna)),
        usa_union=usa_union,
        con_fecha=habilitada(definicion.fecha.columna),
    )
    origen = dominio.sql_from()
    dominio.valores = {
        clave: db.valores_distintos(origen, sql_columna(a.columna)) for clave, a in dominio.atributos.items()
    }
    if dominio.con_fecha:
        dominio.rango_meses = db.rango_meses(origen, sql_columna(definicion.fecha.columna))
        dominio.registros_por_mes = db.registros_por_mes(origen, sql_columna(definicion.fecha.columna))
    return dominio


def _cargar() -> Catalogo:
    tablas = db.tablas_disponibles()  # {tabla: cod_dominio}, solo schema ods
    columnas = {tabla: set(db.columnas_disponibles("ods", tabla)) for tabla in tablas}
    relaciones = db.relaciones_disponibles()
    disponibles = {}
    for cod, definicion in DEFINICIONES.items():
        if tablas.get(definicion.tabla) != (definicion.permiso or cod):
            continue  # la tabla no está habilitada en meta.MET_TABLA para este dominio
        dominio = _cargar_dominio(definicion, columnas, relaciones)
        if dominio:
            disponibles[cod] = dominio
    areas = {cod: nombre for cod, nombre in AREAS_PROPIAS.items() if cod in disponibles}
    return Catalogo(dominios={**db.dominios(), **areas}, disponibles=disponibles)


def ampliar_permisos(dominios_usuario: set[str]) -> set[str]:
    """Suma las áreas que dependen de un dominio que el usuario ya puede consultar."""
    return dominios_usuario | {cod for cod, d in DEFINICIONES.items() if d.permiso in dominios_usuario}


_cache: tuple[float, Catalogo] | None = None


def obtener() -> Catalogo:
    """Catálogo vigente. Se recarga cada pocos minutos, así un cambio en meta.*
    se refleja sin reiniciar el backend."""
    global _cache
    if _cache is None or time.monotonic() - _cache[0] > _DURACION_CACHE:
        try:
            nuevo = _cargar()
        except pyodbc.Error:
            if _cache is None:
                raise
            # Si la BD falla al recargar, se sigue con el catálogo anterior y se
            # reintenta en un minuto, en vez de botar todas las consultas
            print("[catalogo] no se pudo recargar; se usa el anterior", flush=True)
            _cache = (time.monotonic() - _DURACION_CACHE + 60, _cache[1])
            return _cache[1]
        # La hora se toma al terminar: con una BD lenta, la carga podía durar más que
        # el propio caché y el catálogo nacía vencido
        _cache = (time.monotonic(), nuevo)
    return _cache[1]
