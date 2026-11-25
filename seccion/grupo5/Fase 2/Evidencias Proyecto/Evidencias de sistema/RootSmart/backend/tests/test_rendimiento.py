"""Pruebas de rendimiento del backend (sin contar la latencia de SQL Server ni de Claude).

Los umbrales son holgados para que pasen en cualquier equipo; los tiempos medidos
se imprimen con `pytest -s` y se registran en el plan de pruebas.
"""

import time

from fastapi.testclient import TestClient

from app import claves, main
from app.consultas import construir_sql, validar_plan

from conftest import plan


def _medir(funcion, repeticiones: int) -> float:
    inicio = time.perf_counter()
    for _ in range(repeticiones):
        funcion()
    return (time.perf_counter() - inicio) / repeticiones


def test_validar_y_armar_sql_toma_menos_de_5_ms(cat):
    p = plan(desde="2026-01", hasta="2026-04")
    promedio = _medir(lambda: (validar_plan(p, cat, {"SIN"}), construir_sql(p, cat)), 1000)
    print(f"\nvalidar + construir SQL: {promedio * 1000:.3f} ms por consulta")
    assert promedio < 0.005


def test_verificar_clave_es_lento_a_proposito_pero_usable():
    # PBKDF2 con 600.000 iteraciones: lento para un atacante, aceptable para un login
    h = claves.generar_hash("1234")
    promedio = _medir(lambda: claves.verificar("1234", h), 3)
    print(f"\nverificar clave: {promedio * 1000:.0f} ms")
    assert 0.05 < promedio < 3


def test_rechazo_de_peticiones_sin_sesion_bajo_carga():
    cliente = TestClient(main.app)
    n = 200
    inicio = time.perf_counter()
    for _ in range(n):
        assert cliente.post("/api/consultas", json={"pregunta": "x"}).status_code == 401
    por_segundo = n / (time.perf_counter() - inicio)
    print(f"\nrechazos 401 por segundo: {por_segundo:.0f}")
    assert por_segundo > 50
