USE DB_BI_RUTA_SMART;
GO

/* ============================================================
   VALIDACION DEL MODELO FINANCIERO
   ============================================================ */


/* ============================================================
   1. CONTEOS GENERALES
   ============================================================ */

SELECT
    'ODS_FIN_PRIMA' AS OBJETO,
    COUNT(*) AS Q_REGISTROS
FROM ods.ODS_FIN_PRIMA

UNION ALL

SELECT
    'ODS_FIN_CUOTA_PRIMA',
    COUNT(*)
FROM ods.ODS_FIN_CUOTA_PRIMA;
GO


/* ============================================================
   2. VALIDAR COMPOSICION DE PRIMAS
   ============================================================ */

SELECT
    COUNT(*) AS Q_INCONSISTENCIAS
FROM ods.ODS_FIN_PRIMA
WHERE
    MNT_PRIMA_DIRECTA
    !=
    MNT_PRIMA_CEDIDA + MNT_PRIMA_RETENIDA;
GO


/* ============================================================
   3. VALIDAR MODALIDAD DE CUOTAS
   ============================================================ */

SELECT
    COUNT(*) AS Q_INCONSISTENCIAS
FROM ods.ODS_FIN_PRIMA
WHERE
    (
        DESC_TIPO_MOVIMIENTO = 'EMISION'
        AND Q_CUOTAS NOT IN (1, 11)
    )
    OR
    (
        DESC_TIPO_MOVIMIENTO = 'ANULACION'
        AND NOT Q_CUOTAS = 0
    );
GO


/* ============================================================
   4. CONCILIAR CUOTAS CON PRIMA DIRECTA
   ============================================================ */

SELECT
    P.ID_MOVIMIENTO_PRIMA,
    P.DESC_TIPO_MOVIMIENTO,
    P.MNT_PRIMA_DIRECTA,
    P.Q_CUOTAS,
    COUNT(C.ID_CUOTA_PRIMA) AS Q_CUOTAS_CARGADAS,
    COALESCE(SUM(C.MNT_CUOTA), 0) AS MNT_TOTAL_CUOTAS,

    CASE
        WHEN P.DESC_TIPO_MOVIMIENTO = 'ANULACION'
            THEN 0
        ELSE
            P.MNT_PRIMA_DIRECTA
            - COALESCE(SUM(C.MNT_CUOTA), 0)
    END AS DIFERENCIA

FROM ods.ODS_FIN_PRIMA P

LEFT JOIN ods.ODS_FIN_CUOTA_PRIMA C
    ON P.ID_MOVIMIENTO_PRIMA = C.ID_MOVIMIENTO_PRIMA

GROUP BY
    P.ID_MOVIMIENTO_PRIMA,
    P.DESC_TIPO_MOVIMIENTO,
    P.MNT_PRIMA_DIRECTA,
    P.Q_CUOTAS

ORDER BY
    P.ID_MOVIMIENTO_PRIMA;
GO


/* ============================================================
   5. VALIDAR ESTADO Y FECHA DE PAGO
   ============================================================ */

SELECT
    COUNT(*) AS Q_INCONSISTENCIAS
FROM ods.ODS_FIN_CUOTA_PRIMA
WHERE
    (
        DESC_ESTADO_CUOTA = 'PAGADA'
        AND DT_FECHA_PAGO IS NULL
    )
    OR
    (
        DESC_ESTADO_CUOTA = 'PENDIENTE'
        AND DT_FECHA_PAGO IS NOT NULL
    );
GO


/* ============================================================
   6. VALIDAR ANULACIONES SIN CUOTAS
   ============================================================ */

SELECT
    COUNT(*) AS Q_ANULACIONES_CON_CUOTAS
FROM ods.ODS_FIN_PRIMA P

INNER JOIN ods.ODS_FIN_CUOTA_PRIMA C
    ON P.ID_MOVIMIENTO_PRIMA = C.ID_MOVIMIENTO_PRIMA

WHERE P.DESC_TIPO_MOVIMIENTO = 'ANULACION';
GO


/* ============================================================
   7. RESUMEN DE COBRANZA
   ============================================================ */

SELECT
    DESC_ESTADO_CUOTA,
    COUNT(*) AS Q_CUOTAS,
    SUM(MNT_CUOTA) AS MNT_TOTAL
FROM ods.ODS_FIN_CUOTA_PRIMA
GROUP BY
    DESC_ESTADO_CUOTA
ORDER BY
    DESC_ESTADO_CUOTA;
GO

