"""Contraseñas: nunca se guardan en texto plano, solo su hash.

Se usa PBKDF2-SHA256 (incluido en Python) con una sal aleatoria por usuario y
600.000 iteraciones, lo recomendado por OWASP. El resultado se guarda en
seguridad.SEG_USUARIO.DESC_CLAVE_HASH con el formato:

    pbkdf2_sha256$<iteraciones>$<sal en base64>$<hash en base64>

Para generar el hash de una clave nueva:
    python -m app.claves "mi clave"
"""

import base64
import hashlib
import hmac
import secrets
import sys

ALGORITMO = "pbkdf2_sha256"
ITERACIONES = 600_000


def _b64(datos: bytes) -> str:
    return base64.b64encode(datos).decode("ascii")


def generar_hash(clave: str) -> str:
    sal = secrets.token_bytes(16)
    resumen = hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), sal, ITERACIONES)
    return f"{ALGORITMO}${ITERACIONES}${_b64(sal)}${_b64(resumen)}"


def verificar(clave: str, hash_guardado: str | None) -> bool:
    if not hash_guardado:
        return False
    try:
        algoritmo, iteraciones, sal, esperado = hash_guardado.split("$")
        if algoritmo != ALGORITMO:
            return False
        resumen = hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), base64.b64decode(sal), int(iteraciones))
    except (ValueError, TypeError):
        return False
    # compare_digest tarda lo mismo acierte o no, para no filtrar información por tiempos
    return hmac.compare_digest(resumen, base64.b64decode(esperado))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit('Uso: python -m app.claves "clave"')
    print(generar_hash(sys.argv[1]))
