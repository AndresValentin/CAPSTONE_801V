USE DB_BI_RUTA_SMART;
GO

-- Propuesta: contraseñas de los usuarios. Solo se guarda el hash
-- (PBKDF2-SHA256 con sal propia por usuario, ver backend/app/claves.py),
-- nunca la clave en texto plano.
ALTER TABLE seguridad.SEG_USUARIO
    ADD DESC_CLAVE_HASH VARCHAR(200) NULL;
GO


-- Clave de demostración para los 4 usuarios: 1234.
-- Cada hash es distinto aunque la clave sea la misma, porque cada uno tiene su sal.
-- Para otra clave: python -m app.claves "nueva clave"  (desde la carpeta backend)
UPDATE U
SET U.DESC_CLAVE_HASH = V.DESC_CLAVE_HASH
FROM seguridad.SEG_USUARIO U

INNER JOIN
(
    VALUES
    ('USR_SIN', 'pbkdf2_sha256$600000$SOqaoJdFB4FlQau5/6M30g==$0OnKdOTm7XET8VIMC1cMMz2GUW3yEQcLgiB48RAFl8Q='),
    ('USR_FIN', 'pbkdf2_sha256$600000$/drF1QNxxblTB/UmgCo1PA==$pTBN+XR4W+esQUQ/kxLPdnLA9g8ebrmsttG3FgWUaME='),
    ('USR_SEG', 'pbkdf2_sha256$600000$aotXgnbH/59WqJP7NlcDRQ==$t5skS6sCG+k+OmBBJGgdsQAOYaYsIPnMmRuwfUJ2TmQ='),
    ('USR_ADMIN', 'pbkdf2_sha256$600000$7ouZSa0uH4YMYQnZi+BO3A==$C+tsbW7UlCf0zsU8Q9pm0iId/aPk6bIaGaaR/7DGh2g=')
) V
(
    COD_USUARIO,
    DESC_CLAVE_HASH
)
    ON V.COD_USUARIO = U.COD_USUARIO;
GO
