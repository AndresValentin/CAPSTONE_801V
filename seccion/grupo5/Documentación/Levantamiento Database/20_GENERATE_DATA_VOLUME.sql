USE DB_BI_RUTA_SMART;
GO

/* ============================================================
   GENERACION DE VOLUMEN DE DATOS

   Este script complementa la carga inicial realizada en
   12_INSERT_DATA_DEMO.sql.

   Objetivos actuales:

   Clientes: 5000
   Items asegurados: 12000
   ============================================================ */


/* ============================================================
   1. GENERACION DE CLIENTES

   Clientes existentes: 10
   Clientes objetivo: 5000
   Clientes adicionales: 4990
   ============================================================ */

;WITH NUMEROS AS
(
    SELECT TOP (4990)
        ROW_NUMBER() OVER
        (
            ORDER BY (SELECT NULL)
        ) AS N
    FROM sys.all_objects A
    CROSS JOIN sys.all_objects B
)
INSERT INTO ods.ODS_SEG_CLIENTE
(
    COD_CLIENTE,
    DESC_TIPO_CLIENTE,
    DESC_SEGMENTO,
    DESC_REGION
)
SELECT
    'CLI'
    + RIGHT
    (
        '000000'
        + CAST(N + 10 AS VARCHAR(6)),
        6
    ) AS COD_CLIENTE,

    CASE
        WHEN N % 4 = 0
            THEN 'EMPRESA'
        ELSE 'PERSONA'
    END AS DESC_TIPO_CLIENTE,

    CASE
        WHEN N % 4 != 0
            THEN 'MASIVO'
        WHEN N % 20 = 0
            THEN 'CORPORATIVO'
        ELSE 'PYME'
    END AS DESC_SEGMENTO,

    CASE N % 7
        WHEN 0 THEN 'Metropolitana'
        WHEN 1 THEN 'Valparaíso'
        WHEN 2 THEN 'Biobío'
        WHEN 3 THEN 'Maule'
        WHEN 4 THEN 'Antofagasta'
        WHEN 5 THEN 'Coquimbo'
        WHEN 6 THEN 'La Araucanía'
    END AS DESC_REGION
FROM NUMEROS;
GO


/* ============================================================
   2. VALIDACION DE CLIENTES
   ============================================================ */

SELECT
    COUNT(*) AS Q_CLIENTES
FROM ods.ODS_SEG_CLIENTE;
GO

SELECT
    DESC_TIPO_CLIENTE,
    DESC_SEGMENTO,
    COUNT(*) AS Q_CLIENTES
FROM ods.ODS_SEG_CLIENTE
GROUP BY
    DESC_TIPO_CLIENTE,
    DESC_SEGMENTO
ORDER BY
    DESC_TIPO_CLIENTE,
    DESC_SEGMENTO;
GO

SELECT
    DESC_REGION,
    COUNT(*) AS Q_CLIENTES
FROM ods.ODS_SEG_CLIENTE
GROUP BY
    DESC_REGION
ORDER BY
    DESC_REGION;
GO


/* ============================================================
   3. GENERACION DE ITEMS ASEGURADOS

   Items existentes: 11
   Items objetivo: 12000
   Items adicionales: 11989

   Polizas nuevas: 7992

   Las polizas pueden tener uno, dos o tres certificados.
   ============================================================ */

