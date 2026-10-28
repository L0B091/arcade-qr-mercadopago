"""Validación de la firma x-signature de los webhooks de Mercado Pago.

Header: x-signature: ts=1704908010,v1=618c8534...
Manifest: id:<data.id>;request-id:<x-request-id>;ts:<ts>;
v1 = HMAC-SHA256(clave_secreta, manifest) en hexadecimal.
"""
import hashlib
import hmac
import time


def parse_signature(header):
    parts = {}
    for item in (header or "").split(","):
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k.strip()] = v.strip()
    return parts.get("ts"), parts.get("v1")


def build_manifest(data_id, request_id, ts):
    m = ""
    if data_id:
        # MP indica que si el id es alfanumérico va en minúsculas
        m += f"id:{str(data_id).lower()};"
    if request_id:
        m += f"request-id:{request_id};"
    if ts:
        m += f"ts:{ts};"
    return m


def validate(secret, x_signature, x_request_id, data_id, max_age_s=None):
    """True si la firma es válida. max_age_s opcional para rechazar avisos viejos."""
    if not secret or not x_signature:
        return False
    ts, v1 = parse_signature(x_signature)
    if not ts or not v1:
        return False
    if max_age_s:
        try:
            t = int(ts) / (1000 if len(ts) > 11 else 1)
            if abs(time.time() - t) > max_age_s:
                return False
        except ValueError:
            return False
    manifest = build_manifest(data_id, x_request_id, ts)
    expected = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, v1)
