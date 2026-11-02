USE DB_BI_RUTA_SMART;
GO

/* ============================================================
   CARGA INICIAL DE CUOTAS DE PRIMA

   Este script genera cuotas únicamente para movimientos
   de tipo EMISION.

   Reglas:

   Una emisión puede tener 1 u 11 cuotas.

   Una anulación no genera cuotas nuevas.

   La suma de las cuotas debe coincidir con la prima directa.

   Las cuotas pagadas tienen fecha de pago.

   Las cuotas pendientes no tienen fecha de pago.
   ============================================================ */


/* ============================================================
   1. VALIDAR QUE LA TABLA DE CUOTAS ESTE VACIA
   ============================================================ */

IF EXISTS
(
    SELECT 1
    FROM ods.ODS_FIN_CUOTA_PRIMA
)
BEGIN
    RAISERROR
    (
        'La tabla de cuotas ya contiene registros. No se realizo una nueva carga.',
        16,
        1
    );
END
ELSE
BEGIN

    /* ========================================================
       2. GENERAR E INSERTAR CUOTAS
       ======================================================== */

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
    CUOTAS AS
    (
        SELECT
            P.ID_MOVIMIENTO_PRIMA,
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
            END AS MNT_CUOTA,

            CASE
                WHEN P.DESC_ESTADO_PAGO = 'PAGADO'
                    THEN 'PAGADA'
                ELSE 'PENDIENTE'
            END AS DESC_ESTADO_CUOTA,

            CASE
                WHEN P.DESC_ESTADO_PAGO = 'PAGADO'
                THEN DATEADD
                (
                    MONTH,
                    N.NRO_CUOTA - 1,
                    P.DT_FECHA_PAGO
                )
                ELSE NULL
            END AS DT_FECHA_PAGO

        FROM ods.ODS_FIN_PRIMA P

        INNER JOIN NUMEROS_CUOTA N
            ON N.NRO_CUOTA <= P.Q_CUOTAS

        WHERE P.DESC_TIPO_MOVIMIENTO = 'EMISION'
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
        DESC_ESTADO_CUOTA,
        DT_FECHA_PAGO
    FROM CUOTAS;

END;
GO


/* ============================================================
   3. VALIDAR CANTIDAD TOTAL DE CUOTAS
   ============================================================ */

SELECT
    COUNT(*) AS Q_CUOTAS
FROM ods.ODS_FIN_CUOTA_PRIMA;
GO


/* ============================================================
   4. CONCILIAR CUOTAS CONTRA PRIMA DIRECTA
   ============================================================ */

SELECT
    P.ID_MOVIMIENTO_PRIMA,
    P.MNT_PRIMA_DIRECTA,
    P.Q_CUOTAS,
    COUNT(C.ID_CUOTA_PRIMA) AS Q_CUOTAS_CARGADAS,
    SUM(C.MNT_CUOTA) AS MNT_TOTAL_CUOTAS,
    P.MNT_PRIMA_DIRECTA - SUM(C.MNT_CUOTA) AS DIFERENCIA
FROM ods.ODS_FIN_PRIMA P

INNER JOIN ods.ODS_FIN_CUOTA_PRIMA C
    ON P.ID_MOVIMIENTO_PRIMA = C.ID_MOVIMIENTO_PRIMA

WHERE P.DESC_TIPO_MOVIMIENTO = 'EMISION'

GROUP BY
    P.ID_MOVIMIENTO_PRIMA,
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
   6. RESUMEN DE COBRANZA
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
   7. VALIDAR QUE LAS ANULACIONES NO TENGAN CUOTAS
   ============================================================ */

SELECT
    COUNT(*) AS Q_ANULACIONES_CON_CUOTAS
FROM ods.ODS_FIN_CUOTA_PRIMA C

INNER JOIN ods.ODS_FIN_PRIMA P
    ON C.ID_MOVIMIENTO_PRIMA = P.ID_MOVIMIENTO_PRIMA

WHERE P.DESC_TIPO_MOVIMIENTO = 'ANULACION';
GO