;WITH POLIZAS AS
(
    SELECT TOP (7992)
        ROW_NUMBER() OVER
        (
            ORDER BY (SELECT NULL)
        ) AS NRO_POLIZA
    FROM sys.all_objects A
    CROSS JOIN sys.all_objects B
),
BASE AS
(
    SELECT
        NRO_POLIZA,
        CASE
            WHEN NRO_POLIZA % 10 = 0 THEN 3
            WHEN NRO_POLIZA % 10 IN (1, 2, 3) THEN 2
            ELSE 1
        END AS Q_CERTIFICADOS,
        ((NRO_POLIZA - 1) % 5000) + 1 AS NRO_CLIENTE
    FROM POLIZAS
),
CERTIFICADOS AS
(
    SELECT
        B.NRO_POLIZA,
        B.NRO_CLIENTE,
        C.COD_CERTIFICADO
    FROM BASE B
    CROSS APPLY
    (
        VALUES
            (1),
            (2),
            (3)
    ) C(COD_CERTIFICADO)
    WHERE C.COD_CERTIFICADO <= B.Q_CERTIFICADOS
)
INSERT INTO ods.ODS_SEG_SEGURO
(
    COD_POLIZA,
    COD_CERTIFICADO,
    ID_CLIENTE,
    COD_PRODUCTO,
    DESC_PRODUCTO,
    DESC_REGION,
    DT_FECHA_EMISION,
    DT_FECHA_INICIO_VIGENCIA,
    DT_FECHA_FIN_VIGENCIA,
    DESC_ESTADO_POLIZA,
    MNT_MONTO_ASEGURADO
)
SELECT
    'POL'
    + RIGHT
    (
        '000000'
        + CAST(C.NRO_POLIZA + 10 AS VARCHAR(6)),
        6
    ) AS COD_POLIZA,

    C.COD_CERTIFICADO,
    CL.ID_CLIENTE,

    CASE
    WHEN CL.DESC_TIPO_CLIENTE = 'EMPRESA'
    THEN
        CASE
            WHEN ((C.NRO_POLIZA - 1) / 4) % 2 = 0
                THEN 'PYME'
            ELSE 'EMP'
        END
    ELSE
        CASE
            WHEN C.NRO_POLIZA % 2 = 0
                THEN 'AUTO'
            ELSE 'HOGAR'
        END
    END AS COD_PRODUCTO,

    CASE
    WHEN CL.DESC_TIPO_CLIENTE = 'EMPRESA'
    THEN
        CASE
            WHEN ((C.NRO_POLIZA - 1) / 4) % 2 = 0
                THEN 'Seguro Pyme'
            ELSE 'Seguro Empresa'
        END
    ELSE
        CASE
            WHEN C.NRO_POLIZA % 2 = 0
                THEN 'Seguro Automóvil'
            ELSE 'Seguro Hogar'
        END
    END AS DESC_PRODUCTO,
    CL.DESC_REGION,

    DATEADD
    (
        DAY,
        C.NRO_POLIZA % 730,
        CAST('2024-01-01' AS DATE)
    ) AS DT_FECHA_EMISION,

    DATEADD
    (
        DAY,
        (C.NRO_POLIZA % 730) + 5,
        CAST('2024-01-01' AS DATE)
    ) AS DT_FECHA_INICIO_VIGENCIA,

    DATEADD
    (
        YEAR,
        1,
        DATEADD
        (
            DAY,
            (C.NRO_POLIZA % 730) + 5,
            CAST('2024-01-01' AS DATE)
        )
    ) AS DT_FECHA_FIN_VIGENCIA,

    CASE
        WHEN C.NRO_POLIZA % 10 = 0
            THEN 'ANULADA'
        ELSE 'VIGENTE'
    END AS DESC_ESTADO_POLIZA,

    CASE
        WHEN CL.DESC_TIPO_CLIENTE = 'EMPRESA'
        THEN
            100000000.00
            + (C.NRO_POLIZA * 25000.00)
            + (C.COD_CERTIFICADO * 500000.00)
        ELSE
            10000000.00
            + (C.NRO_POLIZA * 10000.00)
            + (C.COD_CERTIFICADO * 100000.00)
    END AS MNT_MONTO_ASEGURADO
FROM CERTIFICADOS C
INNER JOIN ods.ODS_SEG_CLIENTE CL
    ON CL.COD_CLIENTE =
        'CLI'
        + RIGHT
        (
            '000000'
            + CAST(C.NRO_CLIENTE AS VARCHAR(6)),
            6
        );
GO


/* ============================================================
   4. VALIDACION DE ITEMS ASEGURADOS
   ============================================================ */

SELECT
    COUNT(*) AS Q_ITEMS
FROM ods.ODS_SEG_SEGURO;
GO

SELECT
    COUNT(DISTINCT COD_POLIZA) AS Q_POLIZAS,
    COUNT(*) AS Q_ITEMS,
    MIN(COD_CERTIFICADO) AS MIN_CERTIFICADO,
    MAX(COD_CERTIFICADO) AS MAX_CERTIFICADO
