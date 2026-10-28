"""Cliente mínimo de la API de Mercado Pago con reintentos y backoff."""
import logging
import time
import uuid
import requests
from . import config

log = logging.getLogger("mercadopago")
API = "https://api.mercadopago.com"


def _request(method, path, retries=4, **kw):
    """Hace la llamada y reintenta ante errores de red o 5xx/429 (1s, 2s, 4s...)."""
    headers = kw.pop("headers", {})
    headers["Authorization"] = f"Bearer {config.MP_ACCESS_TOKEN}"
    last = None
    for attempt in range(retries):
        try:
            r = requests.request(method, API + path, headers=headers, timeout=15, **kw)
            if r.status_code < 500 and r.status_code != 429:
                r.raise_for_status()
                return r.json()
            last = RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        except requests.HTTPError:
            raise  # 4xx: error nuestro (token mal, datos mal); no tiene sentido reintentar
        except requests.RequestException as e:
            last = e
        wait = 2 ** attempt
        log.warning("Fallo llamando a MP %s %s (%s). Reintento en %ss", method, path, last, wait)
        time.sleep(wait)
    raise RuntimeError(f"Mercado Pago no respondió: {last}")


def create_preference(price, base_url):
    """Crea una preferencia de Checkout Pro por 1 crédito. Devuelve (pref, external_ref)."""
    external_ref = uuid.uuid4().hex
    body = {
        "items": [{"title": config.ITEM_TITLE, "quantity": 1,
                   "unit_price": float(price), "currency_id": "ARS"}],
        "external_reference": external_ref,
        "notification_url": f"{base_url}/api/mercadopago/webhook?source_news=webhooks",
        "back_urls": {"success": f"{base_url}/pago/exito",
                      "pending": f"{base_url}/pago/pendiente",
                      "failure": f"{base_url}/pago/error"},
        "auto_return": "approved",
        "statement_descriptor": "ARCADE",
    }
    pref = _request("POST", "/checkout/preferences", json=body,
                    headers={"X-Idempotency-Key": external_ref})
    return pref, external_ref


def get_payment(payment_id):
    """Consulta el estado REAL del pago (nunca confiamos solo en el webhook)."""
    return _request("GET", f"/v1/payments/{payment_id}")
