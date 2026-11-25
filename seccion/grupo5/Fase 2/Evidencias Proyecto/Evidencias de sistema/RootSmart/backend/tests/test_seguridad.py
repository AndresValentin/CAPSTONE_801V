"""Pruebas de seguridad: contraseñas, sesiones, escritura bloqueada, inyección SQL y permisos."""

import time

import pytest

from app import claves, sesion
from app.consultas import construir_sql, rechazo_previo, validar_plan
from app.ia import FiltroPlan

from conftest import plan


# --- Contraseñas (PBKDF2-SHA256) ---------------------------------------------

def test_hash_no_contiene_la_clave():
    h = claves.generar_hash("MiClave2026")
    assert "MiClave2026" not in h
    assert h.startswith("pbkdf2_sha256$600000$")


def test_misma_clave_genera_hashes_distintos_por_la_sal():
    assert claves.generar_hash("1234") != claves.generar_hash("1234")


def test_clave_correcta_e_incorrecta():
    h = claves.generar_hash("1234")
    assert claves.verificar("1234", h)
    assert not claves.verificar("12345", h)


@pytest.mark.parametrize("guardado", [None, "", "texto-cualquiera", "md5$1$abc$def", "pbkdf2_sha256$x$y$z"])
def test_hash_vacio_o_alterado_no_permite_entrar(guardado):
    assert not claves.verificar("1234", guardado)


# --- Sesiones (token firmado con HMAC) ---------------------------------------

def test_token_valido_devuelve_el_usuario():
    assert sesion.leer_token(sesion.crear_token("USR_SIN")) == "USR_SIN"


def test_cambiar_el_usuario_del_token_invalida_la_firma():
    _, vence, firma = sesion.crear_token("USR_SIN").split(".")
    assert sesion.leer_token(f"USR_ADMIN.{vence}.{firma}") is None


def test_alargar_el_vencimiento_invalida_la_firma():
    usuario, vence, firma = sesion.crear_token("USR_SIN").split(".")
    assert sesion.leer_token(f"{usuario}.{int(vence) + 86400}.{firma}") is None


def test_token_vencido_se_rechaza(monkeypatch):
    token = sesion.crear_token("USR_SIN")
    monkeypatch.setattr(time, "time", lambda: 9_999_999_999)
    assert sesion.leer_token(token) is None


@pytest.mark.parametrize("token", ["", "abc", "a.b", "a.b.c.d", "USR_SIN.no-es-numero.firma"])
def test_token_malformado_se_rechaza(token):
    assert sesion.leer_token(token) is None


# --- Solo lectura (RN-02) -------------------------------------------------------

@pytest.mark.parametrize("pregunta", [
    "Borra los siniestros de abril",
    "elimina las pólizas vencidas",
    "DROP TABLE ods.ODS_SIN_SINIESTRO",
    "actualiza el monto pagado a cero",
    "INSERT INTO seguridad.SEG_USUARIO VALUES ('x')",
    "'; TRUNCATE TABLE ods.ODS_FIN_PRIMA; --",
])
def test_pedidos_de_escritura_se_bloquean_antes_de_la_ia(pregunta):
    assert rechazo_previo(pregunta) is not None


# --- Inyección SQL ----------------------------------------------------------------

def test_valor_malicioso_en_un_filtro_se_rechaza(cat):
    p = plan(filtros=[FiltroPlan(campo="region", valor="x' OR 1=1; DROP TABLE ods.ODS_SIN_SINIESTRO; --")])
    assert validar_plan(p, cat, {"SIN"}) is not None


def test_los_valores_viajan_como_parametros_y_no_dentro_del_sql(cat):
    p = plan(filtros=[FiltroPlan(campo="region", valor="Valparaíso")], desde="2026-01")
    for sql, params in construir_sql(p, cat).values():
        assert "Valparaíso" not in sql
        assert "?" in sql
        assert "Valparaíso" in params


# --- Permisos por área -------------------------------------------------------------

def test_usuario_sin_permiso_de_finanzas_no_consulta_finanzas(cat):
    p = plan(dominio="FIN", metrica="prima_total", agrupar_por="region")
    assert "no autorizado" in validar_plan(p, cat, {"SIN"})


def test_catalogo_no_expone_columnas_con_datos_personales(cat):
    for dominio in cat.disponibles.values():
        for atributo in dominio.atributos.values():
            columna = atributo.columna[1].upper()
            assert not any(s in columna for s in ("RUT", "CORREO", "EMAIL", "TELEFONO", "DIRECCION"))