FROM ods.ODS_SEG_SEGURO;
GO


/* ============================================================
   5. VALIDACION DE DUPLICADOS
   ============================================================ */

SELECT
    COD_POLIZA,
    COD_CERTIFICADO,
    COUNT(*) AS Q_REGISTROS
FROM ods.ODS_SEG_SEGURO
GROUP BY
    COD_POLIZA,
    COD_CERTIFICADO
HAVING COUNT(*) > 1;
GO


/* ============================================================
   6. VALIDACION DE PRODUCTOS POR TIPO DE CLIENTE
   ============================================================ */

SELECT
    C.DESC_TIPO_CLIENTE,
    S.COD_PRODUCTO,
    COUNT(*) AS Q_ITEMS
FROM ods.ODS_SEG_SEGURO S
INNER JOIN ods.ODS_SEG_CLIENTE C
    ON S.ID_CLIENTE = C.ID_CLIENTE
GROUP BY
    C.DESC_TIPO_CLIENTE,
    S.COD_PRODUCTO
ORDER BY
    C.DESC_TIPO_CLIENTE,
    S.COD_PRODUCTO;
GO


/* ============================================================
   7. VALIDACION DE FECHAS
   ============================================================ */

SELECT
    COUNT(*) AS Q_FECHAS_INCONSISTENTES
FROM ods.ODS_SEG_SEGURO
WHERE DT_FECHA_EMISION > DT_FECHA_INICIO_VIGENCIA
   OR DT_FECHA_INICIO_VIGENCIA > DT_FECHA_FIN_VIGENCIA;
GO


/* ============================================================
   8. DISTRIBUCION DE CERTIFICADOS POR POLIZA
   ============================================================ */

;WITH CERTIFICADOS_POR_POLIZA AS
(
    SELECT
        COD_POLIZA,
        COUNT(*) AS Q_CERTIFICADOS
    FROM ods.ODS_SEG_SEGURO
    GROUP BY COD_POLIZA
)
SELECT
    Q_CERTIFICADOS,
    COUNT(*) AS Q_POLIZAS
FROM CERTIFICADOS_POR_POLIZA
GROUP BY Q_CERTIFICADOS
ORDER BY Q_CERTIFICADOS;
GO

/* ============================================================
   9. GENERACION DE EMISIONES DE PRIMA

   Se genera una emision para cada item que todavia no tenga
   un movimiento de tipo EMISION.

   Los codigos continuan desde el mayor codigo PRI existente.

   La prima directa se calcula segun el producto.

   La prima cedida y retenida representan la distribucion
   de la prima directa por reaseguro.

   Las emisiones pueden tener una u once cuotas.
   ============================================================ */

DECLARE @ULTIMO_CODIGO_PRIMA INT;

SELECT
    @ULTIMO_CODIGO_PRIMA =
        COALESCE
        (
            MAX
            (
                TRY_CONVERT
                (
                    INT,
                    RIGHT(COD_MOVIMIENTO_PRIMA, 6)
                )
            ),
            0
        )
FROM ods.ODS_FIN_PRIMA;

