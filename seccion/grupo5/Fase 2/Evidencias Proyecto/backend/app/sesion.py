"""Token de sesión firmado.

Al iniciar sesión el backend entrega un token "usuario.vencimiento.firma".
La firma es un HMAC con SESSION_SECRET, así que el navegador no puede
cambiar el usuario del token (por ejemplo, hacerse pasar por USR_ADMIN)
sin que la firma deje de calzar.
"""

import base64
import hashlib
import hmac
import os
import secrets
import time

DURACION = 8 * 60 * 60  # segundos

# Sin SESSION_SECRET en .env se usa una clave temporal: funciona, pero las
# sesiones se pierden cada vez que se reinicia el backend.
_SECRETO = (os.getenv("SESSION_SECRET") or secrets.token_hex(32)).encode("utf-8")


def _firmar(contenido: str) -> str:
    firma = hmac.new(_SECRETO, contenido.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(firma).decode("ascii").rstrip("=")


def crear_token(usuario: str) -> str:
    contenido = f"{usuario}.{int(time.time()) + DURACION}"
    return f"{contenido}.{_firmar(contenido)}"


def leer_token(token: str) -> str | None:
    """Devuelve el usuario del token, o None si es inválido o venció."""
    try:
        usuario, vencimiento, firma = token.split(".")
        vence = int(vencimiento)
    except ValueError:
        return None
    if not hmac.compare_digest(firma, _firmar(f"{usuario}.{vencimiento}")):
        return None
    if vence < time.time():
        return None
    return usuario
