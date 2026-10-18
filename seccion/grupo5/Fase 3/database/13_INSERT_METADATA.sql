USE DB_BI_RUTA_SMART;
GO


/* ============================================================
   METADATA DE TABLAS
   ============================================================ */

INSERT INTO meta.MET_TABLA
(
      ID_DOMINIO
    , DESC_SCHEMA
    , DESC_TABLA
    , COD_CAPA
    , DESC_NEGOCIO
    , FLG_DISPONIBLE_IA
    , FLG_ACTIVO
)
SELECT
      D.ID_DOMINIO
    , V.DESC_SCHEMA
    , V.DESC_TABLA
    , V.COD_CAPA
    , V.DESC_NEGOCIO
    , 1
    , 1
FROM
(
    VALUES
      ('SEG', 'ods', 'ODS_SEG_CLIENTE', 'ODS',
       'Información de clientes asociados a seguros.')

    , ('SEG', 'ods', 'ODS_SEG_SEGURO', 'ODS',
       'Información de pólizas, certificados e ítems asegurados.')

    , ('FIN', 'ods', 'ODS_FIN_PRIMA', 'ODS',
       'Información de movimientos de prima asociados a ítems asegurados.')

    , ('SIN', 'ods', 'ODS_SIN_SINIESTRO', 'ODS',
       'Información de siniestros asociados a ítems asegurados.')
) V
(
      COD_DOMINIO
    , DESC_SCHEMA
    , DESC_TABLA
    , COD_CAPA
    , DESC_NEGOCIO
)

INNER JOIN seguridad.SEG_DOMINIO D
    ON D.COD_DOMINIO = V.COD_DOMINIO;
GO

/* ============================================================
   METADATA DE COLUMNAS - ODS_FIN_PRIMA
   ============================================================ */

INSERT INTO meta.MET_COLUMNA
(
      ID_TABLA
    , DESC_COLUMNA
    , DESC_TIPO_DATO
    , DESC_NEGOCIO
    , FLG_ES_LLAVE
    , FLG_ES_MEDIDA
    , FLG_ES_FILTRO
    , FLG_DISPONIBLE_IA
    , FLG_ACTIVO
)
SELECT
      T.ID_TABLA
    , V.DESC_COLUMNA
    , V.DESC_TIPO_DATO
    , V.DESC_NEGOCIO
    , V.FLG_ES_LLAVE
    , V.FLG_ES_MEDIDA
    , V.FLG_ES_FILTRO
    , 1
    , 1
FROM
(
    VALUES
      ('ID_MOVIMIENTO_PRIMA', 'INT',
       'Identificador técnico del movimiento de prima.',
       1, 0, 0)

    , ('ID_ITEM', 'INT',
       'Identificador técnico del ítem asegurado asociado al movimiento de prima.',
       1, 0, 0)

    , ('NRO_MOVIMIENTO', 'INT',
       'Número correlativo del movimiento dentro del ítem asegurado.',
       1, 0, 1)

    , ('DT_FECHA_MOVIMIENTO', 'DATE',
       'Fecha en que se registra el movimiento de prima.',
       0, 0, 1)

    , ('DESC_TIPO_MOVIMIENTO', 'VARCHAR(30)',
       'Tipo de movimiento de prima, por ejemplo emisión o anulación.',
       0, 0, 1)

    , ('MNT_PRIMA', 'DECIMAL(18,2)',
       'Monto asociado al movimiento de prima.',
       0, 1, 0)

    , ('MNT_COMISION', 'DECIMAL(18,2)',
       'Monto de comisión asociado al movimiento de prima.',
       0, 1, 0)

    , ('DESC_ESTADO_PAGO', 'VARCHAR(30)',
       'Estado de pago asociado al movimiento de prima.',
       0, 0, 1)

    , ('DT_FECHA_PAGO', 'DATE',
       'Fecha en que se realizó el pago del movimiento de prima.',
       0, 0, 1)

) V
(
      DESC_COLUMNA
    , DESC_TIPO_DATO
    , DESC_NEGOCIO
    , FLG_ES_LLAVE
    , FLG_ES_MEDIDA
    , FLG_ES_FILTRO
)

INNER JOIN meta.MET_TABLA T
    ON T.DESC_SCHEMA = 'ods'
   AND T.DESC_TABLA = 'ODS_FIN_PRIMA';
GO

/* ============================================================
   METADATA DE COLUMNAS - ODS_SEG_CLIENTE
   ============================================================ */

