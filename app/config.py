"""Configuración central: lee el archivo .env y expone valores tipados."""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _get(name, default=""):
    return os.getenv(name, default).strip()


MP_ACCESS_TOKEN = _get("MP_ACCESS_TOKEN")
MP_WEBHOOK_SECRET = _get("MP_WEBHOOK_SECRET")
DEFAULT_PRICE = float(_get("DEFAULT_PRICE", "2000"))
ITEM_TITLE = _get("ITEM_TITLE", "1 crédito Arcade")

HOST = _get("HOST", "0.0.0.0")
PORT = int(_get("PORT", "8000"))

CREDIT_KEY = _get("CREDIT_KEY", "5")
KEY_PRESS_DURATION = float(_get("KEY_PRESS_DURATION", "0.08"))
KEY_PRESS_DELAY = float(_get("KEY_PRESS_DELAY", "0.25"))
FOCUS_EMULATOR = _get("FOCUS_EMULATOR", "1") == "1"

ADMIN_KEY = _get("ADMIN_KEY")

GITHUB_TOKEN = _get("GITHUB_TOKEN")
GITHUB_PAGES_REPO = _get("GITHUB_PAGES_REPO", "frarcade-26/frarcade-26.github.io")
# URL fija que va impresa en el QR del gabinete (página de GitHub Pages del cliente)
QR_URL = _get("QR_URL", "https://frarcade-26.github.io/")
GITHUB_PAGES_BRANCH = _get("GITHUB_PAGES_BRANCH", "main")

CLOUDFLARED_PATH = _get("CLOUDFLARED_PATH", "cloudflared.exe")
PUBLIC_URL = _get("PUBLIC_URL").rstrip("/")
# Desactiva el arranque automático del túnel (útil para pruebas)
DISABLE_TUNNEL = _get("DISABLE_TUNNEL", "0") == "1"

DB_PATH = BASE_DIR / _get("DB_PATH", "data/arcade.db")
LOG_DIR = BASE_DIR / _get("LOG_DIR", "logs")
