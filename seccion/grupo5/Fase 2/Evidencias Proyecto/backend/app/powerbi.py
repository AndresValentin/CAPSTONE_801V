"""Exportación de los gráficos pedidos en el chat a un proyecto de Power BI (.pbip) en un .zip.

Se genera solo cuando el usuario lo pide y contiene únicamente esos gráficos. Trae
el modelo (tablas, relaciones y medidas DAX) y las páginas, pero no datos ni
credenciales: Power BI lee directamente de SQL Server con la cuenta de quien lo abre.
"""

import io
import json
import uuid
import zipfile
from dataclasses import dataclass, field

from . import catalogo, db
from .ia import PlanConsulta

NOMBRE = "BI_Copilot"
ESQUEMAS = "https://developer.microsoft.com/json-schemas/fabric/item"
TEMA = "BICopilot"
MONEDA = '"$"#,0'
ENTERO = "#,0"
ANULACION = 'IF(Prima[Tipo de movimiento] = "ANULACION", -Prima[{c}], Prima[{c}])'


@dataclass(frozen=True)
class ColumnaPbi:
    nombre: str
    fuente: str
    tipo: str = "string"  # string | int64 | double | dateTime
    oculta: bool = False
    solo_dominio: str | None = None  # si es dato propio de otro dominio


@dataclass(frozen=True)
class MedidaPbi:
    nombre: str
    dax: str
    formato: str = MONEDA


@dataclass(frozen=True)
class TablaPbi:
    fuente: str
    columnas: tuple[ColumnaPbi, ...]
    meses: tuple[tuple[str, str], ...] = ()  # (columna nueva AAAA-MM, columna de fecha)
    medidas: tuple[MedidaPbi, ...] = ()
    medidas_solo_dominio: str | None = None


