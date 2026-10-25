USE DB_BI_RUTA_SMART;
GO


/* ============================================================
   CLIENTES FICTICIOS
   ============================================================ */

INSERT INTO ods.ODS_SEG_CLIENTE
(
      COD_CLIENTE
    , DESC_TIPO_CLIENTE
    , DESC_SEGMENTO
    , DESC_REGION
)
VALUES
      ('CLI000001', 'PERSONA', 'MASIVO',      'Metropolitana')
    , ('CLI000002', 'PERSONA', 'MASIVO',      'Valparaíso')
    , ('CLI000003', 'EMPRESA', 'PYME',        'Metropolitana')
    , ('CLI000004', 'EMPRESA', 'CORPORATIVO', 'Biobío')
    , ('CLI000005', 'PERSONA', 'MASIVO',      'Maule')
    , ('CLI000006', 'EMPRESA', 'PYME',        'Antofagasta')
    , ('CLI000007', 'PERSONA', 'MASIVO',      'Coquimbo')
    , ('CLI000008', 'EMPRESA', 'CORPORATIVO', 'Metropolitana')
    , ('CLI000009', 'PERSONA', 'MASIVO',      'La Araucanía')
    , ('CLI000010', 'EMPRESA', 'PYME',        'Valparaíso');
GO

/* ============================================================
   SEGUROS / ITEMS FICTICIOS
   ============================================================ */

INSERT INTO ods.ODS_SEG_SEGURO
(
      COD_POLIZA
    , COD_CERTIFICADO
    , ID_CLIENTE
    , COD_PRODUCTO
    , DESC_PRODUCTO
    , DESC_REGION
    , DT_FECHA_EMISION
    , DT_FECHA_INICIO_VIGENCIA
    , DT_FECHA_FIN_VIGENCIA
    , DESC_ESTADO_POLIZA
    , MNT_MONTO_ASEGURADO
)
SELECT
      V.COD_POLIZA
    , V.COD_CERTIFICADO
    , C.ID_CLIENTE
    , V.COD_PRODUCTO
    , V.DESC_PRODUCTO
    , V.DESC_REGION
    , V.DT_FECHA_EMISION
    , V.DT_FECHA_INICIO_VIGENCIA
    , V.DT_FECHA_FIN_VIGENCIA
    , V.DESC_ESTADO_POLIZA
    , V.MNT_MONTO_ASEGURADO

FROM
(
    VALUES

      ('POL000001', 1, 'CLI000001', 'AUTO', 'Seguro Automóvil',
       'Metropolitana',
       CAST('2026-01-02' AS DATE),
       CAST('2026-01-05' AS DATE),
       CAST('2027-01-05' AS DATE),
       'VIGENTE',
       CAST(18000000.00 AS DECIMAL(18,2)))

    , ('POL000001', 2, 'CLI000001', 'AUTO', 'Seguro Automóvil',
       'Metropolitana',
       CAST('2026-01-02' AS DATE),
       CAST('2026-01-05' AS DATE),
       CAST('2027-01-05' AS DATE),
       'VIGENTE',
       CAST(12000000.00 AS DECIMAL(18,2)))

    , ('POL000002', 1, 'CLI000002', 'HOGAR', 'Seguro Hogar',
       'Valparaíso',
       CAST('2026-02-01' AS DATE),
       CAST('2026-02-05' AS DATE),
       CAST('2027-02-05' AS DATE),
       'VIGENTE',
       CAST(85000000.00 AS DECIMAL(18,2)))

    , ('POL000003', 1, 'CLI000003', 'PYME', 'Seguro Pyme',
       'Metropolitana',
       CAST('2026-01-15' AS DATE),
       CAST('2026-01-20' AS DATE),
       CAST('2027-01-20' AS DATE),
       'VIGENTE',
       CAST(150000000.00 AS DECIMAL(18,2)))

    , ('POL000004', 1, 'CLI000004', 'EMP', 'Seguro Empresa',
       'Biobío',
       CAST('2025-01-10' AS DATE),
       CAST('2025-01-15' AS DATE),
       CAST('2026-01-15' AS DATE),
       'VENCIDA',
       CAST(500000000.00 AS DECIMAL(18,2)))

    , ('POL000005', 1, 'CLI000005', 'AUTO', 'Seguro Automóvil',
       'Maule',
       CAST('2026-03-01' AS DATE),
       CAST('2026-03-05' AS DATE),
       CAST('2027-03-05' AS DATE),
       'VIGENTE',
       CAST(22000000.00 AS DECIMAL(18,2)))

    , ('POL000006', 1, 'CLI000006', 'PYME', 'Seguro Pyme',
       'Antofagasta',
       CAST('2026-02-10' AS DATE),
       CAST('2026-02-15' AS DATE),
       CAST('2027-02-15' AS DATE),
       'VIGENTE',
       CAST(180000000.00 AS DECIMAL(18,2)))

    , ('POL000007', 1, 'CLI000007', 'HOGAR', 'Seguro Hogar',
       'Coquimbo',
       CAST('2025-05-01' AS DATE),
       CAST('2025-05-10' AS DATE),
       CAST('2026-05-10' AS DATE),
       'VENCIDA',
       CAST(65000000.00 AS DECIMAL(18,2)))

    , ('POL000008', 1, 'CLI000008', 'EMP', 'Seguro Empresa',
       'Metropolitana',
       CAST('2026-04-01' AS DATE),
       CAST('2026-04-05' AS DATE),
       CAST('2027-04-05' AS DATE),
       'VIGENTE',
       CAST(750000000.00 AS DECIMAL(18,2)))

    , ('POL000009', 1, 'CLI000009', 'AUTO', 'Seguro Automóvil',
       'La Araucanía',
       CAST('2026-03-15' AS DATE),
       CAST('2026-03-20' AS DATE),
       CAST('2027-03-20' AS DATE),
       'ANULADA',
       CAST(16000000.00 AS DECIMAL(18,2)))

    , ('POL000010', 1, 'CLI000010', 'PYME', 'Seguro Pyme',
       'Valparaíso',
       CAST('2026-05-01' AS DATE),
       CAST('2026-05-05' AS DATE),
       CAST('2027-05-05' AS DATE),
       'VIGENTE',
       CAST(210000000.00 AS DECIMAL(18,2)))

) V
(
      COD_POLIZA
    , COD_CERTIFICADO
    , COD_CLIENTE
    , COD_PRODUCTO
    , DESC_PRODUCTO
    , DESC_REGION
    , DT_FECHA_EMISION
    , DT_FECHA_INICIO_VIGENCIA
    , DT_FECHA_FIN_VIGENCIA
    , DESC_ESTADO_POLIZA
    , MNT_MONTO_ASEGURADO
)

