"""Deterministic standard QR downloads for the configured canonical URL."""

from io import BytesIO
from typing import Literal

import segno

from app.config import public_url


def qr_bytes(url: str, *, kind: Literal["svg", "png"]) -> bytes:
    """Encode one canonical HTTPS destination with visible background/quiet zone."""
    code = segno.make_qr(public_url(url), error="m")
    output = BytesIO()
    code.save(output, kind=kind, scale=8, border=4, dark="black", light="white")
    return output.getvalue()
