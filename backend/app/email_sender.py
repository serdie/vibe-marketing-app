"""Envío real de emails vía Resend API o SMTP.

Usa el ProviderRegistry: busca un proveedor con task="email" activo y envía.
Si no hay ninguno configurado, lanza EmailProviderMissing (HTTP 400 upstream).
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any

import httpx

from .providers import CATALOG_BY_ID, registry

log = logging.getLogger("email_sender")


class EmailProviderMissing(Exception):
    """No hay ningún proveedor de email configurado."""


class EmailSendError(Exception):
    """Fallo al enviar un email concreto."""


def _pick_email_provider():
    # Preferencia explícita primero
    cfg = registry.choose("email")
    if cfg:
        return cfg
    # Si no, cualquier proveedor activo con task email
    for cfg in registry.all():
        if not cfg.enabled:
            continue
        tasks = CATALOG_BY_ID.get(cfg.id, {}).get("tasks", [])
        if "email" in tasks:
            return cfg
    return None


def send_email(*, to: str, subject: str, html: str, from_name: str | None = None, reply_to: str | None = None) -> dict[str, Any]:
    cfg = _pick_email_provider()
    if cfg is None:
        raise EmailProviderMissing(
            "No hay proveedor de email configurado. Ve a Ajustes → Proveedores y añade Resend o SMTP."
        )
    extra = cfg.extra or {}
    from_email = extra.get("from_email")
    if not from_email:
        raise EmailProviderMissing(
            f"El proveedor {cfg.id} no tiene 'from_email' configurado. "
            "Ve a Ajustes → Proveedores y añádelo (p. ej. hola@tudominio.com)."
        )
    from_header = f"{from_name} <{from_email}>" if from_name else from_email

    if cfg.id == "resend":
        return _send_resend(cfg.api_key, from_header, to, subject, html, reply_to)
    if cfg.id == "smtp":
        return _send_smtp(cfg, from_header, to, subject, html, reply_to)
    raise EmailProviderMissing(f"Proveedor de email no soportado: {cfg.id}")


def _send_resend(api_key: str, from_header: str, to: str, subject: str, html: str, reply_to: str | None) -> dict:
    body = {"from": from_header, "to": [to], "subject": subject, "html": html}
    if reply_to:
        body["reply_to"] = reply_to
    with httpx.Client(timeout=30) as c:
        r = c.post("https://api.resend.com/emails",
                   json=body,
                   headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
        if r.status_code >= 300:
            raise EmailSendError(f"Resend {r.status_code}: {r.text[:500]}")
        data = r.json()
    return {"provider": "resend", "id": data.get("id"), "to": to}


def _send_smtp(cfg, from_header: str, to: str, subject: str, html: str, reply_to: str | None) -> dict:
    extra = cfg.extra or {}
    if not cfg.base_url:
        raise EmailProviderMissing("SMTP sin host. Pon 'host:port' en base_url (ej. smtp.gmail.com:587).")
    host, _, port_s = cfg.base_url.partition(":")
    port = int(port_s or "587")
    user = extra.get("smtp_user") or extra.get("from_email")
    password = cfg.api_key
    use_ssl = extra.get("smtp_ssl") is True or port == 465
    use_starttls = extra.get("smtp_starttls", True) and not use_ssl

    msg = EmailMessage()
    msg["From"] = from_header
    msg["To"] = to
    msg["Subject"] = subject
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.add_alternative(html, subtype="html")

    try:
        if use_ssl:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as s:
                s.login(user, password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as s:
                s.ehlo()
                if use_starttls:
                    s.starttls(context=ssl.create_default_context())
                    s.ehlo()
                s.login(user, password)
                s.send_message(msg)
    except Exception as e:
        raise EmailSendError(f"SMTP {host}:{port} falló: {e}") from e
    return {"provider": "smtp", "host": host, "to": to}
