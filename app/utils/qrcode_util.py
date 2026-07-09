"""Generate a QR-code PNG (in-memory) for a subscription/config link."""
from __future__ import annotations

import io

import qrcode


def make_qr_png(data: str) -> io.BytesIO:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    buf.name = "config_qr.png"
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