TABLAS: dict[str, TablaPbi] = {
    "Seguro": TablaPbi(
        "ODS_SEG_SEGURO",
        (
            ColumnaPbi("ID_ITEM", "ID_ITEM", "int64", True),
            ColumnaPbi("ID_CLIENTE", "ID_CLIENTE", "int64", True, "SEG"),
            ColumnaPbi("Producto", "DESC_PRODUCTO"),
            ColumnaPbi("Región", "DESC_REGION"),
            ColumnaPbi("Póliza", "COD_POLIZA", solo_dominio="SEG"),
            ColumnaPbi("Estado de la póliza", "DESC_ESTADO_POLIZA", solo_dominio="SEG"),
            ColumnaPbi("Fecha de emisión", "DT_FECHA_EMISION", "dateTime", solo_dominio="SEG"),
            ColumnaPbi("Monto asegurado ítem", "MNT_MONTO_ASEGURADO", "double", solo_dominio="SEG"),
        ),
        meses=(("Mes de emisión", "DT_FECHA_EMISION"),),
        medidas=(
            MedidaPbi("Ítems asegurados", "COUNTROWS(Seguro)", ENTERO),
            MedidaPbi("Pólizas", "DISTINCTCOUNT(Seguro[Póliza])", ENTERO),
            MedidaPbi("Monto asegurado", "SUM(Seguro[Monto asegurado ítem])"),
        ),
        medidas_solo_dominio="SEG",
    ),
    "Cliente": TablaPbi(
        "ODS_SEG_CLIENTE",
        (
            ColumnaPbi("ID_CLIENTE", "ID_CLIENTE", "int64", True),
            ColumnaPbi("Tipo de cliente", "DESC_TIPO_CLIENTE"),
            ColumnaPbi("Segmento", "DESC_SEGMENTO"),
        ),
    ),
    "Siniestro": TablaPbi(
        "ODS_SIN_SINIESTRO",
        (
            ColumnaPbi("ID_ITEM", "ID_ITEM", "int64", True),
            ColumnaPbi("Código de siniestro", "COD_SINIESTRO"),
            ColumnaPbi("Fecha de ocurrencia", "DT_FECHA_OCURRENCIA", "dateTime"),
            ColumnaPbi("Tipo de siniestro", "DESC_TIPO_SINIESTRO"),
            ColumnaPbi("Estado del siniestro", "DESC_ESTADO_SINIESTRO"),
            ColumnaPbi("Denunciado", "MNT_DENUNCIADO", "double"),
            ColumnaPbi("Reserva", "MNT_RESERVA", "double"),
            ColumnaPbi("Pagado", "MNT_PAGADO", "double"),
            ColumnaPbi("Recuperado", "MNT_RECUPERADO", "double"),
        ),
        meses=(("Mes", "DT_FECHA_OCURRENCIA"),),
        medidas=(
            MedidaPbi("Siniestros", "COUNTROWS(Siniestro)", ENTERO),
            MedidaPbi("Monto pagado", "SUM(Siniestro[Pagado])"),
            MedidaPbi("Monto pagado promedio", "AVERAGE(Siniestro[Pagado])"),
            MedidaPbi("Monto denunciado", "SUM(Siniestro[Denunciado])"),
            MedidaPbi("Monto en reserva", "SUM(Siniestro[Reserva])"),
            MedidaPbi("Monto recuperado", "SUM(Siniestro[Recuperado])"),
        ),
    ),
    "Prima": TablaPbi(
        "ODS_FIN_PRIMA",
        (
            ColumnaPbi("ID_MOVIMIENTO_PRIMA", "ID_MOVIMIENTO_PRIMA", "int64", True),
            ColumnaPbi("ID_ITEM", "ID_ITEM", "int64", True),
            ColumnaPbi("Código de movimiento", "COD_MOVIMIENTO_PRIMA"),
            ColumnaPbi("Fecha del movimiento", "DT_FECHA_MOVIMIENTO", "dateTime"),
            ColumnaPbi("Tipo de movimiento", "DESC_TIPO_MOVIMIENTO"),
            ColumnaPbi("Cantidad de cuotas", "Q_CUOTAS", "int64"),
            ColumnaPbi("Prima directa", "MNT_PRIMA_DIRECTA", "double"),
            ColumnaPbi("Prima cedida", "MNT_PRIMA_CEDIDA", "double"),
            ColumnaPbi("Prima retenida", "MNT_PRIMA_RETENIDA", "double"),
            ColumnaPbi("Comisión", "MNT_COMISION", "double"),
        ),
        meses=(("Mes", "DT_FECHA_MOVIMIENTO"),),
        medidas=(
            MedidaPbi("Prima directa neta", "SUMX(Prima, " + ANULACION.format(c="Prima directa") + ")"),
            MedidaPbi("Prima cedida neta", "SUMX(Prima, " + ANULACION.format(c="Prima cedida") + ")"),
            MedidaPbi("Prima retenida neta", "SUMX(Prima, " + ANULACION.format(c="Prima retenida") + ")"),
            MedidaPbi("Comisión total", "SUM(Prima[Comisión])"),
            MedidaPbi("Movimientos de prima", "COUNTROWS(Prima)", ENTERO),
        ),
    ),
    "Cuota": TablaPbi(
        "ODS_FIN_CUOTA_PRIMA",
        (
            ColumnaPbi("ID_MOVIMIENTO_PRIMA", "ID_MOVIMIENTO_PRIMA", "int64", True),
            ColumnaPbi("Número de cuota", "NRO_CUOTA", "int64"),
            ColumnaPbi("Fecha de vencimiento", "DT_FECHA_VENCIMIENTO", "dateTime"),
            ColumnaPbi("Estado de la cuota", "DESC_ESTADO_CUOTA"),
            ColumnaPbi("Monto cuota", "MNT_CUOTA", "double"),
        ),
        meses=(("Mes de vencimiento", "DT_FECHA_VENCIMIENTO"),),
        medidas=(
            MedidaPbi("Monto total de cuotas", "SUM(Cuota[Monto cuota])"),
            MedidaPbi("Monto de cuotas pagadas",
                      'CALCULATE(SUM(Cuota[Monto cuota]), Cuota[Estado de la cuota] = "PAGADA")'),
            MedidaPbi("Monto de cuotas pendientes",
                      'CALCULATE(SUM(Cuota[Monto cuota]), Cuota[Estado de la cuota] = "PENDIENTE")'),
            MedidaPbi("Monto de cuotas vencidas",
                      'CALCULATE(SUM(Cuota[Monto cuota]), Cuota[Estado de la cuota] = "PENDIENTE", '
                      "Cuota[Fecha de vencimiento] < TODAY())"),
            MedidaPbi("Total de cuotas", "COUNTROWS(Cuota)", ENTERO),
        ),
    ),
}