;WITH ITEMS_SIN_EMISION AS
(
    SELECT
        S.ID_ITEM,
        S.COD_PRODUCTO,
        S.MNT_MONTO_ASEGURADO,
        S.DT_FECHA_EMISION,

        ROW_NUMBER() OVER
        (
            ORDER BY S.ID_ITEM
        ) AS NRO_NUEVO_MOVIMIENTO

    FROM ods.ODS_SEG_SEGURO AS S

    WHERE NOT EXISTS
    (
        SELECT 1
        FROM ods.ODS_FIN_PRIMA AS P
        WHERE P.ID_ITEM = S.ID_ITEM
          AND P.DESC_TIPO_MOVIMIENTO = 'EMISION'
    )
)
INSERT INTO ods.ODS_FIN_PRIMA
(
    COD_MOVIMIENTO_PRIMA,
    ID_ITEM,
    NRO_MOVIMIENTO,
    DT_FECHA_MOVIMIENTO,
    DESC_TIPO_MOVIMIENTO,
    MNT_PRIMA,
    MNT_COMISION,
    DESC_ESTADO_PAGO,
    DT_FECHA_PAGO,
    MNT_PRIMA_DIRECTA,
    MNT_PRIMA_CEDIDA,
    MNT_PRIMA_RETENIDA,
    Q_CUOTAS
)
SELECT
    'PRI'
    + RIGHT
    (
        '000000'
        + CAST
        (
            @ULTIMO_CODIGO_PRIMA
            + NRO_NUEVO_MOVIMIENTO
            AS VARCHAR(6)
        ),
        6
    ) AS COD_MOVIMIENTO_PRIMA,

    ID_ITEM,

    1 AS NRO_MOVIMIENTO,

    DT_FECHA_EMISION AS DT_FECHA_MOVIMIENTO,

    'EMISION' AS DESC_TIPO_MOVIMIENTO,

    CAST
    (
        CASE COD_PRODUCTO
            WHEN 'AUTO'
                THEN MNT_MONTO_ASEGURADO * 0.030
            WHEN 'HOGAR'
                THEN MNT_MONTO_ASEGURADO * 0.008
            WHEN 'PYME'
                THEN MNT_MONTO_ASEGURADO * 0.015
            WHEN 'EMP'
                THEN MNT_MONTO_ASEGURADO * 0.012
        END
        AS DECIMAL(18,2)
    ) AS MNT_PRIMA,

    CAST
    (
        CASE COD_PRODUCTO
            WHEN 'AUTO'
                THEN MNT_MONTO_ASEGURADO * 0.030 * 0.10
            WHEN 'HOGAR'
                THEN MNT_MONTO_ASEGURADO * 0.008 * 0.10
            WHEN 'PYME'
                THEN MNT_MONTO_ASEGURADO * 0.015 * 0.10
            WHEN 'EMP'
                THEN MNT_MONTO_ASEGURADO * 0.012 * 0.10
        END
        AS DECIMAL(18,2)
    ) AS MNT_COMISION,

    CASE
        WHEN ID_ITEM % 3 = 0
            THEN 'PENDIENTE'
        ELSE 'PAGADO'
    END AS DESC_ESTADO_PAGO,

    CASE
        WHEN ID_ITEM % 3 = 0
            THEN NULL
        ELSE DATEADD
        (
            DAY,
            5,
            DT_FECHA_EMISION
        )
    END AS DT_FECHA_PAGO,

    CAST
    (
        CASE COD_PRODUCTO
            WHEN 'AUTO'
                THEN MNT_MONTO_ASEGURADO * 0.030
            WHEN 'HOGAR'
                THEN MNT_MONTO_ASEGURADO * 0.008
            WHEN 'PYME'
                THEN MNT_MONTO_ASEGURADO * 0.015
            WHEN 'EMP'
                THEN MNT_MONTO_ASEGURADO * 0.012
        END
        AS DECIMAL(18,2)
    ) AS MNT_PRIMA_DIRECTA,

    CAST
    (
        CASE COD_PRODUCTO
            WHEN 'AUTO'
                THEN MNT_MONTO_ASEGURADO * 0.030 * 0.20
            WHEN 'HOGAR'
                THEN MNT_MONTO_ASEGURADO * 0.008 * 0.25
            WHEN 'PYME'
                THEN MNT_MONTO_ASEGURADO * 0.015 * 0.30
            WHEN 'EMP'
                THEN MNT_MONTO_ASEGURADO * 0.012 * 0.40
        END
        AS DECIMAL(18,2)
    ) AS MNT_PRIMA_CEDIDA,

    CAST
    (
        CASE COD_PRODUCTO
            WHEN 'AUTO'
                THEN MNT_MONTO_ASEGURADO * 0.030 * 0.80
            WHEN 'HOGAR'
                THEN MNT_MONTO_ASEGURADO * 0.008 * 0.75
            WHEN 'PYME'
                THEN MNT_MONTO_ASEGURADO * 0.015 * 0.70
            WHEN 'EMP'
                THEN MNT_MONTO_ASEGURADO * 0.012 * 0.60
        END
        AS DECIMAL(18,2)
    ) AS MNT_PRIMA_RETENIDA,

    CASE
        WHEN ID_ITEM % 2 = 0
            THEN 1
        ELSE 11
    END AS Q_CUOTAS

