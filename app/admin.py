"""API de administración para la app Android (solo WiFi local).

Protecciones:
- Header X-Admin-Key igual a ADMIN_KEY del .env.
- La IP de origen tiene que ser privada (192.168.x, 10.x, 172.16-31.x) o localhost.
- Se rechaza todo lo que llega por el túnel (Cloudflare agrega cf-connecting-ip / cf-ray).
  Ojo: cloudflared conecta desde 127.0.0.1, por eso el chequeo de headers es clave.
"""
import hmac
import ipaddress
import time
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from . import config, db, tunnel

router = APIRouter(prefix="/api/admin", tags=["admin"])
STARTED = time.time()
CF_HEADERS = ("cf-connecting-ip", "cf-ray", "cf-ipcountry", "cf-visitor", "x-forwarded-for")


def require_local_admin(request: Request, x_admin_key: str = Header(default="")):
    if any(h in request.headers for h in CF_HEADERS):
        raise HTTPException(403, "La administración solo funciona desde el WiFi del local")
    try:
        ip = ipaddress.ip_address(request.client.host if request.client else "")
    except ValueError:
        raise HTTPException(403, "IP inválida")
    if not (ip.is_private or ip.is_loopback):
        raise HTTPException(403, "La administración solo funciona desde el WiFi del local")
    if not config.ADMIN_KEY or not hmac.compare_digest(x_admin_key, config.ADMIN_KEY):
        raise HTTPException(401, "Clave de administrador incorrecta")


class PriceIn(BaseModel):
    price: float = Field(gt=0, le=1_000_000)


@router.get("/stats", dependencies=[Depends(require_local_admin)])
def stats():
    return {"currency": "ARS", "price": db.get_price(), **db.stats()}


@router.get("/payments", dependencies=[Depends(require_local_admin)])
def payments(limit: int = 50, offset: int = 0):
    return {"items": db.list_payments(min(limit, 500), max(offset, 0))}


@router.get("/status", dependencies=[Depends(require_local_admin)])
def status():
    return {"ok": True, "uptime_s": int(time.time() - STARTED),
            "tunnel_url": tunnel.public_url() or None,
            "tunnel_started": db.get_setting("tunnel_started"),
            "github_page_updated": db.get_setting("github_page_updated"),
            "last_webhook": db.get_setting("last_webhook"),
            "credit_key": config.CREDIT_KEY,
            "mp_configured": bool(config.MP_ACCESS_TOKEN and config.MP_WEBHOOK_SECRET)}


@router.put("/price", dependencies=[Depends(require_local_admin)])
def set_price(body: PriceIn):
    db.set_setting("price", round(body.price, 2))
    return {"price": db.get_price()}