# (tabla muchos, columna, tabla uno, columna)
RELACIONES = (
    ("Siniestro", "ID_ITEM", "Seguro", "ID_ITEM"),
    ("Prima", "ID_ITEM", "Seguro", "ID_ITEM"),
    ("Cuota", "ID_MOVIMIENTO_PRIMA", "Prima", "ID_MOVIMIENTO_PRIMA"),
    ("Seguro", "ID_CLIENTE", "Cliente", "ID_CLIENTE"),
)

TABLAS_DOMINIO = {
    "SIN": ("Siniestro", "Seguro"),
    "FIN": ("Prima", "Seguro"),
    "SEG": ("Seguro", "Cliente"),
    "CUO": ("Cuota", "Prima", "Seguro"),
}

MEDIDAS_CATALOGO: dict[str, dict[str, tuple[str, str]]] = {
    "SIN": {
        "cantidad_siniestros": ("Siniestro", "Siniestros"),
        "monto_pagado": ("Siniestro", "Monto pagado"),
        "monto_pagado_promedio": ("Siniestro", "Monto pagado promedio"),
        "monto_denunciado": ("Siniestro", "Monto denunciado"),
        "monto_reserva": ("Siniestro", "Monto en reserva"),
        "monto_recuperado": ("Siniestro", "Monto recuperado"),
    },
    "FIN": {
        "prima_total": ("Prima", "Prima directa neta"),
        "prima_cedida": ("Prima", "Prima cedida neta"),
        "prima_retenida": ("Prima", "Prima retenida neta"),
        "comision_total": ("Prima", "Comisión total"),
        "cantidad_movimientos": ("Prima", "Movimientos de prima"),
    },
    "SEG": {
        "cantidad_items": ("Seguro", "Ítems asegurados"),
        "cantidad_polizas": ("Seguro", "Pólizas"),
        "monto_asegurado": ("Seguro", "Monto asegurado"),
    },
    "CUO": {
        "monto_cuotas": ("Cuota", "Monto total de cuotas"),
        "monto_cuotas_pagadas": ("Cuota", "Monto de cuotas pagadas"),
        "monto_cuotas_pendientes": ("Cuota", "Monto de cuotas pendientes"),
        "monto_cuotas_vencidas": ("Cuota", "Monto de cuotas vencidas"),
        "cantidad_cuotas": ("Cuota", "Total de cuotas"),
    },
}

_PRODUCTO, _REGION = ("Seguro", "Producto"), ("Seguro", "Región")
DIMENSIONES_CATALOGO: dict[str, dict[str, tuple[str, str]]] = {
    "SIN": {
        "tipo_siniestro": ("Siniestro", "Tipo de siniestro"),
        "estado_siniestro": ("Siniestro", "Estado del siniestro"),
        "producto": _PRODUCTO, "region": _REGION, "mes": ("Siniestro", "Mes"),
    },
    "FIN": {
        "tipo_movimiento": ("Prima", "Tipo de movimiento"),
        "producto": _PRODUCTO, "region": _REGION, "mes": ("Prima", "Mes"),
    },
    "SEG": {
        "producto": _PRODUCTO, "region": _REGION,
        "estado_poliza": ("Seguro", "Estado de la póliza"),
        "segmento": ("Cliente", "Segmento"),
        "tipo_cliente": ("Cliente", "Tipo de cliente"),
        "mes": ("Seguro", "Mes de emisión"),
    },
    "CUO": {
        "estado_cuota": ("Cuota", "Estado de la cuota"),
        "producto": _PRODUCTO, "region": _REGION, "mes": ("Cuota", "Mes de vencimiento"),
    },
}

