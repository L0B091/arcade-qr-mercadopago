"""Base SQLite: pagos, créditos pendientes y ajustes (precio, URL del túnel).

Todo se guarda en disco, así un reinicio o corte de luz no pierde nada.
"""
import sqlite3
import threading
from datetime import datetime, timedelta
from . import config

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS payments (
    payment_id      TEXT PRIMARY KEY,      -- id del pago en Mercado Pago (idempotencia)
    external_ref    TEXT,
    status          TEXT NOT NULL,         -- approved / pending / rejected / ...
    status_detail   TEXT,
    amount          REAL,
    credits         INTEGER NOT NULL DEFAULT 1,
    credited        INTEGER NOT NULL DEFAULT 0, -- 1 = crédito ya cargado en el juego
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS preferences (
    external_ref    TEXT PRIMARY KEY,
    preference_id   TEXT,
    price           REAL,
    created_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def now():
    return datetime.now().isoformat(timespec="seconds")


def connect():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    with _lock, connect() as c:
        c.executescript(SCHEMA)
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('price',?)",
                  (str(config.DEFAULT_PRICE),))


# ---------- ajustes ----------
def get_setting(key, default=None):
    with connect() as c:
        r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


def set_setting(key, value):
    with _lock, connect() as c:
        c.execute("INSERT INTO settings(key,value) VALUES(?,?) "
                  "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))


def get_price():
    return float(get_setting("price", config.DEFAULT_PRICE))


# ---------- preferencias ----------
def save_preference(external_ref, preference_id, price):
    with _lock, connect() as c:
        c.execute("INSERT OR REPLACE INTO preferences VALUES(?,?,?,?)",
                  (external_ref, preference_id, price, now()))


# ---------- pagos ----------
def upsert_payment(payment_id, status, status_detail, amount, external_ref, credits=1):
    """Guarda o actualiza un pago. Devuelve True si quedó APROBADO y todavía
    no fue acreditado, y lo marca como 'en cola' de forma atómica.
    Así, aunque Mercado Pago mande el mismo aviso 10 veces, el crédito se carga una sola vez.
    """
    with _lock, connect() as c:
        row = c.execute("SELECT credited FROM payments WHERE payment_id=?",
                        (str(payment_id),)).fetchone()
        if row is None:
            c.execute("INSERT INTO payments VALUES(?,?,?,?,?,?,0,?,?)",
                      (str(payment_id), external_ref, status, status_detail, amount,
                       credits, now(), now()))
            credited = 0
        else:
            c.execute("UPDATE payments SET status=?, status_detail=?, amount=?, updated_at=? "
                      "WHERE payment_id=?",
                      (status, status_detail, amount, now(), str(payment_id)))
            credited = row["credited"]
        if status == "approved" and credited == 0:
            # 2 = en cola para acreditar (persistido: si se reinicia se reintenta)
            c.execute("UPDATE payments SET credited=2 WHERE payment_id=?", (str(payment_id),))
            return True
        return False


def mark_credited(payment_id):
    with _lock, connect() as c:
        c.execute("UPDATE payments SET credited=1, updated_at=? WHERE payment_id=?",
                  (now(), str(payment_id)))


def pending_credits():
    """Pagos aprobados que quedaron en cola sin acreditar (ej. se cortó la luz)."""
    with connect() as c:
        return [dict(r) for r in c.execute(
            "SELECT payment_id, credits FROM payments WHERE credited=2 ORDER BY created_at")]


def list_payments(limit=100, offset=0):
    with connect() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM payments ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset))]


def stats():
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    week = today - timedelta(days=today.weekday())  # desde el lunes
    q = ("SELECT COALESCE(SUM(amount),0) AS income, COALESCE(SUM(credits),0) AS credits, "
         "COUNT(*) AS n FROM payments WHERE status='approved' AND created_at>=?")
    out = {}
    with connect() as c:
        for name, since in (("today", today), ("week", week), ("total", datetime(1970, 1, 1))):
            r = c.execute(q, (since.isoformat(),)).fetchone()
            out[name] = {"income": r["income"], "credits": r["credits"], "payments": r["n"]}
        out["credits_used"] = c.execute(
            "SELECT COALESCE(SUM(credits),0) FROM payments WHERE credited=1").fetchone()[0]
        out["credits_pending"] = c.execute(
            "SELECT COALESCE(SUM(credits),0) FROM payments WHERE credited=2").fetchone()[0]
    return out
