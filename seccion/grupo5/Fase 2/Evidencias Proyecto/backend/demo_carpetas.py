"""Deja carpetas compartidas de ejemplo para la demo (requiere el backend corriendo).

    python demo_carpetas.py            # en backend/, con el venv activo

Usa la API, así que pasa por las mismas validaciones y permisos que la pantalla:
- USR_ADMIN es dueño de «Comité de Siniestros»: USR_SIN la edita y USR_FIN solo la lee,
  salvo el dashboard «Resumen ejecutivo», que USR_FIN puede editar (permiso por dashboard).
  Ese dashboard mezcla áreas: cada persona ve bloqueados los gráficos de áreas que no consulta.
- USR_FIN es dueño de «Primas y comisiones» y la comparte con USR_ADMIN como lector, para
  que USR_ADMIN tenga algo en «Compartidas conmigo».
Si una carpeta con ese nombre ya existe para su dueño, no se vuelve a crear.
Los tokens se firman con SESSION_SECRET de .env (el mismo del backend).
"""

import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv

load_dotenv()

from app import sesion  # noqa: E402

API = os.getenv("DEMO_API", "http://127.0.0.1:8000")


def plan(dominio: str, metrica: str, agrupar_por: str, tipo: str) -> dict:
    return {"accion": "consultar", "motivo_rechazo": "", "dominio": dominio, "titulo": "", "metrica": metrica,
            "agrupar_por": agrupar_por, "filtros": [], "desde": "", "hasta": "", "tipo_salida": tipo, "comparar": ""}


CARPETAS = [
    {
        "dueno": "USR_ADMIN",
        "nombre": "Comité de Siniestros",
        "descripcion": "Seguimiento mensual para el comité. Siniestros edita; Finanzas solo lee.",
        "miembros": {"USR_SIN": "EDITOR", "USR_FIN": "LECTOR"},
        "dashboards": [
            {
                "nombre": "Seguimiento de siniestros",
                "descripcion": "Cuántos siniestros llegan, dónde y de qué tipo se paga más.",
                "graficos": [
                    ("Siniestros por mes", plan("SIN", "cantidad_siniestros", "mes", "grafico_lineas")),
                    ("Monto pagado por región", plan("SIN", "monto_pagado", "region", "grafico_mapa")),
                    ("Monto pagado por tipo de siniestro", plan("SIN", "monto_pagado", "tipo_siniestro", "grafico_barras")),
                    ("Monto denunciado por producto", plan("SIN", "monto_denunciado", "producto", "grafico_barras")),
                ],
            },
            {
                "nombre": "Resumen ejecutivo",
                "descripcion": "Siniestros, primas y cartera en una vista. Cada persona ve solo sus áreas.",
                "graficos": [
                    ("Siniestros por mes", plan("SIN", "cantidad_siniestros", "mes", "grafico_lineas")),
                    ("Prima directa neta por mes", plan("FIN", "prima_total", "mes", "grafico_lineas")),
                    ("Monto asegurado por región", plan("SEG", "monto_asegurado", "region", "grafico_barras")),
                ],
                "permisos": {"USR_FIN": "EDITOR"},
            },
        ],
    },
    {
        "dueno": "USR_FIN",
        "nombre": "Primas y comisiones",
        "descripcion": "Tablero del área de Finanzas, compartido con la administración.",
        "miembros": {"USR_ADMIN": "LECTOR"},
        "dashboards": [
            {
                "nombre": "Primas mensuales",
                "descripcion": "Evolución de la prima y su reparto por producto.",
                "graficos": [
                    ("Prima directa neta por mes", plan("FIN", "prima_total", "mes", "grafico_lineas")),
                    ("Prima directa neta por producto", plan("FIN", "prima_total", "producto", "grafico_barras")),
                    ("Comisiones por mes", plan("FIN", "comision_total", "mes", "grafico_lineas")),
                ],
            },
        ],
    },
]


def llamar(usuario: str, ruta: str, cuerpo: dict | None = None) -> dict:
    solicitud = urllib.request.Request(
        API + ruta,
        json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None,
        {"Content-Type": "application/json", "Authorization": f"Bearer {sesion.crear_token(usuario)}"},
    )
    try:
        with urllib.request.urlopen(solicitud, timeout=300) as respuesta:
            return json.load(respuesta)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{ruta} respondió {e.code}: {e.read().decode('utf-8', 'replace')}") from e


def main() -> None:
    for c in CARPETAS:
        dueno = c["dueno"]
        existentes = llamar(dueno, "/api/carpetas")["carpetas"]
        if any(x["nombre"] == c["nombre"] and x["rol"] == "PROPIETARIO" for x in existentes):
            print(f"· «{c['nombre']}» ya existe para {dueno}: no se toca")
            continue
        id_carpeta = llamar(dueno, "/api/carpetas", {"nombre": c["nombre"], "descripcion": c["descripcion"]})["id"]
        for usuario, rol in c["miembros"].items():
            llamar(dueno, f"/api/carpetas/{id_carpeta}/miembros", {"usuario": usuario, "rol": rol})
        print(f"✓ «{c['nombre']}» ({dueno}) compartida con {', '.join(f'{u} ({r.lower()})' for u, r in c['miembros'].items())}")
        for d in c["dashboards"]:
            r = llamar(dueno, "/api/dashboards", {
                "carpeta": id_carpeta, "nombre": d["nombre"], "descripcion": d["descripcion"],
                "graficos": [{"titulo": t, "plan": p} for t, p in d["graficos"]],
            })
            omitidos = r.get("omitidos") or []
            print(f"    ✓ dashboard «{d['nombre']}»: {len(d['graficos']) - len(omitidos)} gráficos"
                  + (f" (omitidos: {', '.join(o['titulo'] for o in omitidos)})" if omitidos else ""))
            for usuario, rol in d.get("permisos", {}).items():
                llamar(dueno, f"/api/dashboards/{r['id']}/permisos", {"usuario": usuario, "rol": rol})
                print(f"      · {usuario} puede {'editar' if rol == 'EDITOR' else 'solo leer'} este dashboard")


if __name__ == "__main__":
    main()
