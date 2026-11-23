USE DB_BI_RUTA_SMART;
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

/* ============================================================
   AMPLIACION DEL MODELO DE PRIMAS

   Este script incorpora:

   Prima directa
   Prima cedida
   Prima retenida
   Cantidad de cuotas

   Reglas principales:

   Prima directa = prima cedida + prima retenida

   Las emisiones pueden tener 1 u 11 cuotas.

   Las anulaciones no generan un nuevo plan de cuotas,
   por lo tanto tienen Q_CUOTAS igual a 0.

   Los importes nuevos se almacenan como valores positivos.
   El tipo de movimiento determina si el importe suma o resta
   en las consultas analiticas.
   ============================================================ */

BEGIN TRY

    BEGIN TRANSACTION;

    /* ========================================================
       1. AGREGAR NUEVAS COLUMNAS
       ======================================================== */

    IF COL_LENGTH
    (
        'ods.ODS_FIN_PRIMA',
        'MNT_PRIMA_DIRECTA'
    ) IS NULL
    BEGIN

        EXEC sys.sp_executesql
        N'
            ALTER TABLE ods.ODS_FIN_PRIMA
            ADD MNT_PRIMA_DIRECTA DECIMAL(18,2) NULL;
        ';

    END;


    IF COL_LENGTH
    (
        'ods.ODS_FIN_PRIMA',
        'MNT_PRIMA_CEDIDA'
    ) IS NULL
    BEGIN

        EXEC sys.sp_executesql
        N'
            ALTER TABLE ods.ODS_FIN_PRIMA
            ADD MNT_PRIMA_CEDIDA DECIMAL(18,2) NULL;
        ';

    END;


    IF COL_LENGTH
    (
        'ods.ODS_FIN_PRIMA',
        'MNT_PRIMA_RETENIDA'
    ) IS NULL
    BEGIN

        EXEC sys.sp_executesql
        N'
            ALTER TABLE ods.ODS_FIN_PRIMA
            ADD MNT_PRIMA_RETENIDA DECIMAL(18,2) NULL;
        ';

    END;


    IF COL_LENGTH
    (
        'ods.ODS_FIN_PRIMA',
        'Q_CUOTAS'
    ) IS NULL
    BEGIN

        EXEC sys.sp_executesql
        N'
            ALTER TABLE ods.ODS_FIN_PRIMA
            ADD Q_CUOTAS TINYINT NULL;
        ';

    END;


    /* ========================================================
       2. VALIDAR PRODUCTOS ANTES DE LA MIGRACION
       ======================================================== */

    IF EXISTS
    (
        SELECT 1
        FROM ods.ODS_FIN_PRIMA AS P

        INNER JOIN ods.ODS_SEG_SEGURO AS S
            ON P.ID_ITEM = S.ID_ITEM

        WHERE S.COD_PRODUCTO NOT IN
        (
            'AUTO',
            'HOGAR',
            'PYME',
            'EMP'
        )
    )
    BEGIN

        RAISERROR
        (
            'Existen productos sin una regla de cesion definida.',
            16,
            1
        );

    END;


    /* ========================================================
       3. CALCULAR PRIMA DIRECTA, CEDIDA Y RETENIDA

       Porcentajes utilizados para los datos iniciales:

       AUTO    20 por ciento cedido
       HOGAR   25 por ciento cedido
       PYME    30 por ciento cedido
       EMP     40 por ciento cedido
       ======================================================== */

    EXEC sys.sp_executesql
    N'
        UPDATE P
        SET
            P.MNT_PRIMA_DIRECTA =
                ABS(P.MNT_PRIMA),

            P.MNT_PRIMA_CEDIDA =
                CASE S.COD_PRODUCTO
                    WHEN ''AUTO''
                        THEN ROUND(ABS(P.MNT_PRIMA) * 0.20, 2)

                    WHEN ''HOGAR''
                        THEN ROUND(ABS(P.MNT_PRIMA) * 0.25, 2)

                    WHEN ''PYME''
                        THEN ROUND(ABS(P.MNT_PRIMA) * 0.30, 2)

                    WHEN ''EMP''
                        THEN ROUND(ABS(P.MNT_PRIMA) * 0.40, 2)
                END,

            P.MNT_PRIMA_RETENIDA =
                ABS(P.MNT_PRIMA)
                -
                CASE S.COD_PRODUCTO
                    WHEN ''AUTO''
                        THEN ROUND(ABS(P.MNT_PRIMA) * 0.20, 2)

                    WHEN ''HOGAR''
                        THEN ROUND(ABS(P.MNT_PRIMA) * 0.25, 2)

                    WHEN ''PYME''
                        THEN ROUND(ABS(P.MNT_PRIMA) * 0.30, 2)

                    WHEN ''EMP''
                        THEN ROUND(ABS(P.MNT_PRIMA) * 0.40, 2)
                END

        FROM ods.ODS_FIN_PRIMA AS P

        INNER JOIN ods.ODS_SEG_SEGURO AS S
            ON P.ID_ITEM = S.ID_ITEM;
    ';


    /* ========================================================
       4. ASIGNAR CANTIDAD DE CUOTAS

       Las emisiones pares se pagan en una cuota.

       Las emisiones impares se pagan en once cuotas.

       Las anulaciones no generan un nuevo plan de cuotas.
       ======================================================== */

    EXEC sys.sp_executesql
    N'
        UPDATE ods.ODS_FIN_PRIMA
        SET Q_CUOTAS =
            CASE
                WHEN DESC_TIPO_MOVIMIENTO = ''ANULACION''
                    THEN 0

                WHEN ID_MOVIMIENTO_PRIMA % 2 = 0
                    THEN 1

                ELSE 11
            END;
    ';


        /* ========================================================
       5. VALIDAR QUE LA MIGRACION ESTE COMPLETA

       Las validaciones utilizan SQL dinamico porque las
       columnas fueron creadas durante esta misma ejecucion.
       ======================================================== */

    EXEC sys.sp_executesql
    N'
        IF EXISTS
        (
            SELECT 1
            FROM ods.ODS_FIN_PRIMA
            WHERE MNT_PRIMA_DIRECTA IS NULL
               OR MNT_PRIMA_CEDIDA IS NULL
               OR MNT_PRIMA_RETENIDA IS NULL
               OR Q_CUOTAS IS NULL
        )
        BEGIN
            RAISERROR
            (
                ''La migracion de primas contiene registros incompletos.'',
                16,
                1
            );
        END;


        IF EXISTS
        (
            SELECT 1
            FROM ods.ODS_FIN_PRIMA
            WHERE MNT_PRIMA_DIRECTA
                  !=
                  MNT_PRIMA_CEDIDA + MNT_PRIMA_RETENIDA
        )
        BEGIN
            RAISERROR
            (
                ''La prima directa no coincide con la suma de prima cedida y retenida.'',
                16,
                1
            );
        END;


        IF EXISTS
        (
            SELECT 1
            FROM ods.ODS_FIN_PRIMA
            WHERE
                (
                    DESC_TIPO_MOVIMIENTO = ''EMISION''
                    AND Q_CUOTAS NOT IN (1, 11)
                )
                OR
                (
                    DESC_TIPO_MOVIMIENTO = ''ANULACION''
                    AND Q_CUOTAS != 0
                )
                OR DESC_TIPO_MOVIMIENTO NOT IN
                (
                    ''EMISION'',
                    ''ANULACION''
                )
        )
        BEGIN
            RAISERROR
            (
                ''Existen movimientos con una cantidad de cuotas no permitida.'',
                16,
                1
            );
        END;


        IF EXISTS
        (
            SELECT 1
            FROM ods.ODS_FIN_PRIMA
            WHERE SIGN(MNT_PRIMA_DIRECTA) = -1
               OR SIGN(MNT_PRIMA_CEDIDA) = -1
               OR SIGN(MNT_PRIMA_RETENIDA) = -1
        )
        BEGIN
            RAISERROR
            (
                ''Existen componentes de prima con valores negativos.'',
                16,
                1
            );
        END;
    ';



    /* ========================================================
       6. CONVERTIR COLUMNAS A NOT NULL
       ======================================================== */

    EXEC sys.sp_executesql
    N'
        ALTER TABLE ods.ODS_FIN_PRIMA
        ALTER COLUMN MNT_PRIMA_DIRECTA
        DECIMAL(18,2) NOT NULL;

        ALTER TABLE ods.ODS_FIN_PRIMA
        ALTER COLUMN MNT_PRIMA_CEDIDA
        DECIMAL(18,2) NOT NULL;

        ALTER TABLE ods.ODS_FIN_PRIMA
        ALTER COLUMN MNT_PRIMA_RETENIDA
        DECIMAL(18,2) NOT NULL;

        ALTER TABLE ods.ODS_FIN_PRIMA
        ALTER COLUMN Q_CUOTAS
        TINYINT NOT NULL;
    ';


    /* ========================================================
       7. RESTRINGIR LOS MONTOS
       ======================================================== */

    IF OBJECT_ID
    (
        'ods.CK_ODS_FIN_PRIMA_MONTOS',
        'C'
    ) IS NULL
    BEGIN

        EXEC sys.sp_executesql
        N'
            ALTER TABLE ods.ODS_FIN_PRIMA
            ADD CONSTRAINT CK_ODS_FIN_PRIMA_MONTOS
            CHECK
            (
                SIGN(MNT_PRIMA_DIRECTA) IN (0, 1)
                AND SIGN(MNT_PRIMA_CEDIDA) IN (0, 1)
                AND SIGN(MNT_PRIMA_RETENIDA) IN (0, 1)
            );
        ';

    END;


    /* ========================================================
       8. PROTEGER LA COMPOSICION DE LA PRIMA
       ======================================================== */

    IF OBJECT_ID
    (
        'ods.CK_ODS_FIN_PRIMA_COMPOSICION',
        'C'
    ) IS NULL
    BEGIN

        EXEC sys.sp_executesql
        N'
            ALTER TABLE ods.ODS_FIN_PRIMA
            ADD CONSTRAINT CK_ODS_FIN_PRIMA_COMPOSICION
            CHECK
            (
                MNT_PRIMA_DIRECTA =
                MNT_PRIMA_CEDIDA + MNT_PRIMA_RETENIDA
            );
        ';

    END;


    /* ========================================================
       9. PROTEGER LA CANTIDAD DE CUOTAS
       ======================================================== */

    IF OBJECT_ID
    (
        'ods.CK_ODS_FIN_PRIMA_CUOTAS',
        'C'
    ) IS NULL
    BEGIN

        EXEC sys.sp_executesql
        N'
            ALTER TABLE ods.ODS_FIN_PRIMA
            ADD CONSTRAINT CK_ODS_FIN_PRIMA_CUOTAS
            CHECK
            (
                (
                    DESC_TIPO_MOVIMIENTO = ''EMISION''
                    AND Q_CUOTAS IN (1, 11)
                )
                OR
                (
                    DESC_TIPO_MOVIMIENTO = ''ANULACION''
                    AND Q_CUOTAS = 0
                )
            );
        ';

    END;


    /* ========================================================
       10. PROTEGER LOS TIPOS DE MOVIMIENTO
       ======================================================== */

    IF OBJECT_ID
    (
        'ods.CK_ODS_FIN_PRIMA_TIPO_MOVIMIENTO',
        'C'
    ) IS NULL
    BEGIN

        EXEC sys.sp_executesql
        N'
            ALTER TABLE ods.ODS_FIN_PRIMA
            ADD CONSTRAINT CK_ODS_FIN_PRIMA_TIPO_MOVIMIENTO
            CHECK
            (
                DESC_TIPO_MOVIMIENTO IN
                (
                    ''EMISION'',
                    ''ANULACION''
                )
            );
        ';

    END;


    COMMIT TRANSACTION;

