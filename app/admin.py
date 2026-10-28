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
import base64
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
from . import alertas, config, db, qr, tunnel

router = APIRouter(prefix="/api/admin", tags=["admin"])
STARTED = time.time()
CF_HEADERS = ("cf-connecting-ip", "cf-ray", "cf-ipcountry", "cf-visitor", "x-forwarded-for")


def _check_lan(request: Request):
    if any(h in request.headers for h in CF_HEADERS):
        raise HTTPException(403, "La administración solo funciona desde el WiFi del local")
    try:
        ip = ipaddress.ip_address(request.client.host if request.client else "")
    except ValueError:
        raise HTTPException(403, "IP inválida")
    if not (ip.is_private or ip.is_loopback):
        raise HTTPException(403, "La administración solo funciona desde el WiFi del local")


def _check_key(key: str):
    if not config.ADMIN_KEY or not hmac.compare_digest(key or "", config.ADMIN_KEY):
        raise HTTPException(401, "Clave de administrador incorrecta")


def require_local_admin(request: Request, x_admin_key: str = Header(default="")):
    _check_lan(request)
    _check_key(x_admin_key)


def _tunnel_status():
    """Estado del watchdog del túnel (reinicios, último reinicio, URL actual)."""
    from .main import quick_tunnel
    st = quick_tunnel.status()
    st["tunnel_url"] = tunnel.public_url() or None
    return st


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
            "tunnel_restarts_total": int(db.get_setting("tunnel_restarts_total", 0) or 0),
            **_tunnel_status(),
            "github_page_updated": db.get_setting("github_page_updated"),
            "last_webhook": db.get_setting("last_webhook"),
            "credit_key": config.CREDIT_KEY,
            "mp_configured": bool(config.MP_ACCESS_TOKEN and config.MP_WEBHOOK_SECRET)}


@router.put("/price", dependencies=[Depends(require_local_admin)])
def set_price(body: PriceIn):
    db.set_setting("price", round(body.price, 2))
    return {"price": db.get_price()}


@router.get("/qr.png", dependencies=[Depends(require_local_admin)])
def qr_png():
    """PNG del QR fijo del gabinete (para descargar e imprimir desde Android)."""
    return Response(qr.make_png(), media_type="image/png",
                    headers={"Content-Disposition": 'inline; filename="qr_arcade.png"'})


# Página imprimible: el navegador no puede mandar headers, así que SOLO acá
# se acepta la clave por ?key=. Sigue siendo solo WiFi local.
print_router = APIRouter(tags=["admin"])


@print_router.get("/admin/qr/imprimir", response_class=HTMLResponse)
def qr_imprimir(request: Request, key: str = Query(default="")):
    _check_lan(request)
    _check_key(key)
    src = "data:image/png;base64," + base64.b64encode(qr.make_png()).decode()
    return HTMLResponse(qr.print_html(src), headers={"Cache-Control": "no-store",
                                                      "Referrer-Policy": "no-referrer"})


# ---------- Alertas del vigilante ----------
class MarcarIn(BaseModel):
    ids: list[int] | None = None   # marcar estas
    hasta_id: int | None = None    # o todas hasta este id (si no se manda nada: todas)


@router.get("/alertas", dependencies=[Depends(require_local_admin)])
def get_alertas(desde_id: int = 0, limite: int = Query(default=100, ge=1, le=500),
                solo_no_leidas: bool = False):
    return alertas.listar(desde_id, limite, solo_no_leidas)


@router.post("/alertas/marcar_leidas", dependencies=[Depends(require_local_admin)])
def post_marcar_leidas(body: MarcarIn | None = None):
    body = body or MarcarIn()
    return {"marcadas": alertas.marcar_leidas(body.ids, body.hasta_id)}
