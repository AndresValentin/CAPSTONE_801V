"""Crea db/siniestros.db con el esquema y datos sintéticos (RN-06: sin datos reales).

Uso:  python db/seed.py
Se reemplaza cuando exista la base de datos real.
"""

import random
import sqlite3
from pathlib import Path

AQUI = Path(__file__).parent
DB_PATH = AQUI / "siniestros.db"

PRODUCTOS = ["Automotriz", "Hogar", "Salud", "Vida"]
REGIONES = ["Metropolitana", "Valparaíso", "Biobío", "Los Lagos", "Antofagasta"]
ESTADOS = ["Aprobado", "En revisión", "Rechazado", "Pagado"]
MESES = ["2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03"]


def main() -> None:
    DB_PATH.unlink(missing_ok=True)
    rnd = random.Random(42)

    with sqlite3.connect(DB_PATH) as con:
        con.executescript((AQUI / "schema.sql").read_text(encoding="utf-8"))

        for i in range(1, 221):
            con.execute(
                "INSERT INTO cliente (id, rut, nombre, correo, telefono) VALUES (?, ?, ?, ?, ?)",
                (i, f"{10_000_000 + i}-K", f"Cliente {i}", f"cliente{i}@ejemplo.cl", f"+5690000{i:04d}"),
            )

        for i in range(1, 91):
            con.execute(
                "INSERT INTO poliza (id, codigo, cliente_id, producto) VALUES (?, ?, ?, ?)",
                (i, f"POL-{20000 + i}", rnd.randint(1, 220), rnd.choice(PRODUCTOS)),
            )
            con.execute(
                "INSERT INTO siniestro (id, codigo, poliza_id, region, estado, fecha, monto) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (i, f"SIN-{1000 + i}", i, rnd.choice(REGIONES), rnd.choice(ESTADOS),
                 rnd.choice(MESES), rnd.randint(150_000, 4_650_000)),
            )

    print(f"Base de datos creada en {DB_PATH}")


if __name__ == "__main__":
    main()
