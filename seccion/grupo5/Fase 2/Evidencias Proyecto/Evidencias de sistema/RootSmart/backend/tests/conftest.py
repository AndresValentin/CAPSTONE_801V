"""Configuración común de las pruebas.

Las pruebas no necesitan SQL Server ni la API de Anthropic: el catálogo se arma
con las definiciones reales de app/catalogo.py y valores de ejemplo, y en las
pruebas de la API la base de datos y la IA se reemplazan por dobles de prueba.
"""

import os
import sys
from pathlib import Path

import pytest

# Deben existir antes de importar app.*: sesion.py lee la clave al cargarse
os.environ.setdefault("SESSION_SECRET", "clave-solo-para-pruebas")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-pruebas")
os.environ["DB_USUARIO_LECTOR"] = "bi_lector"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import catalogo, db  # noqa: E402

DOMINIOS = {"SIN": "Siniestros", "FIN": "Finanzas", "SEG": "Seguros", "CUO": "Cobranza de cuotas"}

VALORES = {
    "DESC_REGION": ["Metropolitana", "Valparaíso", "Biobío"],
    "DESC_TIPO_SINIESTRO": ["CHOQUE", "ROBO", "INCENDIO"],
    "DESC_ESTADO_SINIESTRO": ["ABIERTO", "CERRADO"],
    "DESC_PRODUCTO": ["AUTO", "HOGAR"],
}


def _columnas_y_relaciones():
    """Todas las columnas y relaciones que usan las definiciones, como si meta.* las habilitara."""
    columnas: dict[str, set[str]] = {}
    relaciones = set()
    for d in catalogo.DEFINICIONES.values():
        usadas = [d.fecha.columna, *(a.columna for a in d.atributos.values()), *(a.columna for a in d.detalle)]
        usadas += [c for m in d.medidas.values() for c in m.columnas]
        for tabla, columna in usadas:
            columnas.setdefault(tabla, set()).add(columna)
        for u in d.uniones:
            columnas.setdefault(u.tabla, set()).add(u.columna_destino)
            relaciones.add((u.origen or d.tabla, u.columna_origen, u.tabla, u.columna_destino))
    return columnas, relaciones


@pytest.fixture(scope="session")
def cat() -> catalogo.Catalogo:
    """Catálogo completo con valores de ejemplo, sin conectarse a SQL Server."""
    mp = pytest.MonkeyPatch()
    mp.setattr(db, "valores_distintos", lambda origen, col: VALORES.get(col.rsplit(".", 1)[-1], ["A", "B"]))
    mp.setattr(db, "rango_meses", lambda origen, col: ("2024-01", "2026-10"))
    mp.setattr(db, "registros_por_mes", lambda origen, col: {})
    columnas, relaciones = _columnas_y_relaciones()
    disponibles = {}
    for cod, definicion in catalogo.DEFINICIONES.items():
        dominio = catalogo._cargar_dominio(definicion, columnas, relaciones)
        if dominio:
            disponibles[cod] = dominio
    mp.undo()
    return catalogo.Catalogo(dominios=dict(DOMINIOS), disponibles=disponibles)


def plan(**cambios):
    """Plan válido de Siniestros, con los cambios indicados."""
    from app.ia import PlanConsulta

    base = dict(
        accion="consultar", motivo_rechazo="", dominio="SIN", titulo="Monto pagado por región",
        metrica="monto_pagado", agrupar_por="region", filtros=[], desde="", hasta="",
        tipo_salida="grafico_barras",
    )
    return PlanConsulta(**(base | cambios))
