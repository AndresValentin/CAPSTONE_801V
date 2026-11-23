-- Esquema PROPUESTO para coordinar con quien diseña la base de datos.
-- Está en SQLite para poder probar el backend sin servidor; en PostgreSQL/MySQL
-- cambian solo los tipos (INTEGER PRIMARY KEY -> SERIAL, TEXT -> VARCHAR, etc.).
-- Lo importante es el contrato: nombres de tabla/columna que usa app/consultas.py.

-- ===== Datos de negocio (solo lectura para la IA) =====

CREATE TABLE IF NOT EXISTS cliente (
    id          INTEGER PRIMARY KEY,
    rut         TEXT NOT NULL,      -- sensible: NO está en el catálogo
    nombre      TEXT NOT NULL,      -- sensible
    correo      TEXT,               -- sensible
    telefono    TEXT                -- sensible
);

CREATE TABLE IF NOT EXISTS poliza (
    id          INTEGER PRIMARY KEY,
    codigo      TEXT NOT NULL UNIQUE,          -- ej: POL-20001
    cliente_id  INTEGER NOT NULL REFERENCES cliente(id),
    producto    TEXT NOT NULL CHECK (producto IN ('Automotriz', 'Hogar', 'Salud', 'Vida'))
);

CREATE TABLE IF NOT EXISTS siniestro (
    id          INTEGER PRIMARY KEY,
    codigo      TEXT NOT NULL UNIQUE,          -- ej: SIN-1001
    poliza_id   INTEGER NOT NULL REFERENCES poliza(id),
    region      TEXT NOT NULL,
    estado      TEXT NOT NULL CHECK (estado IN ('Aprobado', 'En revisión', 'Rechazado', 'Pagado')),
    fecha       TEXT NOT NULL,                 -- AAAA-MM (en Postgres puede ser DATE)
    monto       INTEGER NOT NULL CHECK (monto > 0)
);

CREATE INDEX IF NOT EXISTS idx_siniestro_fecha ON siniestro(fecha);

-- ===== Trazabilidad (la app sí escribe aquí) =====

-- Cada pregunta hecha a la IA, aceptada o rechazada (RF-07 / RF-08)
CREATE TABLE IF NOT EXISTS consulta_log (
    id            INTEGER PRIMARY KEY,
    creada        TEXT NOT NULL DEFAULT (datetime('now')),
    pregunta      TEXT NOT NULL,
    estado        TEXT NOT NULL CHECK (estado IN ('validado', 'rechazado', 'aclaracion', 'error')),
    motivo        TEXT,
    plan_json     TEXT,          -- lo que propuso la IA
    sql_ejecutado TEXT,          -- SQL final (parametrizado) que corrió el backend
    tokens_entrada INTEGER,      -- uso de la IA, para medir el costo real por reporte
    tokens_salida  INTEGER
);

-- Historial de chats tipo Claude (hoy vive en localStorage del frontend)
CREATE TABLE IF NOT EXISTS conversacion (
    id          TEXT PRIMARY KEY,
    titulo      TEXT NOT NULL,
    creada      TEXT NOT NULL DEFAULT (datetime('now')),
    actualizada TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS mensaje (
    id              TEXT PRIMARY KEY,
    conversacion_id TEXT NOT NULL REFERENCES conversacion(id) ON DELETE CASCADE,
    rol             TEXT NOT NULL CHECK (rol IN ('usuario', 'asistente')),
    tipo            TEXT,         -- validado | rechazo | archivo | importacion | error
    texto           TEXT NOT NULL,
    consulta_id     INTEGER REFERENCES consulta_log(id),  -- el reporte que generó
    creado          TEXT NOT NULL DEFAULT (datetime('now'))
);
