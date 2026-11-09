"""Exporta los gráficos del chat a un solo archivo .html interactivo.

El archivo se abre con doble clic, sin servidor ni internet. Para poder filtrar
en el navegador, cada gráfico lleva sus totales agrupados por categoría, región,
producto y mes; nunca filas de detalle. Los datos son los del momento de exportar.
"""

import json
from datetime import datetime
from pathlib import Path

from . import catalogo, consultas, db
from .ia import PlanConsulta

_PLANTILLA = Path(__file__).with_name("plantilla_reporte.html")
_MAPA_CHILE = Path(__file__).with_name("chile_regiones.json")
SIN_DATO = "—"


def mapa_chile() -> str:
    return _MAPA_CHILE.read_text(encoding="utf-8")

# Métricas que no se pueden sumar entre grupos: se envía lo necesario para recalcularlas
PROMEDIOS: dict[str, catalogo.Columna] = {"monto_pagado_promedio": (catalogo.SIN, "MNT_PAGADO")}
DISTINTOS: dict[str, catalogo.Columna] = {"cantidad_polizas": (catalogo.SEG, "COD_POLIZA")}


def _sql_grafico(plan: PlanConsulta, cat: catalogo.Catalogo) -> tuple[str, list, str]:
    """(sql, parámetros, modo). Las columnas salen del catálogo y los valores van como parámetros."""
    dominio = cat.disponibles[plan.dominio]
    where, params = consultas.filtros_sql(plan, cat)

    categoria = dominio.sql_dimension(plan.agrupar_por)
    region = dominio.sql_dimension("region") if "region" in dominio.atributos else None
    producto = dominio.sql_dimension("producto") if "producto" in dominio.atributos else None
    mes = dominio.sql_dimension(catalogo.MES) if dominio.con_fecha else None
    columnas = {"categoria": categoria, "region": region, "producto": producto, "mes": mes}

    def literal(expresion: str | None, alias: str) -> str:
        texto = "Total" if alias == "categoria" else SIN_DATO
        return f"{expresion} AS {alias}" if expresion else f"N'{texto}' AS {alias}"

    seleccion = ", ".join(literal(e, alias) for alias, e in columnas.items())
    grupos = [e for e in columnas.values() if e]

    if plan.metrica in DISTINTOS:
        modo = "distinto"
        columna = catalogo.sql_columna(DISTINTOS[plan.metrica])
        medida = f"DENSE_RANK() OVER (ORDER BY {columna}) AS valor, 1 AS cantidad"
        grupos.append(columna)
    elif plan.metrica in PROMEDIOS:
        modo = "promedio"
        columna = catalogo.sql_columna(PROMEDIOS[plan.metrica])
        medida = f"SUM({columna}) AS valor, COUNT({columna}) AS cantidad"
    else:
        modo = "suma"
        medida = f"{dominio.sql_medida(plan.metrica)} AS valor, COUNT(*) AS cantidad"

    grupo = " GROUP BY " + ", ".join(grupos) if grupos else ""
    return f"SELECT {seleccion}, {medida} FROM {dominio.sql_from()}{where}{grupo}", params, modo


class _Indice:
    """Guarda cada texto una sola vez para que el archivo pese menos."""

    def __init__(self) -> None:
        self.valores: list[str] = []
        self._posicion: dict[str, int] = {}

    def __call__(self, valor) -> int:
        texto = SIN_DATO if valor is None else str(valor)
        if texto not in self._posicion:
            self._posicion[texto] = len(self.valores)
            self.valores.append(texto)
        return self._posicion[texto]


def _visualizacion(plan: PlanConsulta) -> str:
    tipo = plan.tipo_salida.removeprefix("grafico_")
    return "kpi" if plan.agrupar_por == catalogo.NINGUNO else tipo


def generar(titulo: str, cat: catalogo.Catalogo, graficos: list[tuple[str, PlanConsulta]]) -> str:
    """HTML completo. `graficos` ya deben venir validados."""
    regiones, productos, meses = _Indice(), _Indice(), _Indice()
    salida = []
    for titulo_grafico, plan in graficos:
        dominio = cat.disponibles[plan.dominio]
        sql, params, modo = _sql_grafico(plan, cat)
        categorias = _Indice()
        filas = [
            [categorias(f["categoria"]), regiones(f["region"]), productos(f["producto"]), meses(f["mes"]),
             f["valor"] or 0, f["cantidad"]]
            for f in db.ejecutar(sql, params)["filas"]
        ]
        medida = dominio.medidas[plan.metrica]
        periodo = [f"{plan.desde or '…'} a {plan.hasta or '…'}"] if plan.desde or plan.hasta else []
        salida.append({
            "titulo": titulo_grafico,
            "area": cat.dominios[plan.dominio],
            "etiquetaMetrica": medida.etiqueta,
            "etiquetaDimension": dominio.etiqueta_dimension(plan.agrupar_por),
            "agruparPor": plan.agrupar_por,
            "tipo": _visualizacion(plan),
            "moneda": medida.moneda,
            "modo": modo,
            "filtrosFijos": [f.valor for f in plan.filtros] + periodo,
            "categorias": categorias.valores,
            "filas": filas,
        })

    datos = {
        "titulo": titulo,
        "exportado": datetime.now().strftime("%d-%m-%Y %H:%M"),
        "regiones": regiones.valores,
        "productos": productos.valores,
        "meses": meses.valores,
        "graficos": salida,
        "mapa": json.loads(mapa_chile()) if any(g["tipo"] == "mapa" for g in salida) else None,
    }
    # Con < escapado, un título escrito en el chat no puede cerrar el bloque <script>
    incrustado = json.dumps(datos, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return _PLANTILLA.read_text(encoding="utf-8").replace("__DATOS__", incrustado)
