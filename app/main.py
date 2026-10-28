"""Servidor principal del arcade (FastAPI).

Rutas públicas (pasan por el túnel):
  GET  /                         página con el botón "Pagar 1 crédito"
  POST /pagar                    crea la preferencia y redirige a Mercado Pago
  GET  /pago/exito|pendiente|error   páginas de vuelta
  POST /api/mercadopago/webhook  avisos de Mercado Pago
Rutas privadas (solo WiFi local): /api/admin/*  (ver admin.py)
"""
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from . import admin, alertas, config, db, logger, mercadopago, tunnel, webhook
from .credits import CreditWorker

logger.setup()
log = logging.getLogger("main")
TEMPLATES = Path(__file__).parent / "templates"
worker = CreditWorker()
quick_tunnel = tunnel.QuickTunnel()


@asynccontextmanager
async def lifespan(app):
    db.init()
    alertas.init()
    alertas.registrar("backend_reiniciado", "El servidor del arcade arrancó", "info")
    worker.start()
    quick_tunnel.start()
    log.info("Arcade listo en puerto %s. Precio actual: $%s", config.PORT, db.get_price())
    yield
    quick_tunnel.stop()


app = FastAPI(title="Arcade QR", lifespan=lifespan, docs_url=None, redoc_url=None)
app.include_router(admin.router)
app.include_router(admin.print_router)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


def render(name, **vals):
    html = (TEMPLATES / name).read_text(encoding="utf-8")
    for k, v in vals.items():
        html = html.replace("{{" + k + "}}", str(v))
    return HTMLResponse(html)


def fmt_price(p):
    return f"{p:,.0f}".replace(",", ".")


@app.get("/", response_class=HTMLResponse)
def home():
    return render("index.html", price=fmt_price(db.get_price()))


@app.post("/pagar")
def pagar(request: Request):
    base = tunnel.public_url()
    if not base:
        # Sin túnel no llegarían los avisos de pago: mejor no cobrar
        log.error("Intento de pago sin URL pública (túnel caído)")
        alertas.registrar("tunel_caido", "Un jugador intentó pagar sin túnel activo", "warning")
        return render("result.html", title="Arcade fuera de servicio",
                      msg="No hay conexión con internet. Probá en un minuto.", icon="⚠️")
    price = db.get_price()
    try:
        pref, ref = mercadopago.create_preference(price, base)
    except Exception as e:
        log.error("No se pudo crear la preferencia: %s", e)
        alertas.registrar("excepcion", f"No se pudo crear la preferencia: {e}")
        return render("result.html", title="Error", icon="⚠️",
                      msg="No pudimos iniciar el pago. Probá de nuevo.")
    db.save_preference(ref, pref.get("id"), price)
    log.info("Preferencia creada %s (ref %s) por $%s", pref.get("id"), ref, price)
    return RedirectResponse(pref["init_point"], status_code=303)


@app.get("/pago/exito", response_class=HTMLResponse)
def exito():
    return render("result.html", title="¡Pago aprobado!", icon="🎮",
                  msg="Tu crédito se carga en unos segundos. ¡A jugar!")


@app.get("/pago/pendiente", response_class=HTMLResponse)
def pendiente():
    return render("result.html", title="Pago pendiente", icon="⏳",
                  msg="Cuando Mercado Pago lo apruebe, el crédito se carga solo.")


@app.get("/pago/error", response_class=HTMLResponse)
def error():
    return render("result.html", title="Pago no realizado", icon="❌",
                  msg="No se cobró nada. Podés intentarlo de nuevo.")


def process_payment(payment_id):
    """Consulta el pago real en MP, lo registra y, si está aprobado, encola el crédito."""
    try:
        p = mercadopago.get_payment(payment_id)
    except Exception as e:
        log.error("No pude consultar el pago %s: %s (MP reintentará el aviso)", payment_id, e)
        alertas.registrar("pago_error_consulta", f"Pago {payment_id}: {e}", "warning")
        return
    status = p.get("status")
    amount = p.get("transaction_amount")
    should_credit = db.upsert_payment(payment_id, status, p.get("status_detail"),
                                      amount, p.get("external_reference"), credits=1)
    log.info("Pago %s: estado=%s monto=$%s", payment_id, status, amount)
    if should_credit:
        worker.enqueue(payment_id, 1)
    elif status == "approved":
        log.info("Pago %s ya estaba acreditado: se ignora (idempotencia)", payment_id)


@app.post("/api/mercadopago/webhook")
async def mp_webhook(request: Request, background: BackgroundTasks):
    q = request.query_params
    try:
        body = await request.json()
    except Exception:
        body = {}
    topic = q.get("type") or q.get("topic") or body.get("type") or body.get("topic")
    data_id = q.get("data.id") or (body.get("data") or {}).get("id") or q.get("id")
    db.set_setting("last_webhook", db.now())

    if not webhook.validate(config.MP_WEBHOOK_SECRET, request.headers.get("x-signature"),
                            request.headers.get("x-request-id"), data_id):
        log.warning("Webhook con firma INVÁLIDA rechazado (id=%s)", data_id)
        alertas.registrar("webhook_firma_invalida", f"Aviso rechazado (id={data_id})", "warning")
        return JSONResponse({"error": "firma inválida"}, status_code=401)

    if topic != "payment" or not data_id:
        log.info("Webhook ignorado (tipo=%s)", topic)
        return {"ok": True}
    # Respondemos 200 enseguida y procesamos aparte (MP exige respuesta rápida)
    background.add_task(process_payment, str(data_id))
    return {"ok": True}


@app.get("/health")
def health():
    """Lo usa el watchdog del túnel (local y a través de Cloudflare)."""
    return {"ok": True, "ts": int(time.time())}


@app.exception_handler(Exception)
async def _excepcion(request: Request, exc: Exception):
    """Cualquier error no previsto queda como alerta para la app de Android."""
    log.exception("Error no previsto en %s", request.url.path)
    alertas.registrar("excepcion", f"{request.url.path}: {type(exc).__name__}: {exc}")
    return JSONResponse({"error": "error interno"}, status_code=500)
