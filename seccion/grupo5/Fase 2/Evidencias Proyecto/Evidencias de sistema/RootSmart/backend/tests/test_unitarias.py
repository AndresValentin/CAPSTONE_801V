"""Pruebas unitarias: validación del plan, armado del SQL y utilidades."""

from app import analisis, catalogo
from app.consultas import construir_sql, normalizar_salida, rechazo_previo, validar_plan
from app.ia import FiltroPlan

from conftest import plan

TODOS = {"SIN", "FIN", "SEG", "CUO"}


# --- validar_plan (RF-005 / RF-006) ---------------------------------------

def test_plan_valido_se_acepta(cat):
    assert validar_plan(plan(), cat, {"SIN"}) is None


def test_plan_con_filtro_y_periodo_valido(cat):
    p = plan(filtros=[FiltroPlan(campo="region", valor="Valparaíso")], desde="2026-01", hasta="2026-04")
    assert validar_plan(p, cat, {"SIN"}) is None


def test_metrica_fuera_del_catalogo_se_rechaza(cat):
    assert "métrica" in validar_plan(plan(metrica="sueldo_gerente"), cat, TODOS)


def test_agrupacion_fuera_del_catalogo_se_rechaza(cat):
    assert "agrupar" in validar_plan(plan(agrupar_por="rut_cliente"), cat, TODOS)


def test_valor_de_filtro_inexistente_se_rechaza(cat):
    p = plan(filtros=[FiltroPlan(campo="region", valor="Marte")])
    assert "no es válido" in validar_plan(p, cat, TODOS)


def test_dos_filtros_sobre_el_mismo_campo_se_rechazan(cat):
    p = plan(filtros=[FiltroPlan(campo="region", valor="Biobío"), FiltroPlan(campo="region", valor="Valparaíso")])
    assert "mismo campo" in validar_plan(p, cat, TODOS)


def test_formato_de_mes_invalido_se_rechaza(cat):
    assert "AAAA-MM" in validar_plan(plan(desde="abril"), cat, TODOS)
    assert "AAAA-MM" in validar_plan(plan(desde="0000-01"), cat, TODOS)


def test_periodo_invertido_se_rechaza(cat):
    assert "posterior" in validar_plan(plan(desde="2026-05", hasta="2026-01"), cat, TODOS)


def test_tipo_de_grafico_invalido_se_rechaza(cat):
    assert "gráfico" in validar_plan(plan(tipo_salida="grafico_3d"), cat, TODOS)


def test_plan_de_rechazo_de_la_ia_devuelve_su_motivo(cat):
    p = plan(accion="rechazar", motivo_rechazo="Fuera del catálogo")
    assert validar_plan(p, cat, TODOS) == "Fuera del catálogo"


# --- construir_sql (RF-009) -------------------------------------------------

def test_sql_tiene_total_serie_y_detalle(cat):
    consultas = construir_sql(plan(), cat)
    assert set(consultas) == {"total", "serie", "detalle"}


def test_sql_solo_contiene_select(cat):
    for sql, _ in construir_sql(plan(desde="2026-01", hasta="2026-03"), cat).values():
        assert sql.lstrip().upper().startswith("SELECT")


def test_sql_limita_filas(cat):
    consultas = construir_sql(plan(), cat)
    assert "TOP (500)" in consultas["serie"][0]
    assert "TOP (50)" in consultas["detalle"][0]


def test_sql_agrupa_por_mes(cat):
    sql, _ = construir_sql(plan(agrupar_por=catalogo.MES), cat)["serie"]
    assert "CONVERT(CHAR(7)" in sql and "GROUP BY" in sql


def test_sql_une_con_polizas_para_agrupar_por_region(cat):
    sql, _ = construir_sql(plan(), cat)["serie"]
    assert "JOIN ods.ODS_SEG_SEGURO" in sql


# --- utilidades ---------------------------------------------------------------

def test_mapa_sin_region_se_cambia_a_barras():
    p = normalizar_salida(plan(tipo_salida="grafico_mapa", agrupar_por="tipo_siniestro"))
    assert p.tipo_salida == "grafico_barras"


def test_mapa_por_region_se_mantiene():
    assert normalizar_salida(plan(tipo_salida="grafico_mapa")).tipo_salida == "grafico_mapa"


def test_sumar_meses_cruza_el_anio():
    assert analisis.sumar_meses("2026-11", 3) == "2027-02"
    assert analisis.sumar_meses("2026-01", -1) == "2025-12"


def test_pregunta_de_lectura_no_se_rechaza():
    assert rechazo_previo("Monto pagado por región en abril") is None


def test_permisos_de_cobranza_dependen_de_finanzas():
    assert "CUO" in catalogo.ampliar_permisos({"FIN"})
    assert "CUO" not in catalogo.ampliar_permisos({"SIN"})
