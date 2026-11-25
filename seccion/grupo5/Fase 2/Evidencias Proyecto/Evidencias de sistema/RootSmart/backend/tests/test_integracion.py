"""Pruebas de integración de la API: login, permisos, flujo pregunta -> plan -> SQL -> respuesta
y auditoría. SQL Server y Claude se reemplazan por dobles de prueba, así que se prueba
todo el backend (FastAPI, validación, SQL y respuesta) sin servicios externos."""

import pytest
from fastapi.testclient import TestClient

from app import catalogo, claves, db, main, sesion

from conftest import plan

HASH_1234 = claves.generar_hash("1234")
USUARIOS = {
    "USR_SIN": {"usuario": "USR_SIN", "nombre": "Analista Siniestros", "clave_hash": HASH_1234, "dominios": {"SIN"}},
    "USR_ADMIN": {"usuario": "USR_ADMIN", "nombre": "Administrador", "clave_hash": HASH_1234,
                  "dominios": {"SIN", "FIN", "SEG"}},
}


@pytest.fixture
def api(cat, monkeypatch):
    """Cliente de la API con la BD y la IA simuladas. Devuelve (cliente, registro de llamadas)."""
    registro = {"auditoria": [], "sql": [], "ia": []}

    def usuario(cod):
        u = USUARIOS.get(cod)
        return {k: u[k] for k in ("usuario", "nombre", "clave_hash")} if u else None

    def ejecutar(sql, params):
        registro["sql"].append((sql, params))
        if "GROUP BY" in sql:
            return {"columnas": ["categoria", "valor"],
                    "filas": [{"categoria": "Metropolitana", "valor": 1500}, {"categoria": "Valparaíso", "valor": 900}]}
        if sql.startswith("SELECT TOP"):
            return {"columnas": ["Región"], "filas": [{"Región": "Metropolitana"}]}
        return {"columnas": ["valor", "cantidad"], "filas": [{"valor": 2400, "cantidad": 12}]}

    monkeypatch.setattr(db, "usuario", usuario)
    monkeypatch.setattr(db, "dominios_autorizados", lambda cod: USUARIOS[cod]["dominios"] if cod in USUARIOS else None)
    monkeypatch.setattr(db, "dominios", lambda: {"SIN": "Siniestros", "FIN": "Finanzas", "SEG": "Seguros"})
    monkeypatch.setattr(db, "ejecutar", ejecutar)
    monkeypatch.setattr(db, "registrar_consulta", lambda *a, **k: registro["auditoria"].append((a, k)))
    monkeypatch.setattr(catalogo, "obtener", lambda: cat)

    def ia_falsa(pregunta, *args):
        registro["ia"].append(pregunta)
        return registro.get("plan", plan()), {"entrada": 1000, "salida": 150}

    monkeypatch.setattr(main, "interpretar_con_ia", ia_falsa)
    return TestClient(main.app), registro


def _login(cliente, usuario="USR_SIN", clave="1234"):
    return cliente.post("/api/sesion", json={"usuario": usuario, "clave": clave})


def _auth(usuario="USR_SIN"):
    return {"Authorization": f"Bearer {sesion.crear_token(usuario)}"}


# --- Inicio de sesión (RF-021) ---------------------------------------------------

def test_login_correcto_entrega_token_y_areas(api):
    cliente, _ = api
    r = _login(cliente)
    assert r.status_code == 200
    datos = r.json()
    assert sesion.leer_token(datos["token"]) == "USR_SIN"
    assert [d["codigo"] for d in datos["dominios"]] == ["SIN"]


def test_login_con_clave_incorrecta_falla(api):
    cliente, _ = api
    assert _login(cliente, clave="0000").status_code == 401


def test_usuario_inexistente_recibe_el_mismo_mensaje(api):
    cliente, _ = api
    a, b = _login(cliente, clave="0000"), _login(cliente, usuario="NO_EXISTE")
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()  # no revela qué usuarios existen


# --- Protección de endpoints -------------------------------------------------------

def test_consulta_sin_token_se_rechaza(api):
    cliente, _ = api
    assert cliente.post("/api/consultas", json={"pregunta": "siniestros por región"}).status_code == 401


def test_consulta_con_token_falso_se_rechaza(api):
    cliente, _ = api
    r = cliente.post("/api/consultas", json={"pregunta": "x"}, headers={"Authorization": "Bearer USR_ADMIN.9999999999.firma"})
    assert r.status_code == 401


def test_pregunta_vacia_o_demasiado_larga_se_rechaza(api):
    cliente, _ = api
    assert cliente.post("/api/consultas", json={"pregunta": ""}, headers=_auth()).status_code == 422
    assert cliente.post("/api/consultas", json={"pregunta": "a" * 501}, headers=_auth()).status_code == 422


# --- Flujo completo (RF-001 a RF-011, RF-018) ------------------------------------------

def test_flujo_completo_de_una_consulta(api):
    cliente, registro = api
    r = cliente.post("/api/consultas", json={"pregunta": "Monto pagado por región"}, headers=_auth())
    assert r.status_code == 200
    datos = r.json()
    assert datos["estado"] == "validado"
    assert datos["interpretacion"]["codDominio"] == "SIN"
    assert datos["resultado"]["total"] == 2400
    assert [p["categoria"] for p in datos["resultado"]["serie"]] == ["Metropolitana", "Valparaíso"]
    # El SQL lo armó el backend, solo con SELECT, y la consulta quedó auditada como validada
    assert registro["sql"] and all(sql.startswith("SELECT") for sql, _ in registro["sql"])
    assert registro["auditoria"][-1][0][2] == "validado"


def test_escritura_se_bloquea_sin_llamar_a_la_ia(api):
    cliente, registro = api
    r = cliente.post("/api/consultas", json={"pregunta": "Borra los siniestros de abril"}, headers=_auth())
    assert r.json()["estado"] == "rechazado"
    assert registro["ia"] == []      # no se gastaron tokens
    assert registro["sql"] == []     # no llegó nada a la base
    assert registro["auditoria"][-1][0][2] == "rechazado"


def test_area_no_autorizada_se_rechaza_sin_tocar_la_base(api):
    cliente, registro = api
    registro["plan"] = plan(dominio="FIN", metrica="prima_total")
    r = cliente.post("/api/consultas", json={"pregunta": "primas por región"}, headers=_auth("USR_SIN"))
    assert r.json()["estado"] == "rechazado"
    assert "no autorizado" in r.json()["motivo"]
    assert registro["sql"] == []


def test_reporte_con_otros_filtros_no_usa_la_ia(api):
    cliente, registro = api
    cuerpo = {"pregunta": "Monto pagado por región", "plan": plan(hasta="2026-04").model_dump()}
    r = cliente.post("/api/reportes", json=cuerpo, headers=_auth())
    assert r.status_code == 200 and r.json()["estado"] == "validado"
    assert registro["ia"] == []