/* ============================================================
   8. CALCULAR PRIMA GANADA Y NO GANADA

   Fecha de corte utilizada:
   1 de noviembre de 2026

   El cálculo se realiza según el periodo de cobertura.

   Las emisiones suman.

   Las anulaciones restan.
   ============================================================ */

DECLARE @FECHA_CORTE DATE;

SET @FECHA_CORTE = '2026-11-01';

;WITH BASE_DEVENGO AS
(
    SELECT
        P.ID_MOVIMIENTO_PRIMA,
        S.COD_POLIZA,
        S.COD_CERTIFICADO,
        S.COD_PRODUCTO,
        P.DESC_TIPO_MOVIMIENTO,
        S.DT_FECHA_INICIO_VIGENCIA,
        S.DT_FECHA_FIN_VIGENCIA,
        P.MNT_PRIMA_DIRECTA,
        P.MNT_PRIMA_CEDIDA,
        P.MNT_PRIMA_RETENIDA,

        CASE
            WHEN P.DESC_TIPO_MOVIMIENTO = 'ANULACION'
                THEN -1
            ELSE 1
        END AS SIGNO_MOVIMIENTO,

        DATEDIFF
        (
            DAY,
            S.DT_FECHA_INICIO_VIGENCIA,
            S.DT_FECHA_FIN_VIGENCIA
        ) AS Q_DIAS_VIGENCIA,

        CASE
            WHEN @FECHA_CORTE <= S.DT_FECHA_INICIO_VIGENCIA
                THEN 0

            WHEN @FECHA_CORTE >= S.DT_FECHA_FIN_VIGENCIA
                THEN DATEDIFF
                (
                    DAY,
                    S.DT_FECHA_INICIO_VIGENCIA,
                    S.DT_FECHA_FIN_VIGENCIA
                )

            ELSE DATEDIFF
            (
                DAY,
                S.DT_FECHA_INICIO_VIGENCIA,
                @FECHA_CORTE
            )
        END AS Q_DIAS_GANADOS

    FROM ods.ODS_FIN_PRIMA P

    INNER JOIN ods.ODS_SEG_SEGURO S
        ON P.ID_ITEM = S.ID_ITEM
),
CALCULO_DEVENGO AS
(
    SELECT
        ID_MOVIMIENTO_PRIMA,
        COD_POLIZA,
        COD_CERTIFICADO,
        COD_PRODUCTO,
        DESC_TIPO_MOVIMIENTO,
        DT_FECHA_INICIO_VIGENCIA,
        DT_FECHA_FIN_VIGENCIA,
        Q_DIAS_VIGENCIA,
        Q_DIAS_GANADOS,
        SIGNO_MOVIMIENTO,

        MNT_PRIMA_DIRECTA,
        MNT_PRIMA_CEDIDA,
        MNT_PRIMA_RETENIDA,

        CAST
        (
            Q_DIAS_GANADOS * 1.0
            / NULLIF(Q_DIAS_VIGENCIA, 0)
            AS DECIMAL(18,6)
        ) AS PCT_DEVENGADO

    FROM BASE_DEVENGO
)
SELECT
    ID_MOVIMIENTO_PRIMA,
    COD_POLIZA,
    COD_CERTIFICADO,
    COD_PRODUCTO,
    DESC_TIPO_MOVIMIENTO,
    DT_FECHA_INICIO_VIGENCIA,
    DT_FECHA_FIN_VIGENCIA,
    Q_DIAS_VIGENCIA,
    Q_DIAS_GANADOS,
    PCT_DEVENGADO,

    SIGNO_MOVIMIENTO
    * MNT_PRIMA_DIRECTA AS MNT_PRIMA_DIRECTA_NETA,

    SIGNO_MOVIMIENTO
    * ROUND
    (
        MNT_PRIMA_DIRECTA * PCT_DEVENGADO,
        2
    ) AS MNT_PRIMA_DIRECTA_GANADA,

    SIGNO_MOVIMIENTO
    * ROUND
    (
        MNT_PRIMA_DIRECTA
        - MNT_PRIMA_DIRECTA * PCT_DEVENGADO,
        2
    ) AS MNT_PRIMA_DIRECTA_NO_GANADA,

    SIGNO_MOVIMIENTO
    * ROUND
    (
        MNT_PRIMA_CEDIDA * PCT_DEVENGADO,
        2
    ) AS MNT_PRIMA_CEDIDA_GANADA,

    SIGNO_MOVIMIENTO
    * ROUND
    (
        MNT_PRIMA_CEDIDA
        - MNT_PRIMA_CEDIDA * PCT_DEVENGADO,
        2
    ) AS MNT_PRIMA_CEDIDA_NO_GANADA,

    SIGNO_MOVIMIENTO
    * ROUND
    (
        MNT_PRIMA_RETENIDA * PCT_DEVENGADO,
        2
    ) AS MNT_PRIMA_RETENIDA_GANADA,

    SIGNO_MOVIMIENTO
    * ROUND
    (
        MNT_PRIMA_RETENIDA
        - MNT_PRIMA_RETENIDA * PCT_DEVENGADO,
        2
    ) AS MNT_PRIMA_RETENIDA_NO_GANADA