FROM ITEMS_SIN_EMISION;
GO

/* ============================================================
   10. GENERACION DE ANULACIONES DE PRIMA

   Se anulan aproximadamente el 10 por ciento de las emisiones.

   La anulacion utiliza NRO_MOVIMIENTO igual a 2.

   Los importes de prima directa, cedida y retenida permanecen
   positivos. El tipo de movimiento determina el signo analitico.

   La columna antigua MNT_PRIMA se mantiene negativa para
   conservar compatibilidad con el modelo original.

   Las anulaciones no generan cuotas nuevas.
   ============================================================ */

DECLARE @ULTIMO_CODIGO_ANULACION INT;

SELECT
    @ULTIMO_CODIGO_ANULACION =
        COALESCE
        (
            MAX
            (
                TRY_CONVERT
                (
                    INT,
                    RIGHT(COD_MOVIMIENTO_PRIMA, 6)
                )
            ),
            0
        )
FROM ods.ODS_FIN_PRIMA;

;WITH ANULACIONES_CANDIDATAS AS
(
    SELECT
        P.ID_ITEM,
        DATEADD
        (
            DAY,
            30,
            P.DT_FECHA_MOVIMIENTO
        ) AS DT_FECHA_MOVIMIENTO,
        P.MNT_PRIMA_DIRECTA,
        P.MNT_PRIMA_CEDIDA,
        P.MNT_PRIMA_RETENIDA,

        ROW_NUMBER() OVER
        (
            ORDER BY P.ID_ITEM
        ) AS NRO_NUEVA_ANULACION

    FROM ods.ODS_FIN_PRIMA AS P

    WHERE P.DESC_TIPO_MOVIMIENTO = 'EMISION'
      AND P.ID_ITEM % 10 = 0
      AND NOT EXISTS
      (
          SELECT 1
          FROM ods.ODS_FIN_PRIMA AS A
          WHERE A.ID_ITEM = P.ID_ITEM
            AND A.DESC_TIPO_MOVIMIENTO = 'ANULACION'
      )
)
INSERT INTO ods.ODS_FIN_PRIMA
(
    COD_MOVIMIENTO_PRIMA,
    ID_ITEM,
    NRO_MOVIMIENTO,
    DT_FECHA_MOVIMIENTO,
    DESC_TIPO_MOVIMIENTO,
    MNT_PRIMA,
    MNT_COMISION,
    DESC_ESTADO_PAGO,
    DT_FECHA_PAGO,
    MNT_PRIMA_DIRECTA,
    MNT_PRIMA_CEDIDA,
    MNT_PRIMA_RETENIDA,
    Q_CUOTAS
)
SELECT
    'PRI'
    + RIGHT
    (
        '000000'
        + CAST
        (
            @ULTIMO_CODIGO_ANULACION
            + NRO_NUEVA_ANULACION
            AS VARCHAR(6)
        ),
        6
    ) AS COD_MOVIMIENTO_PRIMA,

    ID_ITEM,

    2 AS NRO_MOVIMIENTO,

    DT_FECHA_MOVIMIENTO,

    'ANULACION' AS DESC_TIPO_MOVIMIENTO,

    MNT_PRIMA_DIRECTA * -1 AS MNT_PRIMA,

    CAST
    (
        0
        AS DECIMAL(18,2)
    ) AS MNT_COMISION,

    'PAGADO' AS DESC_ESTADO_PAGO,

    DT_FECHA_MOVIMIENTO AS DT_FECHA_PAGO,

    MNT_PRIMA_DIRECTA,

    MNT_PRIMA_CEDIDA,

    MNT_PRIMA_RETENIDA,

    0 AS Q_CUOTAS

FROM ANULACIONES_CANDIDATAS;
GO

/* ============================================================
   11. GENERACION DE CUOTAS DE PRIMA

   Se generan cuotas solamente para emisiones que todavía no
   tengan registros en ODS_FIN_CUOTA_PRIMA.

   Situaciones de cobranza:

   Plan completamente pagado.

   Plan completamente pendiente.

   Plan parcialmente pagado, con seis cuotas pagadas y cinco
   cuotas pendientes.

   Las anulaciones no generan cuotas.
   ============================================================ */