INNER JOIN ods.ODS_SEG_CLIENTE C
    ON C.COD_CLIENTE = V.COD_CLIENTE;
GO

/* ============================================================
   MOVIMIENTOS DE PRIMA FICTICIOS
   ============================================================ */

INSERT INTO ods.ODS_FIN_PRIMA
(
      ID_ITEM
    , NRO_MOVIMIENTO
    , DT_FECHA_MOVIMIENTO
    , DESC_TIPO_MOVIMIENTO
    , MNT_PRIMA
    , MNT_COMISION
    , DESC_ESTADO_PAGO
    , DT_FECHA_PAGO
)
SELECT
      S.ID_ITEM
    , V.NRO_MOVIMIENTO
    , V.DT_FECHA_MOVIMIENTO
    , V.DESC_TIPO_MOVIMIENTO
    , V.MNT_PRIMA
    , V.MNT_COMISION
    , V.DESC_ESTADO_PAGO
    , V.DT_FECHA_PAGO
FROM
(
    VALUES
      ('POL000001', 1, 1, CAST('2026-01-05' AS DATE),
       'EMISION', 450000.00, 45000.00, 'PAGADO',
       CAST('2026-01-10' AS DATE))

    , ('POL000001', 2, 1, CAST('2026-01-05' AS DATE),
       'EMISION', 320000.00, 32000.00, 'PAGADO',
       CAST('2026-01-12' AS DATE))

    , ('POL000002', 1, 1, CAST('2026-02-05' AS DATE),
       'EMISION', 280000.00, 28000.00, 'PAGADO',
       CAST('2026-02-15' AS DATE))

    , ('POL000003', 1, 1, CAST('2026-01-20' AS DATE),
       'EMISION', 950000.00, 95000.00, 'PAGADO',
       CAST('2026-01-30' AS DATE))

    , ('POL000004', 1, 1, CAST('2025-01-15' AS DATE),
       'EMISION', 2800000.00, 280000.00, 'PAGADO',
       CAST('2025-01-25' AS DATE))

    , ('POL000005', 1, 1, CAST('2026-03-05' AS DATE),
       'EMISION', 510000.00, 51000.00, 'PENDIENTE',
       CAST(NULL AS DATE))

    , ('POL000006', 1, 1, CAST('2026-02-15' AS DATE),
       'EMISION', 1200000.00, 120000.00, 'PAGADO',
       CAST('2026-02-25' AS DATE))

    , ('POL000007', 1, 1, CAST('2025-05-10' AS DATE),
       'EMISION', 240000.00, 24000.00, 'PAGADO',
       CAST('2025-05-18' AS DATE))

    , ('POL000008', 1, 1, CAST('2026-04-05' AS DATE),
       'EMISION', 3500000.00, 350000.00, 'PENDIENTE',
       CAST(NULL AS DATE))

    , ('POL000009', 1, 1, CAST('2026-03-20' AS DATE),
       'EMISION', 410000.00, 41000.00, 'PAGADO',
       CAST('2026-03-25' AS DATE))

    , ('POL000009', 1, 2, CAST('2026-04-01' AS DATE),
       'ANULACION', -410000.00, 0.00, 'PAGADO',
       CAST('2026-04-01' AS DATE))

    , ('POL000010', 1, 1, CAST('2026-05-05' AS DATE),
       'EMISION', 1400000.00, 140000.00, 'PENDIENTE',
       CAST(NULL AS DATE))
) V
(
      COD_POLIZA
    , COD_CERTIFICADO
    , NRO_MOVIMIENTO
    , DT_FECHA_MOVIMIENTO
    , DESC_TIPO_MOVIMIENTO
    , MNT_PRIMA
    , MNT_COMISION
    , DESC_ESTADO_PAGO
    , DT_FECHA_PAGO
)