FROM CALCULO_DEVENGO

ORDER BY
    ID_MOVIMIENTO_PRIMA;
GO

/* ============================================================
   9. RESUMEN DE DEVENGO POR PRODUCTO
   ============================================================ */

DECLARE @FECHA_CORTE_RESUMEN DATE;

SET @FECHA_CORTE_RESUMEN = '2026-11-01';

;WITH BASE_DEVENGO AS
(
    SELECT
        S.COD_PRODUCTO,
        P.DESC_TIPO_MOVIMIENTO,

        CASE
            WHEN P.DESC_TIPO_MOVIMIENTO = 'ANULACION'
                THEN -1
            ELSE 1
        END AS SIGNO_MOVIMIENTO,

        P.MNT_PRIMA_DIRECTA,
        P.MNT_PRIMA_CEDIDA,
        P.MNT_PRIMA_RETENIDA,

        DATEDIFF
        (
            DAY,
            S.DT_FECHA_INICIO_VIGENCIA,
            S.DT_FECHA_FIN_VIGENCIA
        ) AS Q_DIAS_VIGENCIA,

        CASE
            WHEN @FECHA_CORTE_RESUMEN <=
                 S.DT_FECHA_INICIO_VIGENCIA
                THEN 0

            WHEN @FECHA_CORTE_RESUMEN >=
                 S.DT_FECHA_FIN_VIGENCIA
                THEN DATEDIFF
                (
                    DAY,
                    S.DT_FECHA_INICIO_VIGENCIA,
                    S.DT_FECHA_FIN_VIGENCIA
                )

            ELSE DATEDIFF
            (
                DAY,
                S.DT_FECHA_INICIO_VIGENCIA,
                @FECHA_CORTE_RESUMEN
            )
        END AS Q_DIAS_GANADOS

    FROM ods.ODS_FIN_PRIMA P

    INNER JOIN ods.ODS_SEG_SEGURO S
        ON P.ID_ITEM = S.ID_ITEM
),
CALCULO_DEVENGO AS
(
    SELECT
        COD_PRODUCTO,
        SIGNO_MOVIMIENTO,
        MNT_PRIMA_DIRECTA,
        MNT_PRIMA_CEDIDA,
        MNT_PRIMA_RETENIDA,

        CAST
        (
            Q_DIAS_GANADOS * 1.0
            / NULLIF(Q_DIAS_VIGENCIA, 0)
            AS DECIMAL(18,6)
        ) AS PCT_DEVENGADO

    FROM BASE_DEVENGO
)
SELECT
    COD_PRODUCTO,

    SUM
    (
        SIGNO_MOVIMIENTO
        * MNT_PRIMA_DIRECTA
    ) AS MNT_PRIMA_DIRECTA_NETA,

    SUM
    (
        SIGNO_MOVIMIENTO
        * ROUND
        (
            MNT_PRIMA_DIRECTA * PCT_DEVENGADO,
            2
        )
    ) AS MNT_PRIMA_DIRECTA_GANADA,

    SUM
    (
        SIGNO_MOVIMIENTO
        * ROUND
        (
            MNT_PRIMA_DIRECTA
            - MNT_PRIMA_DIRECTA * PCT_DEVENGADO,
            2
        )
    ) AS MNT_PRIMA_DIRECTA_NO_GANADA,

    SUM
    (
        SIGNO_MOVIMIENTO
        * ROUND
        (
            MNT_PRIMA_CEDIDA * PCT_DEVENGADO,
            2
        )
    ) AS MNT_PRIMA_CEDIDA_GANADA,

    SUM
    (
        SIGNO_MOVIMIENTO
        * ROUND
        (
            MNT_PRIMA_RETENIDA * PCT_DEVENGADO,
            2
        )
    ) AS MNT_PRIMA_RETENIDA_GANADA

FROM CALCULO_DEVENGO

GROUP BY
    COD_PRODUCTO

ORDER BY
    COD_PRODUCTO;
GO