;WITH NUMEROS_CUOTA AS
(
    SELECT 1 AS NRO_CUOTA
    UNION ALL SELECT 2
    UNION ALL SELECT 3
    UNION ALL SELECT 4
    UNION ALL SELECT 5
    UNION ALL SELECT 6
    UNION ALL SELECT 7
    UNION ALL SELECT 8
    UNION ALL SELECT 9
    UNION ALL SELECT 10
    UNION ALL SELECT 11
),
CUOTAS_GENERADAS AS
(
    SELECT
        P.ID_MOVIMIENTO_PRIMA,
        P.ID_ITEM,
        P.Q_CUOTAS,
        N.NRO_CUOTA,

        DATEADD
        (
            MONTH,
            N.NRO_CUOTA - 1,
            P.DT_FECHA_MOVIMIENTO
        ) AS DT_FECHA_VENCIMIENTO,

        CASE
            WHEN N.NRO_CUOTA < P.Q_CUOTAS
            THEN ROUND
            (
                P.MNT_PRIMA_DIRECTA / P.Q_CUOTAS,
                2
            )
            ELSE
                P.MNT_PRIMA_DIRECTA
                -
                (
                    ROUND
                    (
                        P.MNT_PRIMA_DIRECTA / P.Q_CUOTAS,
                        2
                    )
                    * (P.Q_CUOTAS - 1)
                )
        END AS MNT_CUOTA

    FROM ods.ODS_FIN_PRIMA AS P

    INNER JOIN NUMEROS_CUOTA AS N
        ON N.NRO_CUOTA
        BETWEEN 1 AND P.Q_CUOTAS

    WHERE P.DESC_TIPO_MOVIMIENTO = 'EMISION'

      AND NOT EXISTS
      (
          SELECT 1
          FROM ods.ODS_FIN_CUOTA_PRIMA AS C
          WHERE C.ID_MOVIMIENTO_PRIMA =
                P.ID_MOVIMIENTO_PRIMA
      )
)
INSERT INTO ods.ODS_FIN_CUOTA_PRIMA
(
    ID_MOVIMIENTO_PRIMA,
    NRO_CUOTA,
    DT_FECHA_VENCIMIENTO,
    MNT_CUOTA,
    DESC_ESTADO_CUOTA,
    DT_FECHA_PAGO
)
SELECT
    ID_MOVIMIENTO_PRIMA,
    NRO_CUOTA,
    DT_FECHA_VENCIMIENTO,
    MNT_CUOTA,

    CASE
        WHEN Q_CUOTAS = 1
             AND ID_ITEM % 3 = 0
            THEN 'PENDIENTE'

        WHEN Q_CUOTAS = 1
            THEN 'PAGADA'

        WHEN ID_ITEM % 3 = 0
            THEN 'PENDIENTE'

        WHEN ID_ITEM % 3 = 1
            THEN 'PAGADA'

        WHEN NRO_CUOTA BETWEEN 1 AND 6
            THEN 'PAGADA'

        ELSE 'PENDIENTE'
    END AS DESC_ESTADO_CUOTA,

    CASE
        WHEN Q_CUOTAS = 1
             AND ID_ITEM % 3 = 0
            THEN NULL

        WHEN Q_CUOTAS = 1
            THEN DATEADD
            (
                DAY,
                5,
                DT_FECHA_VENCIMIENTO
            )

        WHEN ID_ITEM % 3 = 0
            THEN NULL

        WHEN ID_ITEM % 3 = 1
            THEN DATEADD
            (
                DAY,
                5,
                DT_FECHA_VENCIMIENTO
            )

        WHEN NRO_CUOTA BETWEEN 1 AND 6
            THEN DATEADD
            (
                DAY,
                5,
                DT_FECHA_VENCIMIENTO
            )

        ELSE NULL
    END AS DT_FECHA_PAGO

FROM CUOTAS_GENERADAS;
GO

/* ============================================================
   12. GENERACION DE SINIESTROS

   Siniestros existentes: 8
   Siniestros objetivo: 8000
   Siniestros adicionales: 7992

   Se genera un siniestro para cada item seleccionado que
   todavia no tenga un siniestro asociado.
   ============================================================ */