TIPO_VISUAL = {"lineas": "lineChart", "barras": "clusteredBarChart", "torta": "donutChart"}


def _id() -> str:
    return uuid.uuid4().hex[:20]


def _json(datos) -> str:
    return json.dumps(datos, ensure_ascii=False, indent=2)


# --- Modelo semántico --------------------------------------------------------

def _texto_m(valor: str) -> str:
    return '"' + valor.replace('"', '""') + '"'


def _columna_incluida(c: ColumnaPbi, dominios: set[str]) -> bool:
    return c.solo_dominio is None or c.solo_dominio in dominios


def _consulta_m(tabla: TablaPbi, columnas: list[ColumnaPbi], meses: tuple[tuple[str, str], ...]) -> list[str]:
    # Las fechas de los meses pueden no ser columnas visibles para este usuario
    necesarias = list(dict.fromkeys([*(c.fuente for c in columnas), *(f for _, f in meses)]))
    seleccion = ", ".join(_texto_m(c) for c in necesarias)
    lineas = [
        "let",
        f"    Origen = Sql.Database({_texto_m(db.SERVIDOR)}, {_texto_m(db.BASE)}),",
        f'    Datos = Origen{{[Schema="ods",Item={_texto_m(tabla.fuente)}]}}[Data],',
        f"    Paso0 = Table.SelectColumns(Datos, {{{seleccion}}}),",
    ]
    for n, (nombre, fecha) in enumerate(meses):
        lineas.append(
            f"    Paso{n + 1} = Table.AddColumn(Paso{n}, {_texto_m(nombre)}, "
            f'each Date.ToText([{fecha}], "yyyy-MM"), type text),'
        )
    finales = ", ".join(_texto_m(x) for x in [c.fuente for c in columnas] + [m for m, _ in meses])
    lineas += [f"    Final = Table.SelectColumns(Paso{len(meses)}, {{{finales}}})", "in", "    Final"]
    return lineas


def _tabla_modelo(nombre: str, dominios: set[str]) -> dict:
    tabla = TABLAS[nombre]
    columnas = [c for c in tabla.columnas if _columna_incluida(c, dominios)]
    # El mes de emisión es dato de cartera: sin SEG tampoco se expone
    meses = tabla.meses if tabla.medidas_solo_dominio is None or tabla.medidas_solo_dominio in dominios else ()
    definicion = {
        "name": nombre,
        "columns": [
            {
                "name": c.nombre,
                "dataType": c.tipo,
                "sourceColumn": c.fuente,
                "summarizeBy": "none",
                **({"isHidden": True} if c.oculta else {}),
                **({"formatString": "yyyy-MM-dd"} if c.tipo == "dateTime" else {}),
            }
            for c in columnas
        ] + [
            {"name": m, "dataType": "string", "sourceColumn": m, "summarizeBy": "none"}
            for m, _ in meses
        ],
        "partitions": [{
            "name": nombre,
            "mode": "import",
            "source": {"type": "m", "expression": _consulta_m(tabla, columnas, meses)},
        }],
    }
    if tabla.medidas_solo_dominio is None or tabla.medidas_solo_dominio in dominios:
        definicion["measures"] = [
            {"name": m.nombre, "expression": m.dax, "formatString": m.formato} for m in tabla.medidas
        ]
    return definicion


