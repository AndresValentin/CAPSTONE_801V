USE DB_BI_RUTA_SMART;
GO

-- Propuesta: usuario de base de datos sin login que solo puede leer las capas
-- de datos (ods y dim). El backend ejecuta las consultas de los reportes con
-- EXECUTE AS USER = 'bi_lector', así que aunque una consulta intentara
-- escribir o leer seguridad/meta, SQL Server la rechaza.
CREATE USER bi_lector WITHOUT LOGIN;
GO

GRANT SELECT ON SCHEMA::ods TO bi_lector;
GO

GRANT SELECT ON SCHEMA::dim TO bi_lector;
GO
