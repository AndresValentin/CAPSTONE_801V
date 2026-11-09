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

from . import db

VERSION = "catalogo-v0.8"

Columna = tuple[str, str]  # (tabla, columna) tal como aparecen en meta.MET_COLUMNA


@dataclass(frozen=True)
class Medida:
    etiqueta: str
    sql: str
    columnas: tuple[Columna, ...] = ()
    moneda: bool = False


@dataclass(frozen=True)
class Atributo:
    etiqueta: str
    columna: Columna
    moneda: bool = False  # solo para columnas de detalle con montos


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


def _medida_cuota(etiqueta: str, condicion: str) -> Medida:
    return Medida(
        etiqueta,
        f"SUM(CASE WHEN {condicion} THEN {{CUOTA}}.MNT_CUOTA ELSE 0 END)",
        ((CUOTA, "MNT_CUOTA"), (CUOTA, "DESC_ESTADO_CUOTA"), (CUOTA, "DT_FECHA_VENCIMIENTO")),
        True,
    )


DEFINICIONES: dict[str, DefinicionDominio] = {
    "SIN": DefinicionDominio(
        tabla=SIN,
        uniones=(Union(SEG, "ID_ITEM", "ID_ITEM"),),
        fecha=Atributo("Fecha de ocurrencia", (SIN, "DT_FECHA_OCURRENCIA")),
        medidas={
            "cantidad_siniestros": Medida("Cantidad de siniestros", "COUNT(*)"),
            "monto_pagado": Medida("Monto pagado", "SUM({SIN}.MNT_PAGADO)", ((SIN, "MNT_PAGADO"),), True),
            "monto_pagado_promedio": Medida("Monto pagado promedio", "AVG({SIN}.MNT_PAGADO)", ((SIN, "MNT_PAGADO"),), True),
            "monto_denunciado": Medida("Monto denunciado", "SUM({SIN}.MNT_DENUNCIADO)", ((SIN, "MNT_DENUNCIADO"),), True),
            "monto_reserva": Medida("Monto en reserva", "SUM({SIN}.MNT_RESERVA)", ((SIN, "MNT_RESERVA"),), True),
            "monto_recuperado": Medida("Monto recuperado", "SUM({SIN}.MNT_RECUPERADO)", ((SIN, "MNT_RECUPERADO"),), True),
        },
        atributos={
            "tipo_siniestro": Atributo("Tipo de siniestro", (SIN, "DESC_TIPO_SINIESTRO")),
            "estado_siniestro": Atributo("Estado del siniestro", (SIN, "DESC_ESTADO_SINIESTRO")),
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
            "cantidad_items": Medida("Cantidad de ítems asegurados", "COUNT(*)"),
            "cantidad_polizas": Medida("Cantidad de pólizas", "COUNT(DISTINCT {SEG}.COD_POLIZA)", ((SEG, "COD_POLIZA"),)),
            "monto_asegurado": Medida("Monto asegurado", "SUM({SEG}.MNT_MONTO_ASEGURADO)", ((SEG, "MNT_MONTO_ASEGURADO"),), True),
        },
        atributos={
            "producto": _PRODUCTO,
            "region": _REGION,
            "estado_poliza": Atributo("Estado de la póliza", (SEG, "DESC_ESTADO_POLIZA")),
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
        uniones=(
            Union(FIN, "ID_MOVIMIENTO_PRIMA", "ID_MOVIMIENTO_PRIMA"),
            Union(SEG, "ID_ITEM", "ID_ITEM", origen=FIN),
        ),
        fecha=Atributo("Fecha de vencimiento", (CUOTA, "DT_FECHA_VENCIMIENTO")),
        medidas={
            "monto_cuotas": Medida("Monto total de cuotas", "SUM({CUOTA}.MNT_CUOTA)", ((CUOTA, "MNT_CUOTA"),), True),
            "monto_cuotas_pagadas": _medida_cuota("Monto de cuotas pagadas", "{CUOTA}.DESC_ESTADO_CUOTA = 'PAGADA'"),
            "monto_cuotas_pendientes": _medida_cuota("Monto de cuotas pendientes", "{CUOTA}.DESC_ESTADO_CUOTA = 'PENDIENTE'"),
            "monto_cuotas_vencidas": _medida_cuota(
                "Monto de cuotas vencidas sin pagar",
                "{CUOTA}.DESC_ESTADO_CUOTA = 'PENDIENTE' AND {CUOTA}.DT_FECHA_VENCIMIENTO < CAST(GETDATE() AS DATE)",
            ),
            "cantidad_cuotas": Medida("Cantidad de cuotas", "COUNT(*)"),
        },
        atributos={
            "estado_cuota": Atributo("Estado de la cuota", (CUOTA, "DESC_ESTADO_CUOTA")),
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


# Gráficos sugeridos en el chat, del más útil al menos útil. El tipo sigue lo que
# hay que leer: líneas para tendencias, barras para comparar categorías (con muchas
# se leen mejor que una torta) y torta solo para repartos de pocas partes.
RECOMENDACIONES: dict[str, tuple[Recomendacion, ...]] = {
    "SIN": (
        Recomendacion("Monto pagado por tipo de siniestro en barras", "monto_pagado", "tipo_siniestro", "Muestra qué tipo concentra el gasto"),
        Recomendacion("Monto pagado por región en mapa de Chile", "monto_pagado", "region", "Muestra en el mapa dónde se concentra lo pagado"),
        Recomendacion("Cantidad de siniestros por mes en líneas", "cantidad_siniestros", MES, "Muestra la tendencia y los meses con más casos"),
        Recomendacion("Monto en reserva por región en barras", "monto_reserva", "region", "Compara dónde está el costo aún por pagar"),
        Recomendacion("Monto pagado por producto en barras", "monto_pagado", "producto", "Compara el gasto entre líneas de negocio"),
        Recomendacion("Monto recuperado por mes en líneas", "monto_recuperado", MES, "Muestra cómo evolucionan los recuperos"),
        Recomendacion("Cantidad de siniestros por estado en torta", "cantidad_siniestros", "estado_siniestro", "Reparte los casos abiertos y cerrados"),
    ),
    "FIN": (
        Recomendacion("Prima directa neta por mes en líneas", "prima_total", MES, "Muestra la tendencia de ingresos, ya descontadas las anulaciones"),
        Recomendacion("Prima directa neta por producto en barras", "prima_total", "producto", "Compara el aporte de cada línea de negocio"),
        Recomendacion("Prima retenida neta por región en barras", "prima_retenida", "region", "Compara lo que queda en la compañía tras ceder riesgo"),
        Recomendacion("Prima cedida neta por producto en barras", "prima_cedida", "producto", "Muestra qué productos ceden más riesgo"),
        Recomendacion("Comisión total por producto en barras", "comision_total", "producto", "Compara el costo de intermediación"),
        Recomendacion("Cantidad de movimientos por tipo en torta", "cantidad_movimientos", "tipo_movimiento", "Reparte emisiones y anulaciones"),
    ),
    "SEG": (
        Recomendacion("Monto asegurado por producto en barras", "monto_asegurado", "producto", "Muestra dónde se concentra la exposición"),
        Recomendacion("Cantidad de ítems por mes de emisión en líneas", "cantidad_items", MES, "Muestra la tendencia de ventas"),
        Recomendacion("Cantidad de pólizas por región en barras", "cantidad_polizas", "region", "Compara la cartera por territorio"),
        Recomendacion("Monto asegurado por región en barras", "monto_asegurado", "region", "Compara la exposición por territorio"),
        Recomendacion("Cantidad de ítems por segmento en torta", "cantidad_items", "segmento", "Reparte la cartera entre pocos segmentos"),
    ),
    "CUO": (
        Recomendacion("Monto de cuotas por estado en torta", "monto_cuotas", "estado_cuota", "Reparte lo pagado y lo pendiente"),
        Recomendacion("Monto de cuotas pendientes por mes de vencimiento en líneas", "monto_cuotas_pendientes", MES, "Muestra cuándo se concentra lo que falta cobrar"),
        Recomendacion("Monto de cuotas vencidas sin pagar por producto en barras", "monto_cuotas_vencidas", "producto", "Compara dónde está la morosidad"),
        Recomendacion("Monto de cuotas vencidas sin pagar por región en barras", "monto_cuotas_vencidas", "region", "Compara la morosidad por territorio"),
        Recomendacion("Monto de cuotas pagadas por mes de vencimiento en líneas", "monto_cuotas_pagadas", MES, "Muestra la tendencia de la cobranza"),
    ),
}

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
        _cache = (time.monotonic(), _cargar())
    return _cache[1]
