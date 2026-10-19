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

VERSION = "catalogo-v0.5"

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


@dataclass(frozen=True)
class DefinicionDominio:
    tabla: str                       # tabla de hechos (schema ods)
    union: Union | None
    fecha: Atributo                  # columna para "por mes" y para desde/hasta
    medidas: dict[str, Medida]
    atributos: dict[str, Atributo]   # sirven para agrupar y para filtrar
    detalle: tuple[Atributo, ...]    # columnas de la tabla de detalle del reporte


SIN, FIN, SEG = "ODS_SIN_SINIESTRO", "ODS_FIN_PRIMA", "ODS_SEG_SEGURO"
CLIENTE = "ODS_SEG_CLIENTE"

# Atributos de la póliza, compartidos por los dominios que se unen a ODS_SEG_SEGURO
_PRODUCTO = Atributo("Producto", (SEG, "DESC_PRODUCTO"))
_REGION = Atributo("Región", (SEG, "DESC_REGION"))
_POLIZA = Atributo("Póliza", (SEG, "COD_POLIZA"))

DEFINICIONES: dict[str, DefinicionDominio] = {
    "SIN": DefinicionDominio(
        tabla=SIN,
        union=Union(SEG, "ID_ITEM", "ID_ITEM"),
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
            Atributo("Pagado", (SIN, "MNT_PAGADO"), True),
        ),
    ),
    "FIN": DefinicionDominio(
        tabla=FIN,
        union=Union(SEG, "ID_ITEM", "ID_ITEM"),
        fecha=Atributo("Fecha del movimiento", (FIN, "DT_FECHA_MOVIMIENTO")),
        medidas={
            "prima_total": Medida("Prima total", "SUM({FIN}.MNT_PRIMA)", ((FIN, "MNT_PRIMA"),), True),
            "comision_total": Medida("Comisión total", "SUM({FIN}.MNT_COMISION)", ((FIN, "MNT_COMISION"),), True),
            "cantidad_movimientos": Medida("Cantidad de movimientos de prima", "COUNT(*)"),
        },
        atributos={
            "tipo_movimiento": Atributo("Tipo de movimiento", (FIN, "DESC_TIPO_MOVIMIENTO")),
            "estado_pago": Atributo("Estado de pago", (FIN, "DESC_ESTADO_PAGO")),
            "producto": _PRODUCTO,
            "region": _REGION,
        },
        detalle=(
            _POLIZA,
            Atributo("Movimiento", (FIN, "NRO_MOVIMIENTO")),
            Atributo("Fecha", (FIN, "DT_FECHA_MOVIMIENTO")),
            Atributo("Tipo", (FIN, "DESC_TIPO_MOVIMIENTO")),
            Atributo("Estado de pago", (FIN, "DESC_ESTADO_PAGO")),
            _PRODUCTO,
            Atributo("Prima", (FIN, "MNT_PRIMA"), True),
            Atributo("Comisión", (FIN, "MNT_COMISION"), True),
        ),
    ),
    "SEG": DefinicionDominio(
        tabla=SEG,
        union=Union(CLIENTE, "ID_CLIENTE", "ID_CLIENTE"),
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
            Atributo("Fin de vigencia", (SEG, "DT_FECHA_FIN_VIGENCIA")),
            Atributo("Estado", (SEG, "DESC_ESTADO_POLIZA")),
            Atributo("Monto asegurado", (SEG, "MNT_MONTO_ASEGURADO"), True),
        ),
    ),
}

MES = "mes"
NINGUNO = "ninguno"
TIPOS_SALIDA = ["kpi", "grafico_barras", "grafico_lineas", "grafico_torta", "tabla"]

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
            u = d.union
            sql += f" JOIN ods.{u.tabla} ON ods.{u.tabla}.{u.columna_destino} = ods.{d.tabla}.{u.columna_origen}"
        return sql

    def sql_dimension(self, clave: str) -> str | None:
        if clave == NINGUNO:
            return None
        if clave == MES:
            return f"CONVERT(CHAR(7), {sql_columna(self.definicion.fecha.columna)}, 120)"
        return sql_columna(self.atributos[clave].columna)

    def sql_medida(self, clave: str) -> str:
        return self.medidas[clave].sql.format(SIN=f"ods.{SIN}", FIN=f"ods.{FIN}", SEG=f"ods.{SEG}")

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
    u = definicion.union
    usa_union = bool(u) and u.tabla in columnas and (definicion.tabla, u.columna_origen, u.tabla, u.columna_destino) in relaciones

    def habilitada(col: Columna) -> bool:
        tabla, nombre = col
        if tabla != definicion.tabla and not (usa_union and tabla == u.tabla):
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
        if tablas.get(definicion.tabla) != cod:
            continue  # la tabla no está habilitada en meta.MET_TABLA para este dominio
        dominio = _cargar_dominio(definicion, columnas, relaciones)
        if dominio:
            disponibles[cod] = dominio
    return Catalogo(dominios=db.dominios(), disponibles=disponibles)


_cache: tuple[float, Catalogo] | None = None


def obtener() -> Catalogo:
    """Catálogo vigente. Se recarga cada pocos minutos, así un cambio en meta.*
    se refleja sin reiniciar el backend."""
    global _cache
    if _cache is None or time.monotonic() - _cache[0] > _DURACION_CACHE:
        _cache = (time.monotonic(), _cargar())
    return _cache[1]