END TRY

BEGIN CATCH

    IF XACT_STATE() != 0
    BEGIN
        ROLLBACK TRANSACTION;
    END;

    DECLARE @MENSAJE_ERROR NVARCHAR(2048);

    SET @MENSAJE_ERROR =
        'Error en 15_ALTER_ODS_FIN_PRIMA.sql. '
        + ERROR_MESSAGE();

    RAISERROR
    (
        @MENSAJE_ERROR,
        16,
        1
    );

END CATCH;
GO


/* ============================================================
   11. VALIDACION FINAL DE LOS MOVIMIENTOS
   ============================================================ */

SELECT
    ID_MOVIMIENTO_PRIMA,
    COD_MOVIMIENTO_PRIMA,
    ID_ITEM,
    NRO_MOVIMIENTO,
    DESC_TIPO_MOVIMIENTO,
    MNT_PRIMA,
    MNT_PRIMA_DIRECTA,
    MNT_PRIMA_CEDIDA,
    MNT_PRIMA_RETENIDA,
    Q_CUOTAS
FROM ods.ODS_FIN_PRIMA
ORDER BY ID_MOVIMIENTO_PRIMA;
GO


/* ============================================================
   12. VALIDACION DE LA COMPOSICION
   ============================================================ */

SELECT
    ID_MOVIMIENTO_PRIMA,
    COD_MOVIMIENTO_PRIMA,
    MNT_PRIMA_DIRECTA,
    MNT_PRIMA_CEDIDA,
    MNT_PRIMA_RETENIDA,
    MNT_PRIMA_DIRECTA
    - MNT_PRIMA_CEDIDA
    - MNT_PRIMA_RETENIDA AS DIFERENCIA
FROM ods.ODS_FIN_PRIMA
ORDER BY ID_MOVIMIENTO_PRIMA;
GO


/* ============================================================
   13. VALIDACION DE CANTIDAD DE CUOTAS
   ============================================================ */

SELECT
    Q_CUOTAS,
    DESC_TIPO_MOVIMIENTO,
    COUNT_BIG(1) AS Q_MOVIMIENTOS
FROM ods.ODS_FIN_PRIMA
GROUP BY
    Q_CUOTAS,
    DESC_TIPO_MOVIMIENTO
ORDER BY
    DESC_TIPO_MOVIMIENTO,
    Q_CUOTAS;
GO


/* ============================================================
   14. VALIDACION DE CONSTRAINTS
   ============================================================ */

SELECT
    OBJECT_NAME(parent_object_id) AS DESC_TABLA,
    name AS DESC_CONSTRAINT,
    type_desc AS DESC_TIPO
FROM sys.objects
WHERE parent_object_id =
      OBJECT_ID('ods.ODS_FIN_PRIMA')
ORDER BY
    type_desc,
    name;
GO