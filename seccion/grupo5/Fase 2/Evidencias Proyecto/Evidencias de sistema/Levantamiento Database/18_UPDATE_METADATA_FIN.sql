USE DB_BI_RUTA_SMART;
GO

/* ============================================================
   ACTUALIZACION DE METADATA DEL DOMINIO FIN

   Este script incorpora:

   Nuevas columnas de ODS_FIN_PRIMA

   ODS_FIN_CUOTA_PRIMA

   Columnas de cuotas

   Relacion entre cuotas y movimientos de prima

   Tambien deshabilita para la IA los campos antiguos de pago
   que permanecen temporalmente en ODS_FIN_PRIMA.
   ============================================================ */


/* ============================================================
   1. ACTUALIZAR DESCRIPCION DE ODS_FIN_PRIMA
   ============================================================ */

UPDATE T
SET T.DESC_NEGOCIO =
    'Información de movimientos de prima, incluyendo prima directa, cedida, retenida, comisión y modalidad de cuotas.'
FROM meta.MET_TABLA T
WHERE T.DESC_SCHEMA = 'ods'
  AND T.DESC_TABLA = 'ODS_FIN_PRIMA';
GO


/* ============================================================
   2. REGISTRAR ODS_FIN_CUOTA_PRIMA
   ============================================================ */

IF NOT EXISTS
(
    SELECT 1
    FROM meta.MET_TABLA T
    WHERE T.DESC_SCHEMA = 'ods'
      AND T.DESC_TABLA = 'ODS_FIN_CUOTA_PRIMA'
)
BEGIN

    INSERT INTO meta.MET_TABLA
    (
        ID_DOMINIO,
        DESC_SCHEMA,
        DESC_TABLA,
        COD_CAPA,
        DESC_NEGOCIO,
        FLG_DISPONIBLE_IA,
        FLG_ACTIVO
    )
    SELECT
        D.ID_DOMINIO,
        'ods',
        'ODS_FIN_CUOTA_PRIMA',
        'ODS',
        'Información de cuotas asociadas a movimientos de prima, incluyendo vencimiento, importe, estado y fecha de pago.',
        1,
        1
    FROM seguridad.SEG_DOMINIO D
    WHERE D.COD_DOMINIO = 'FIN';

END;
GO


/* ============================================================
   3. REGISTRAR NUEVAS COLUMNAS DE ODS_FIN_PRIMA
   ============================================================ */

INSERT INTO meta.MET_COLUMNA
(
    ID_TABLA,
    DESC_COLUMNA,
    DESC_TIPO_DATO,
    DESC_NEGOCIO,
    FLG_ES_LLAVE,
    FLG_ES_MEDIDA,
    FLG_ES_FILTRO,
    FLG_DISPONIBLE_IA,
    FLG_ACTIVO
)
SELECT
    T.ID_TABLA,
    V.DESC_COLUMNA,
    V.DESC_TIPO_DATO,
    V.DESC_NEGOCIO,
    V.FLG_ES_LLAVE,
    V.FLG_ES_MEDIDA,
    V.FLG_ES_FILTRO,
    1,
    1
FROM
(
    VALUES
        (
            'MNT_PRIMA_DIRECTA',
            'DECIMAL(18,2)',
            'Importe total del movimiento de prima correspondiente al negocio directo.',
            0,
            1,
            0
        ),
        (
            'MNT_PRIMA_CEDIDA',
            'DECIMAL(18,2)',
            'Parte de la prima directa transferida mediante reaseguro.',
            0,
            1,
            0
        ),
        (
            'MNT_PRIMA_RETENIDA',
            'DECIMAL(18,2)',
            'Parte de la prima directa conservada por la aseguradora.',
            0,
            1,
            0
        ),
        (
            'Q_CUOTAS',
            'TINYINT',
            'Cantidad de cuotas asociadas al movimiento de prima. Las emisiones pueden tener una u once cuotas y las anulaciones no generan cuotas.',
            0,
            0,
            1
        )
) V
(
    DESC_COLUMNA,
    DESC_TIPO_DATO,
    DESC_NEGOCIO,
    FLG_ES_LLAVE,
    FLG_ES_MEDIDA,
    FLG_ES_FILTRO
)
INNER JOIN meta.MET_TABLA T
    ON T.DESC_SCHEMA = 'ods'
   AND T.DESC_TABLA = 'ODS_FIN_PRIMA'
