USE DB_BI_RUTA_SMART;
GO

CREATE TABLE meta.MET_RELACION
(
    ID_RELACION INT IDENTITY(1,1) NOT NULL,

    ID_TABLA_ORIGEN INT NOT NULL,
    ID_COLUMNA_ORIGEN INT NOT NULL,

    ID_TABLA_DESTINO INT NOT NULL,
    ID_COLUMNA_DESTINO INT NOT NULL,

    DESC_TIPO_RELACION VARCHAR(20) NOT NULL,

    FLG_DISPONIBLE_IA BIT NOT NULL
        CONSTRAINT DF_MET_RELACION_DISPONIBLE_IA
        DEFAULT (1),

    FLG_ACTIVO BIT NOT NULL
        CONSTRAINT DF_MET_RELACION_ACTIVO
        DEFAULT (1),

    CONSTRAINT PK_MET_RELACION
        PRIMARY KEY (ID_RELACION),

    CONSTRAINT UQ_MET_RELACION
        UNIQUE
        (
              ID_TABLA_ORIGEN
            , ID_COLUMNA_ORIGEN
            , ID_TABLA_DESTINO
            , ID_COLUMNA_DESTINO
        ),

    CONSTRAINT FK_MET_RELACION_ORIGEN
        FOREIGN KEY
        (
              ID_TABLA_ORIGEN
            , ID_COLUMNA_ORIGEN
        )
        REFERENCES meta.MET_COLUMNA
        (
              ID_TABLA
            , ID_COLUMNA
        ),

    CONSTRAINT FK_MET_RELACION_DESTINO
        FOREIGN KEY
        (
              ID_TABLA_DESTINO
            , ID_COLUMNA_DESTINO
        )
        REFERENCES meta.MET_COLUMNA
        (
              ID_TABLA
            , ID_COLUMNA
        ),

    CONSTRAINT CK_MET_RELACION_TIPO
        CHECK
        (
            DESC_TIPO_RELACION IN
            (
                  '1:1'
                , '1:N'
                , 'N:1'
                , 'N:N'
            )
        )
);
GO