DECLARE @ULTIMO_CODIGO_SINIESTRO INT;

SELECT
    @ULTIMO_CODIGO_SINIESTRO =
        COALESCE
        (
            MAX
            (
                TRY_CONVERT
                (
                    INT,
                    RIGHT(COD_SINIESTRO, 6)
                )
            ),
            0
        )
FROM ods.ODS_SIN_SINIESTRO;

;WITH ITEMS_CANDIDATOS AS
(
    SELECT TOP (7992)
        S.ID_ITEM,
        S.COD_PRODUCTO,
        S.DT_FECHA_INICIO_VIGENCIA,
        S.MNT_MONTO_ASEGURADO,
        ROW_NUMBER() OVER
        (
            ORDER BY S.ID_ITEM
        ) AS NRO_NUEVO_SINIESTRO
    FROM ods.ODS_SEG_SEGURO AS S
    WHERE NOT EXISTS
    (
        SELECT 1
        FROM ods.ODS_SIN_SINIESTRO AS SI
        WHERE SI.ID_ITEM = S.ID_ITEM
    )
    ORDER BY S.ID_ITEM
)
INSERT INTO ods.ODS_SIN_SINIESTRO
(
    COD_SINIESTRO,
    ID_ITEM,
    DT_FECHA_OCURRENCIA,
    DT_FECHA_DENUNCIO,
    DESC_TIPO_SINIESTRO,
    DESC_ESTADO_SINIESTRO,
    MNT_DENUNCIADO,
    MNT_RESERVA,
    MNT_PAGADO,
    MNT_RECUPERADO
)
SELECT
    'SIN'
    + RIGHT
    (
        '000000'
        + CAST
        (
            @ULTIMO_CODIGO_SINIESTRO
            + NRO_NUEVO_SINIESTRO
            AS VARCHAR(6)
        ),
        6
    ) AS COD_SINIESTRO,

    ID_ITEM,

    DATEADD
    (
        DAY,
        30 + NRO_NUEVO_SINIESTRO % 250,
        DT_FECHA_INICIO_VIGENCIA
    ) AS DT_FECHA_OCURRENCIA,

    DATEADD
    (
        DAY,
        32 + NRO_NUEVO_SINIESTRO % 250,
        DT_FECHA_INICIO_VIGENCIA
    ) AS DT_FECHA_DENUNCIO,

    CASE COD_PRODUCTO
        WHEN 'AUTO' THEN 'COLISION'
        WHEN 'HOGAR' THEN 'DANO_HOGAR'
        WHEN 'PYME' THEN 'DANO_COMERCIAL'
        WHEN 'EMP' THEN 'DANO_EMPRESA'
    END AS DESC_TIPO_SINIESTRO,

    CASE
        WHEN NRO_NUEVO_SINIESTRO % 3 = 0
            THEN 'ABIERTO'
        ELSE 'CERRADO'
    END AS DESC_ESTADO_SINIESTRO,

    CAST
    (
        MNT_MONTO_ASEGURADO
        *
        CASE COD_PRODUCTO
            WHEN 'AUTO' THEN 0.08
            WHEN 'HOGAR' THEN 0.05
            WHEN 'PYME' THEN 0.03
            WHEN 'EMP' THEN 0.025
        END
        AS DECIMAL(18,2)
    ) AS MNT_DENUNCIADO,

    CAST
    (
        CASE
            WHEN NRO_NUEVO_SINIESTRO % 3 = 0
            THEN
                MNT_MONTO_ASEGURADO
                *
                CASE COD_PRODUCTO
                    WHEN 'AUTO' THEN 0.06
                    WHEN 'HOGAR' THEN 0.04
                    WHEN 'PYME' THEN 0.02
                    WHEN 'EMP' THEN 0.015
                END
            ELSE 0
        END
        AS DECIMAL(18,2)
    ) AS MNT_RESERVA,

    CAST
    (
        CASE
            WHEN NRO_NUEVO_SINIESTRO % 3 = 0
                THEN 0
            ELSE
                MNT_MONTO_ASEGURADO
                *
                CASE COD_PRODUCTO
                    WHEN 'AUTO' THEN 0.07
                    WHEN 'HOGAR' THEN 0.045
                    WHEN 'PYME' THEN 0.025
                    WHEN 'EMP' THEN 0.020
                END
        END
        AS DECIMAL(18,2)
    ) AS MNT_PAGADO,

    CAST
    (
        CASE
            WHEN NRO_NUEVO_SINIESTRO % 5 = 0
                THEN MNT_MONTO_ASEGURADO * 0.005
            ELSE 0
        END
        AS DECIMAL(18,2)
    ) AS MNT_RECUPERADO