WHERE NOT EXISTS
(
    SELECT 1
    FROM meta.MET_COLUMNA C
    WHERE C.ID_TABLA = T.ID_TABLA
      AND C.DESC_COLUMNA = V.DESC_COLUMNA
);
GO


/* ============================================================
   4. DESHABILITAR COLUMNAS ANTIGUAS PARA LA IA

   Estas columnas se mantienen temporalmente en la tabla fisica
   para conservar trazabilidad durante la migracion.

   La cobranza debe consultarse desde ODS_FIN_CUOTA_PRIMA.
   ============================================================ */

UPDATE C
SET
    C.FLG_DISPONIBLE_IA = 0,
    C.FLG_ACTIVO = 1
FROM meta.MET_COLUMNA C
INNER JOIN meta.MET_TABLA T
    ON C.ID_TABLA = T.ID_TABLA
WHERE T.DESC_SCHEMA = 'ods'
  AND T.DESC_TABLA = 'ODS_FIN_PRIMA'
  AND C.DESC_COLUMNA IN
  (
      'MNT_PRIMA',
      'DESC_ESTADO_PAGO',
      'DT_FECHA_PAGO'
  );
GO


/* ============================================================
   5. REGISTRAR COLUMNAS DE ODS_FIN_CUOTA_PRIMA
   ============================================================ */

INSERT INTO meta.MET_COLUMNA
(
    ID_TABLA,
    DESC_COLUMNA,
    DESC_TIPO_DATO,
    DESC_NEGOCIO,
    FLG_ES_LLAVE,
    FLG_ES_MEDIDA,
    FLG_ES_FILTRO,
    FLG_DISPONIBLE_IA,
    FLG_ACTIVO
)
SELECT
    T.ID_TABLA,
    V.DESC_COLUMNA,
    V.DESC_TIPO_DATO,
    V.DESC_NEGOCIO,
    V.FLG_ES_LLAVE,
    V.FLG_ES_MEDIDA,
    V.FLG_ES_FILTRO,
    1,
    1
FROM
(
    VALUES
        (
            'ID_CUOTA_PRIMA',
            'INT',
            'Identificador técnico de la cuota de prima.',
            1,
            0,
            0
        ),
        (
            'ID_MOVIMIENTO_PRIMA',
            'INT',
            'Identificador técnico del movimiento de prima asociado a la cuota.',
            1,
            0,
            0
        ),
        (
            'NRO_CUOTA',
            'TINYINT',
            'Número correlativo de la cuota dentro del movimiento de prima.',
            1,
            0,
            1
        ),
        (
            'DT_FECHA_VENCIMIENTO',
            'DATE',
            'Fecha de vencimiento de la cuota de prima.',
            0,
            0,
            1
        ),
        (
            'MNT_CUOTA',
            'DECIMAL(18,2)',
            'Importe correspondiente a la cuota de prima.',
            0,
            1,
            0
        ),
        (
            'DESC_ESTADO_CUOTA',
            'VARCHAR(20)',
            'Estado de cobranza de la cuota, pagada o pendiente.',
            0,
            0,
            1
        ),
        (
            'DT_FECHA_PAGO',
            'DATE',
            'Fecha en que se realizó el pago de la cuota.',
            0,
            0,
            1
        )
) V
(
    DESC_COLUMNA,
    DESC_TIPO_DATO,
    DESC_NEGOCIO,
    FLG_ES_LLAVE,
    FLG_ES_MEDIDA,
    FLG_ES_FILTRO
)
INNER JOIN meta.MET_TABLA T
    ON T.DESC_SCHEMA = 'ods'
   AND T.DESC_TABLA = 'ODS_FIN_CUOTA_PRIMA'
WHERE NOT EXISTS
(
    SELECT 1
    FROM meta.MET_COLUMNA C
    WHERE C.ID_TABLA = T.ID_TABLA
      AND C.DESC_COLUMNA = V.DESC_COLUMNA
);
GO


/* ============================================================
   6. REGISTRAR RELACION ENTRE CUOTA Y MOVIMIENTO
   ============================================================ */

INSERT INTO meta.MET_RELACION
(
    ID_TABLA_ORIGEN,
    ID_COLUMNA_ORIGEN,
    ID_TABLA_DESTINO,
    ID_COLUMNA_DESTINO,
    DESC_TIPO_RELACION,
    FLG_DISPONIBLE_IA,
    FLG_ACTIVO
)
SELECT
    TOG.ID_TABLA,
    COG.ID_COLUMNA,
    TDE.ID_TABLA,
    CDE.ID_COLUMNA,
    'N:1',
    1,
    1