INSERT INTO meta.MET_COLUMNA
(
      ID_TABLA
    , DESC_COLUMNA
    , DESC_TIPO_DATO
    , DESC_NEGOCIO
    , FLG_ES_LLAVE
    , FLG_ES_MEDIDA
    , FLG_ES_FILTRO
    , FLG_DISPONIBLE_IA
    , FLG_ACTIVO
)
SELECT
      T.ID_TABLA
    , V.DESC_COLUMNA
    , V.DESC_TIPO_DATO
    , V.DESC_NEGOCIO
    , V.FLG_ES_LLAVE
    , V.FLG_ES_MEDIDA
    , V.FLG_ES_FILTRO
    , 1
    , 1
FROM
(
    VALUES
      ('ID_CLIENTE', 'INT',
       'Identificador técnico del cliente.',
       1, 0, 0)

    , ('COD_CLIENTE', 'VARCHAR(20)',
       'Código identificador del cliente.',
       1, 0, 1)

    , ('DESC_TIPO_CLIENTE', 'VARCHAR(20)',
       'Tipo de cliente, por ejemplo persona o empresa.',
       0, 0, 1)

    , ('DESC_SEGMENTO', 'VARCHAR(50)',
       'Segmento comercial asociado al cliente.',
       0, 0, 1)

    , ('DESC_REGION', 'VARCHAR(100)',
       'Región asociada al cliente.',
       0, 0, 1)

) V
(
      DESC_COLUMNA
    , DESC_TIPO_DATO
    , DESC_NEGOCIO
    , FLG_ES_LLAVE
    , FLG_ES_MEDIDA
    , FLG_ES_FILTRO
)

INNER JOIN meta.MET_TABLA T
    ON T.DESC_SCHEMA = 'ods'
   AND T.DESC_TABLA = 'ODS_SEG_CLIENTE';
GO

/* ============================================================
   METADATA DE COLUMNAS - ODS_SEG_SEGURO
   ============================================================ */

INSERT INTO meta.MET_COLUMNA
(
      ID_TABLA
    , DESC_COLUMNA
    , DESC_TIPO_DATO
    , DESC_NEGOCIO
    , FLG_ES_LLAVE
    , FLG_ES_MEDIDA
    , FLG_ES_FILTRO
    , FLG_DISPONIBLE_IA
    , FLG_ACTIVO
)
SELECT
      T.ID_TABLA
    , V.DESC_COLUMNA
    , V.DESC_TIPO_DATO
    , V.DESC_NEGOCIO
    , V.FLG_ES_LLAVE
    , V.FLG_ES_MEDIDA
    , V.FLG_ES_FILTRO
    , 1
    , 1
FROM
(
    VALUES
      ('ID_ITEM', 'INT',
       'Identificador técnico del ítem asegurado.',
       1, 0, 0)

    , ('COD_POLIZA', 'VARCHAR(20)',
       'Código identificador de la póliza.',
       1, 0, 1)

    , ('COD_CERTIFICADO', 'INT',
       'Número de certificado asociado a la póliza.',
       1, 0, 1)

    , ('ID_CLIENTE', 'INT',
       'Identificador técnico del cliente asociado al ítem asegurado.',
       1, 0, 0)

    , ('COD_PRODUCTO', 'VARCHAR(20)',
       'Código del producto asociado al ítem asegurado.',
       0, 0, 1)

    , ('DESC_PRODUCTO', 'VARCHAR(100)',
       'Nombre del producto asociado al ítem asegurado.',
       0, 0, 1)

    , ('DESC_REGION', 'VARCHAR(100)',
       'Región asociada al ítem asegurado.',
       0, 0, 1)

    , ('DT_FECHA_EMISION', 'DATE',
       'Fecha de emisión de la póliza.',
       0, 0, 1)

    , ('DT_FECHA_INICIO_VIGENCIA', 'DATE',
       'Fecha de inicio de vigencia de la cobertura.',
       0, 0, 1)

    , ('DT_FECHA_FIN_VIGENCIA', 'DATE',
       'Fecha de término de vigencia de la cobertura.',
       0, 0, 1)

    , ('DESC_ESTADO_POLIZA', 'VARCHAR(30)',
       'Estado de la póliza.',
       0, 0, 1)

    , ('MNT_MONTO_ASEGURADO', 'DECIMAL(18,2)',
       'Monto asegurado asociado al ítem.',
       0, 1, 0)

) V
(
      DESC_COLUMNA
    , DESC_TIPO_DATO
    , DESC_NEGOCIO
    , FLG_ES_LLAVE
    , FLG_ES_MEDIDA
    , FLG_ES_FILTRO
)

INNER JOIN meta.MET_TABLA T
    ON T.DESC_SCHEMA = 'ods'
   AND T.DESC_TABLA = 'ODS_SEG_SEGURO';
GO

/* ============================================================
   METADATA DE COLUMNAS - ODS_SIN_SINIESTRO
   ============================================================ */

