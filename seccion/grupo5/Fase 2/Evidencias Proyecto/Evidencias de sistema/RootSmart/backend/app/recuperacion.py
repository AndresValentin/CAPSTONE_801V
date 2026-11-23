"""Recuperación de contraseña por correo.

El enlace lleva un token aleatorio de un solo uso; en la BD queda solo su hash.
La solicitud responde siempre lo mismo y el trabajo se hace en segundo plano,
para que no se pueda averiguar qué usuarios o correos existen.
"""

import hashlib
import os
import secrets
import smtplib
from email.message import EmailMessage

import pyodbc

from . import claves, db

VIGENCIA_MINUTOS = 30
MAX_SOLICITUDES_POR_HORA = 3


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _enlace(token: str) -> str:
    # Sale de la configuración y no de la solicitud, para que nadie pueda desviar el enlace.
    # Va tras el #, que el navegador no envía a servidores ni a otros sitios.
    base = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").split(",")[0].strip().rstrip("/")
    return f"{base}/recuperar#token={token}"


def _enviar_correo(destino: str, nombre: str, enlace: str) -> None:
    servidor = os.getenv("SMTP_HOST", "")
    if not servidor:
        # Solo para desarrollo: sin servidor de correo el enlace queda en la consola del backend
        print(f"[recuperacion] SMTP_HOST sin configurar. Enlace para {destino}: {enlace}", flush=True)
        return

    usuario = os.getenv("SMTP_USER", "")
    mensaje = EmailMessage()
    mensaje["Subject"] = "Cambia tu contraseña de BI Copilot"
    mensaje["From"] = os.getenv("SMTP_FROM") or usuario
    mensaje["To"] = destino
    mensaje.set_content(
        f"Hola, {nombre}:\n\n"
        f"Para cambiar tu contraseña de BI Copilot entra a este enlace:\n\n{enlace}\n\n"
        f"El enlace funciona una sola vez y vence en {VIGENCIA_MINUTOS} minutos.\n"
        "Si no lo pediste, ignora este correo: tu contraseña no cambiará.\n"
    )
    with smtplib.SMTP(servidor, int(os.getenv("SMTP_PORT", "587")), timeout=15) as smtp:
        smtp.starttls()
        if usuario:
            smtp.login(usuario, os.getenv("SMTP_PASSWORD", ""))
        smtp.send_message(mensaje)


def solicitar(cod_usuario: str) -> None:
    """Crea el enlace y lo envía. Corre en segundo plano: los errores solo van a la consola."""
    try:
        usuario = db.usuario_para_recuperar(cod_usuario.strip().upper())
        if usuario is None:
            return
        token = secrets.token_urlsafe(32)
        if not db.crear_recuperacion(usuario["id"], _hash_token(token), VIGENCIA_MINUTOS, MAX_SOLICITUDES_POR_HORA):
            print(f"[recuperacion] {usuario['usuario']} superó el límite de solicitudes por hora", flush=True)
            return
        _enviar_correo(usuario["correo"], usuario["nombre"], _enlace(token))
    except (pyodbc.Error, smtplib.SMTPException, OSError, ValueError) as e:
        print(f"[recuperacion] no se pudo enviar el correo: {type(e).__name__}: {e}", flush=True)


def restablecer(token: str, clave_nueva: str) -> bool:
    """Cambia la clave si el enlace sigue vigente. Después el enlace ya no sirve."""
    return db.aplicar_recuperacion(_hash_token(token), claves.generar_hash(clave_nueva))
