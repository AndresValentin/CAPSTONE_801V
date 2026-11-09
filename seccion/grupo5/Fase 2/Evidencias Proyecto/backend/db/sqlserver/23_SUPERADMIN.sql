USE DB_BI_RUTA_SMART;
GO

-- Quien tenga esta marca puede crear y editar usuarios. Se puede ejecutar más de una vez.
-- Para designar al primero:
--   UPDATE seguridad.SEG_USUARIO SET FLG_SUPERADMIN = 1 WHERE COD_USUARIO = '...';
IF COL_LENGTH('seguridad.SEG_USUARIO', 'FLG_SUPERADMIN') IS NULL
    ALTER TABLE seguridad.SEG_USUARIO
        ADD FLG_SUPERADMIN BIT NOT NULL
        CONSTRAINT DF_SEG_USUARIO_SUPERADMIN DEFAULT (0);
GO
