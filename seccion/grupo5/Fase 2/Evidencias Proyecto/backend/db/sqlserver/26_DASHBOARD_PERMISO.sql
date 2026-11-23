USE DB_BI_RUTA_SMART;
GO

-- Propuesta: permiso por dashboard (requiere 25_CREATE_DASHBOARDS.sql).
--
-- El rol de un miembro vale para toda la carpeta. Esta tabla guarda las
-- excepciones: por ejemplo, Ana es lectora de la carpeta "Comité" pero puede
-- editar el dashboard "Siniestros Q4", o un editor solo puede leer "Cierre anual".
-- Solo aplica a miembros de la carpeta: quitar a alguien de la carpeta borra sus
-- excepciones (lo hace el backend) y el propietario siempre puede todo.

CREATE TABLE app.DASHBOARD_PERMISO
(
    ID_DASHBOARD INT NOT NULL,
    ID_USUARIO INT NOT NULL,
    COD_ROL VARCHAR(10) NOT NULL,
    DT_ASIGNADO DATETIME2(0) NOT NULL
        CONSTRAINT DF_DASHBOARD_PERMISO_DT DEFAULT (SYSDATETIME()),

    CONSTRAINT PK_DASHBOARD_PERMISO PRIMARY KEY (ID_DASHBOARD, ID_USUARIO),
    CONSTRAINT FK_DASHBOARD_PERMISO_DASHBOARD FOREIGN KEY (ID_DASHBOARD)
        REFERENCES app.DASHBOARD (ID_DASHBOARD) ON DELETE CASCADE,
    CONSTRAINT FK_DASHBOARD_PERMISO_USUARIO FOREIGN KEY (ID_USUARIO)
        REFERENCES seguridad.SEG_USUARIO (ID_USUARIO),
    CONSTRAINT CK_DASHBOARD_PERMISO_ROL CHECK (COD_ROL IN ('LECTOR', 'EDITOR'))
);
GO