def _modelo(nombres: list[str], dominios: set[str]) -> dict:
    return {
        "compatibilityLevel": 1567,
        "model": {
            "culture": "es-CL",
            "sourceQueryCulture": "es-CL",
            "dataAccessOptions": {"legacyRedirects": True, "returnErrorValuesAsNull": True},
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "tables": [_tabla_modelo(n, dominios) for n in nombres],
            "relationships": [
                {"name": _id(), "fromTable": a, "fromColumn": b, "toTable": c, "toColumn": d}
                for a, b, c, d in RELACIONES
                if a in nombres and c in nombres
            ],
            "annotations": [{"name": "__PBI_TimeIntelligenceEnabled", "value": "0"}],
        },
    }


# --- Informe -----------------------------------------------------------------

def _campo_medida(tabla: str, nombre: str) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": tabla}}, "Property": nombre}}


def _campo_columna(tabla: str, nombre: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": tabla}}, "Property": nombre}}


def _proyeccion(campo: dict, tabla: str, nombre: str) -> dict:
    return {"field": campo, "queryRef": f"{tabla}.{nombre}", "nativeQueryRef": nombre}


def _literal(valor: str) -> dict:
    return {"expr": {"Literal": {"Value": valor}}}


def _titulo(texto: str) -> dict:
    escapado = texto.replace("'", "''")
    return {"title": [{"properties": {"show": _literal("true"), "text": _literal(f"'{escapado}'")}}]}


def _filtro_visual(tabla: str, columna: str, valores: list[str]) -> dict:
    alias = "t"
    return {
        "name": _id(),
        "field": _campo_columna(tabla, columna),
        "type": "Categorical",
        "filter": {
            "Version": 2,
            "From": [{"Name": alias, "Entity": tabla, "Type": 0}],
            "Where": [{
                "Condition": {
                    "In": {
                        "Expressions": [{
                            "Column": {"Expression": {"SourceRef": {"Source": alias}}, "Property": columna},
                        }],
                        "Values": [[{"Literal": {"Value": "'" + v.replace("'", "''") + "'"}}] for v in valores],
                    },
                },
            }],
        },
    }


@dataclass
class Visual:
    tipo: str
    x: int
    y: int
    ancho: int
    alto: int
    titulo: str | None = None
    roles: dict[str, list[dict]] = field(default_factory=dict)
    orden: dict | None = None
    filtros: list[dict] = field(default_factory=list)


def _visual_json(v: Visual, indice: int) -> dict:
    nombre = _id()
    query: dict = {"queryState": {rol: {"projections": p} for rol, p in v.roles.items()}}
    if v.orden:
        query["sortDefinition"] = v.orden
    visual: dict = {"visualType": v.tipo, "query": query, "drillFilterOtherVisuals": True}
    if v.titulo:
        visual["visualContainerObjects"] = _titulo(v.titulo)
    datos = {
        "$schema": f"{ESQUEMAS}/report/definition/visualContainer/2.0.0/schema.json",
        "name": nombre,
        "position": {"x": v.x, "y": v.y, "z": indice, "height": v.alto, "width": v.ancho, "tabOrder": indice},
        "visual": visual,
    }
    if v.filtros:
        datos["filterConfig"] = {"filters": v.filtros}
    return datos


def _grafico(tipo: str, tabla_med: str, medida: str, tabla_dim: str, dim: str, titulo: str,
             x: int, y: int, ancho: int, alto: int, filtros: list[dict] | None = None) -> Visual:
    campo_med = _campo_medida(tabla_med, medida)
    campo_dim = _campo_columna(tabla_dim, dim)
    if tipo == "tabla":
        return Visual("tableEx", x, y, ancho, alto, titulo, {"Values": [
            _proyeccion(campo_dim, tabla_dim, dim), _proyeccion(campo_med, tabla_med, medida),
        ]}, filtros=filtros or [])
    orden = None
    if tipo == "lineas":
        orden = {"sort": [{"field": campo_dim, "direction": "Ascending"}], "isDefaultSort": True}
    elif tipo == "barras":
        orden = {"sort": [{"field": campo_med, "direction": "Descending"}], "isDefaultSort": True}
    return Visual(TIPO_VISUAL[tipo], x, y, ancho, alto, titulo, {
        "Category": [_proyeccion(campo_dim, tabla_dim, dim)],
        "Y": [_proyeccion(campo_med, tabla_med, medida)],
    }, orden, filtros or [])


def _tarjeta(tabla: str, medida: str, x: int, y: int, ancho: int, alto: int,
             filtros: list[dict] | None = None, titulo: str | None = None) -> Visual:
    return Visual("card", x, y, ancho, alto, titulo,
                  {"Values": [_proyeccion(_campo_medida(tabla, medida), tabla, medida)]}, filtros=filtros or [])


ANCHO, ALTO, MARGEN, SEPARACION = 1280, 720, 16, 12


def _meses_entre(desde: str, hasta: str) -> list[str]:
    a, m = map(int, desde.split("-"))
    a_fin, m_fin = map(int, hasta.split("-"))
    meses = []
    while (a, m) <= (a_fin, m_fin):
        meses.append(f"{a:04d}-{m:02d}")
        a, m = a + (m == 12), m % 12 + 1
    return meses


def _filtros_plan(plan: PlanConsulta, dominio: catalogo.DominioDisponible) -> list[dict]:
    dims = DIMENSIONES_CATALOGO[plan.dominio]
    filtros = [_filtro_visual(*dims[f.campo], [f.valor]) for f in plan.filtros]
    if plan.desde or plan.hasta:
        desde = plan.desde or dominio.rango_meses[0]
        hasta = plan.hasta or dominio.rango_meses[1]
        filtros.append(_filtro_visual(*dims["mes"], _meses_entre(desde, hasta)))
    return filtros


def _paginas_propias(planes: list[tuple[str, PlanConsulta]], cat: catalogo.Catalogo) -> list[list[Visual]]:
    """Los gráficos pedidos en el chat, de a seis por página."""
    paginas: list[list[Visual]] = []
    ancho_g = (ANCHO - 2 * MARGEN - SEPARACION) // 2
    alto_g = (ALTO - 2 * MARGEN - 2 * SEPARACION) // 3
    for n in range(0, len(planes), 6):
        visuales = []
        for i, (titulo, plan) in enumerate(planes[n:n + 6]):
            titulo = f"{cat.dominios[plan.dominio]} · {titulo}"
            x = MARGEN + (i % 2) * (ancho_g + SEPARACION)
            y = MARGEN + (i // 2) * (alto_g + SEPARACION)
            tabla_med, medida = MEDIDAS_CATALOGO[plan.dominio][plan.metrica]
            filtros = _filtros_plan(plan, cat.disponibles[plan.dominio])
            tipo = plan.tipo_salida.removeprefix("grafico_")
            # El mapa de Power BI depende de un servicio externo de mapas: se exporta como barras
            if tipo == "mapa":
                tipo = "barras"
            if plan.agrupar_por == catalogo.NINGUNO or tipo == "kpi":
                visuales.append(_tarjeta(tabla_med, medida, x, y, ancho_g, alto_g, filtros, titulo))
                continue
            tabla_dim, dim = DIMENSIONES_CATALOGO[plan.dominio][plan.agrupar_por]
            visuales.append(_grafico(tipo, tabla_med, medida, tabla_dim, dim, titulo, x, y, ancho_g, alto_g, filtros))
        paginas.append(visuales)
    return paginas


def _tema() -> dict:
    return {"name": TEMA, "dataColors": ["#1E2A5E", "#14B8A6", "#D97706", "#7C3AED", "#64748B"]}


def generar_zip(cat: catalogo.Catalogo, graficos: list[tuple[str, PlanConsulta]], titulo: str = "Mis gráficos") -> bytes:
    """Arma el .zip con los gráficos del chat, que ya deben venir validados. El
    modelo solo trae las tablas y columnas de los dominios de esos gráficos."""
    dominios = {plan.dominio for _, plan in graficos}
    nombres_tablas = list(dict.fromkeys(t for c in sorted(dominios) for t in TABLAS_DOMINIO[c]))

    propias = _paginas_propias(graficos, cat)
    paginas = [
        (f"{titulo[:90]} {i + 1}" if len(propias) > 1 else titulo[:100], visuales)
        for i, visuales in enumerate(propias)
    ]

    raiz_r, raiz_m = f"{NOMBRE}.Report", f"{NOMBRE}.SemanticModel"
    def_r = f"{raiz_r}/definition"
    archivos: dict[str, str] = {
        f"{NOMBRE}.pbip": _json({
            "version": "1.0",
            "artifacts": [{"report": {"path": raiz_r}}],
            "settings": {"enableAutoRecovery": True},
        }),
        f"{raiz_r}/definition.pbir": _json({
            "$schema": f"{ESQUEMAS}/report/definitionProperties/2.0.0/schema.json",
            "version": "4.0",
            "datasetReference": {"byPath": {"path": f"../{raiz_m}"}},
        }),
        f"{def_r}/version.json": _json({
            "$schema": f"{ESQUEMAS}/report/definition/versionMetadata/1.0.0/schema.json",
            "version": "2.0.0",
        }),
        f"{def_r}/report.json": _json({
            "$schema": f"{ESQUEMAS}/report/definition/report/3.0.0/schema.json",
            "themeCollection": {
                "baseTheme": {
                    "name": TEMA,
                    "reportVersionAtImport": {"visual": "2.0.0", "report": "3.0.0", "page": "2.0.0"},
                    "type": "SharedResources",
                },
            },
            "resourcePackages": [{
                "name": "SharedResources",
                "type": "SharedResources",
                "items": [{"name": TEMA, "path": f"BaseThemes/{TEMA}.json", "type": "BaseTheme"}],
            }],
            "settings": {"useStylableVisualContainerHeader": True, "defaultDrillFilterOtherVisuals": True},
        }),
        f"{raiz_r}/StaticResources/SharedResources/BaseThemes/{TEMA}.json": _json(_tema()),
        f"{raiz_m}/definition.pbism": _json({
            "$schema": f"{ESQUEMAS}/semanticModel/definitionProperties/1.0.0/schema.json",
            "version": "1.0",
            "settings": {},
        }),
        f"{raiz_m}/model.bim": _json(_modelo(nombres_tablas, dominios)),
        "LEEME.txt": LEEME,
    }

    ids_pagina = []
    for nombre_pagina, visuales in paginas:
        id_pagina = _id()
        ids_pagina.append(id_pagina)
        archivos[f"{def_r}/pages/{id_pagina}/page.json"] = _json({
            "$schema": f"{ESQUEMAS}/report/definition/page/2.0.0/schema.json",
            "name": id_pagina,
            "displayName": nombre_pagina,
            "displayOption": "FitToPage",
            "height": ALTO,
            "width": ANCHO,
        })
        for i, v in enumerate(visuales):
            datos = _visual_json(v, i)
            archivos[f"{def_r}/pages/{id_pagina}/visuals/{datos['name']}/visual.json"] = _json(datos)
    archivos[f"{def_r}/pages/pages.json"] = _json({
        "$schema": f"{ESQUEMAS}/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": ids_pagina,
        "activePageName": ids_pagina[0],
    })

    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z:
        for ruta, contenido in archivos.items():
            z.writestr(f"{NOMBRE}/{ruta}", contenido)
    return salida.getvalue()


LEEME = """BI Copilot - proyecto de Power BI

1. Descomprime TODA la carpeta (no abras el archivo desde dentro del .zip).
2. Abre BI_Copilot.pbip con Power BI Desktop.
3. Si te pide credenciales de SQL Server, elige "Windows" y "Usar mis credenciales actuales".
   Si advierte que la conexion no esta cifrada, acepta para continuar en el servidor local.
4. Presiona "Actualizar" en la cinta de Inicio para cargar los datos.
5. Para obtener un unico archivo: Archivo > Guardar como > Informe de Power BI (.pbix).

El proyecto no incluye datos ni contrasenas: lee directamente desde SQL Server.
"""