INNER JOIN ods.ODS_SEG_SEGURO S
    ON  S.COD_POLIZA = V.COD_POLIZA
    AND S.COD_CERTIFICADO = V.COD_CERTIFICADO;
GO

/* ============================================================
   SINIESTROS FICTICIOS
   ============================================================ */

INSERT INTO ods.ODS_SIN_SINIESTRO
(
      COD_SINIESTRO
    , ID_ITEM
    , DT_FECHA_OCURRENCIA
    , DT_FECHA_DENUNCIO
    , DESC_TIPO_SINIESTRO
    , DESC_ESTADO_SINIESTRO
    , MNT_DENUNCIADO
    , MNT_RESERVA
    , MNT_PAGADO
    , MNT_RECUPERADO
)
SELECT
      V.COD_SINIESTRO
    , S.ID_ITEM
    , V.DT_FECHA_OCURRENCIA
    , V.DT_FECHA_DENUNCIO
    , V.DESC_TIPO_SINIESTRO
    , V.DESC_ESTADO_SINIESTRO
    , V.MNT_DENUNCIADO
    , V.MNT_RESERVA
    , V.MNT_PAGADO
    , V.MNT_RECUPERADO
FROM
(
    VALUES
      ('SIN000001', 'POL000001', 1,
       CAST('2026-02-10' AS DATE),
       CAST('2026-02-11' AS DATE),
       'COLISION',
       'CERRADO',
       1800000.00,
       0.00,
       1500000.00,
       100000.00)

    , ('SIN000002', 'POL000001', 2,
       CAST('2026-03-05' AS DATE),
       CAST('2026-03-06' AS DATE),
       'ROBO',
       'ABIERTO',
       6500000.00,
       5000000.00,
       1000000.00,
       0.00)

    , ('SIN000003', 'POL000002', 1,
       CAST('2026-04-15' AS DATE),
       CAST('2026-04-16' AS DATE),
       'DAÑO HOGAR',
       'ABIERTO',
       3200000.00,
       2500000.00,
       500000.00,
       0.00)

    , ('SIN000004', 'POL000003', 1,
       CAST('2026-05-01' AS DATE),
       CAST('2026-05-02' AS DATE),
       'DAÑO MATERIAL',
       'CERRADO',
       8000000.00,
       0.00,
       7500000.00,
       500000.00)

    , ('SIN000005', 'POL000004', 1,
       CAST('2025-08-15' AS DATE),
       CAST('2025-08-16' AS DATE),
       'INCENDIO',
       'CERRADO',
       45000000.00,
       0.00,
       40000000.00,
       3000000.00)

    , ('SIN000006', 'POL000005', 1,
       CAST('2026-06-08' AS DATE),
       CAST('2026-06-09' AS DATE),
       'COLISION',
       'ABIERTO',
       2500000.00,
       1800000.00,
       500000.00,
       0.00)

    , ('SIN000007', 'POL000006', 1,
       CAST('2026-07-10' AS DATE),
       CAST('2026-07-11' AS DATE),
       'ROBO',
       'ABIERTO',
       12000000.00,
       9000000.00,
       2000000.00,
       0.00)

    , ('SIN000008', 'POL000008', 1,
       CAST('2026-08-01' AS DATE),
       CAST('2026-08-03' AS DATE),
       'DAÑO MATERIAL',
       'ABIERTO',
       30000000.00,
       25000000.00,
       3000000.00,
       0.00)
) V
(
      COD_SINIESTRO
    , COD_POLIZA
    , COD_CERTIFICADO
    , DT_FECHA_OCURRENCIA
    , DT_FECHA_DENUNCIO
    , DESC_TIPO_SINIESTRO
    , DESC_ESTADO_SINIESTRO
    , MNT_DENUNCIADO
    , MNT_RESERVA
    , MNT_PAGADO
    , MNT_RECUPERADO
)

INNER JOIN ods.ODS_SEG_SEGURO S
    ON  S.COD_POLIZA = V.COD_POLIZA
    AND S.COD_CERTIFICADO = V.COD_CERTIFICADO;
GO