FROM ITEMS_CANDIDATOS;
GO


/* ============================================================
   13. VALIDACION DEL TOTAL DE SINIESTROS
   ============================================================ */

SELECT
    COUNT_BIG(1) AS Q_SINIESTROS
FROM ods.ODS_SIN_SINIESTRO;
GO


/* ============================================================
   14. VALIDACION DE CODIGOS DUPLICADOS
   ============================================================ */

SELECT
    COD_SINIESTRO,
    COUNT_BIG(1) AS Q_REGISTROS
FROM ods.ODS_SIN_SINIESTRO
GROUP BY COD_SINIESTRO
HAVING COUNT_BIG(1) > 1;
GO


/* ============================================================
   15. VALIDACION DE FECHAS
   ============================================================ */

SELECT
    COUNT_BIG(1) AS Q_FECHAS_INCONSISTENTES
FROM ods.ODS_SIN_SINIESTRO
WHERE DT_FECHA_DENUNCIO < DT_FECHA_OCURRENCIA;
GO


/* ============================================================
   16. VALIDACION DE MONTOS NEGATIVOS
   ============================================================ */

SELECT
    COUNT_BIG(1) AS Q_MONTOS_INCONSISTENTES
FROM ods.ODS_SIN_SINIESTRO
WHERE MNT_DENUNCIADO < 0
   OR MNT_RESERVA < 0
   OR MNT_PAGADO < 0
   OR MNT_RECUPERADO < 0;
GO


/* ============================================================
   17. VALIDACION DE ESTADO Y MONTOS DE SINIESTRO

   Un siniestro abierto debe mantener una reserva positiva
   y puede tener pagos parciales.

   Un siniestro cerrado debe tener reserva igual a cero
   y un monto pagado positivo.
   ============================================================ */

SELECT
    COUNT_BIG(1) AS Q_ESTADOS_INCONSISTENTES
FROM ods.ODS_SIN_SINIESTRO
WHERE
    (
        DESC_ESTADO_SINIESTRO = 'ABIERTO'
        AND MNT_RESERVA <= 0
    )
    OR
    (
        DESC_ESTADO_SINIESTRO = 'CERRADO'
        AND
        (
            MNT_RESERVA != 0
            OR MNT_PAGADO <= 0
        )
    )
    OR DESC_ESTADO_SINIESTRO NOT IN
    (
        'ABIERTO',
        'CERRADO'
    );
GO


/* ============================================================
   18. RESUMEN POR ESTADO
   ============================================================ */

SELECT
    DESC_ESTADO_SINIESTRO,
    COUNT_BIG(1) AS Q_SINIESTROS,
    SUM(MNT_DENUNCIADO) AS MNT_DENUNCIADO,
    SUM(MNT_RESERVA) AS MNT_RESERVA,
    SUM(MNT_PAGADO) AS MNT_PAGADO,
    SUM(MNT_RECUPERADO) AS MNT_RECUPERADO
FROM ods.ODS_SIN_SINIESTRO
GROUP BY DESC_ESTADO_SINIESTRO
ORDER BY DESC_ESTADO_SINIESTRO;
GO


/* ============================================================
   19. VALIDACION DE SINIESTROS SIN ITEM
   ============================================================ */

SELECT
    COUNT_BIG(1) AS Q_SINIESTROS_SIN_ITEM
FROM ods.ODS_SIN_SINIESTRO AS SI
LEFT JOIN ods.ODS_SEG_SEGURO AS S
    ON SI.ID_ITEM = S.ID_ITEM
WHERE S.ID_ITEM IS NULL;
GO