FROM meta.MET_TABLA TOG
INNER JOIN meta.MET_COLUMNA COG
    ON COG.ID_TABLA = TOG.ID_TABLA
   AND COG.DESC_COLUMNA = 'ID_MOVIMIENTO_PRIMA'
INNER JOIN meta.MET_TABLA TDE
    ON TDE.DESC_SCHEMA = 'ods'
   AND TDE.DESC_TABLA = 'ODS_FIN_PRIMA'
INNER JOIN meta.MET_COLUMNA CDE
    ON CDE.ID_TABLA = TDE.ID_TABLA
   AND CDE.DESC_COLUMNA = 'ID_MOVIMIENTO_PRIMA'
WHERE TOG.DESC_SCHEMA = 'ods'
  AND TOG.DESC_TABLA = 'ODS_FIN_CUOTA_PRIMA'
  AND NOT EXISTS
  (
      SELECT 1
      FROM meta.MET_RELACION R
      WHERE R.ID_TABLA_ORIGEN = TOG.ID_TABLA
        AND R.ID_COLUMNA_ORIGEN = COG.ID_COLUMNA
        AND R.ID_TABLA_DESTINO = TDE.ID_TABLA
        AND R.ID_COLUMNA_DESTINO = CDE.ID_COLUMNA
  );
GO


/* ============================================================
   7. VALIDAR TABLAS DEL DOMINIO FIN
   ============================================================ */

SELECT
    D.COD_DOMINIO,
    T.DESC_SCHEMA,
    T.DESC_TABLA,
    T.DESC_NEGOCIO,
    T.FLG_DISPONIBLE_IA,
    T.FLG_ACTIVO
FROM meta.MET_TABLA T
INNER JOIN seguridad.SEG_DOMINIO D
    ON T.ID_DOMINIO = D.ID_DOMINIO
WHERE D.COD_DOMINIO = 'FIN'
ORDER BY T.DESC_TABLA;
GO


/* ============================================================
   8. VALIDAR COLUMNAS DEL DOMINIO FIN
   ============================================================ */

SELECT
    T.DESC_TABLA,
    C.DESC_COLUMNA,
    C.DESC_TIPO_DATO,
    C.DESC_NEGOCIO,
    C.FLG_ES_LLAVE,
    C.FLG_ES_MEDIDA,
    C.FLG_ES_FILTRO,
    C.FLG_DISPONIBLE_IA,
    C.FLG_ACTIVO
FROM meta.MET_COLUMNA C
INNER JOIN meta.MET_TABLA T
    ON C.ID_TABLA = T.ID_TABLA
INNER JOIN seguridad.SEG_DOMINIO D
    ON T.ID_DOMINIO = D.ID_DOMINIO
WHERE D.COD_DOMINIO = 'FIN'
ORDER BY
    T.DESC_TABLA,
    C.ID_COLUMNA;
GO


/* ============================================================
   9. VALIDAR RELACION DE CUOTAS
   ============================================================ */

SELECT
    TOG.DESC_TABLA AS TABLA_ORIGEN,
    COG.DESC_COLUMNA AS COLUMNA_ORIGEN,
    R.DESC_TIPO_RELACION,
    TDE.DESC_TABLA AS TABLA_DESTINO,
    CDE.DESC_COLUMNA AS COLUMNA_DESTINO,
    R.FLG_DISPONIBLE_IA,
    R.FLG_ACTIVO
FROM meta.MET_RELACION R
INNER JOIN meta.MET_TABLA TOG
    ON R.ID_TABLA_ORIGEN = TOG.ID_TABLA
INNER JOIN meta.MET_COLUMNA COG
    ON R.ID_COLUMNA_ORIGEN = COG.ID_COLUMNA
INNER JOIN meta.MET_TABLA TDE
    ON R.ID_TABLA_DESTINO = TDE.ID_TABLA
INNER JOIN meta.MET_COLUMNA CDE
    ON R.ID_COLUMNA_DESTINO = CDE.ID_COLUMNA
WHERE TOG.DESC_TABLA = 'ODS_FIN_CUOTA_PRIMA'
  AND TDE.DESC_TABLA = 'ODS_FIN_PRIMA';
GO