INSERT INTO meta.MET_COLUMNA
(
      ID_TABLA
    , DESC_COLUMNA
    , DESC_TIPO_DATO
    , DESC_NEGOCIO
    , FLG_ES_LLAVE
    , FLG_ES_MEDIDA
    , FLG_ES_FILTRO
    , FLG_DISPONIBLE_IA
    , FLG_ACTIVO
)
SELECT
      T.ID_TABLA
    , V.DESC_COLUMNA
    , V.DESC_TIPO_DATO
    , V.DESC_NEGOCIO
    , V.FLG_ES_LLAVE
    , V.FLG_ES_MEDIDA
    , V.FLG_ES_FILTRO
    , 1
    , 1
FROM
(
    VALUES
      ('ID_SINIESTRO', 'INT',
       'Identificador técnico del siniestro.',
       1, 0, 0)

    , ('COD_SINIESTRO', 'VARCHAR(20)',
       'Código identificador del siniestro.',
       1, 0, 1)

    , ('ID_ITEM', 'INT',
       'Identificador técnico del ítem asegurado asociado al siniestro.',
       1, 0, 0)

    , ('DT_FECHA_OCURRENCIA', 'DATE',
       'Fecha en que ocurrió el siniestro.',
       0, 0, 1)

    , ('DT_FECHA_DENUNCIO', 'DATE',
       'Fecha en que el siniestro fue denunciado.',
       0, 0, 1)

    , ('DESC_TIPO_SINIESTRO', 'VARCHAR(50)',
       'Tipo de siniestro registrado.',
       0, 0, 1)

    , ('DESC_ESTADO_SINIESTRO', 'VARCHAR(30)',
       'Estado actual del siniestro.',
       0, 0, 1)

    , ('MNT_DENUNCIADO', 'DECIMAL(18,2)',
       'Monto denunciado asociado al siniestro.',
       0, 1, 0)

    , ('MNT_RESERVA', 'DECIMAL(18,2)',
       'Monto de reserva asociado al siniestro.',
       0, 1, 0)

    , ('MNT_PAGADO', 'DECIMAL(18,2)',
       'Monto pagado asociado al siniestro.',
       0, 1, 0)

    , ('MNT_RECUPERADO', 'DECIMAL(18,2)',
       'Monto recuperado asociado al siniestro.',
       0, 1, 0)

) V
(
      DESC_COLUMNA
    , DESC_TIPO_DATO
    , DESC_NEGOCIO
    , FLG_ES_LLAVE
    , FLG_ES_MEDIDA
    , FLG_ES_FILTRO
)

INNER JOIN meta.MET_TABLA T
    ON T.DESC_SCHEMA = 'ods'
   AND T.DESC_TABLA = 'ODS_SIN_SINIESTRO';
GO

/* ============================================================
   METADATA DE RELACIONES
   ============================================================ */

INSERT INTO meta.MET_RELACION
(
      ID_TABLA_ORIGEN
    , ID_COLUMNA_ORIGEN
    , ID_TABLA_DESTINO
    , ID_COLUMNA_DESTINO
    , DESC_TIPO_RELACION
    , FLG_DISPONIBLE_IA
    , FLG_ACTIVO
)

SELECT
      TOG.ID_TABLA
    , COG.ID_COLUMNA
    , TDE.ID_TABLA
    , CDE.ID_COLUMNA
    , V.DESC_TIPO_RELACION
    , 1
    , 1
FROM
(
    VALUES

      ('ODS_SEG_SEGURO', 'ID_CLIENTE',
       'ODS_SEG_CLIENTE', 'ID_CLIENTE',
       'N:1')

    , ('ODS_FIN_PRIMA', 'ID_ITEM',
       'ODS_SEG_SEGURO', 'ID_ITEM',
       'N:1')

    , ('ODS_SIN_SINIESTRO', 'ID_ITEM',
       'ODS_SEG_SEGURO', 'ID_ITEM',
       'N:1')

) V
(
      TABLA_ORIGEN
    , COLUMNA_ORIGEN
    , TABLA_DESTINO
    , COLUMNA_DESTINO
    , DESC_TIPO_RELACION
)

INNER JOIN meta.MET_TABLA TOG
    ON TOG.DESC_TABLA = V.TABLA_ORIGEN

INNER JOIN meta.MET_COLUMNA COG
    ON COG.ID_TABLA = TOG.ID_TABLA
   AND COG.DESC_COLUMNA = V.COLUMNA_ORIGEN

INNER JOIN meta.MET_TABLA TDE
    ON TDE.DESC_TABLA = V.TABLA_DESTINO

INNER JOIN meta.MET_COLUMNA CDE
    ON CDE.ID_TABLA = TDE.ID_TABLA
   AND CDE.DESC_COLUMNA = V.COLUMNA_DESTINO;
GO