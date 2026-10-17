"""TOTP helpers: secret generation, verification, otpauth URIs and QR PNGs."""

from __future__ import annotations

import base64
import io

import pyotp
import qrcode

ISSUER = "团校积分系统"


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def verify_totp(secret: str, code: str, *, window: int = 1) -> bool:
    """Verify a 6-digit TOTP code allowing +/- one 30s window for clock drift."""
    code = (code or "").strip().replace(" ", "")
    if not code.isdigit() or len(code) != 6:
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=window)


def provisioning_uri(secret: str, account_name: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=account_name, issuer_name=ISSUER)


def qr_png_bytes(uri: str) -> bytes:
    image = qrcode.make(uri)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def qr_png_data_uri(uri: str) -> str:
    return "data:image/png;base64," + base64.b64encode(qr_png_bytes(uri)).decode("ascii")
