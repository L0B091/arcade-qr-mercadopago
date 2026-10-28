"""Alertas del vigilante: eventos importantes guardados en SQLite (tabla `alertas`).

La app de Android los consulta con GET /api/admin/alertas?desde_id=N.
Nunca debe romper el flujo principal: si falla el guardado, solo se loguea.
"""
import logging
from . import db

log = logging.getLogger("alertas")
NIVELES = ("info", "warning", "error")

SCHEMA = """
CREATE TABLE IF NOT EXISTS alertas (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha    TEXT NOT NULL,
    nivel    TEXT NOT NULL,          -- info / warning / error
    tipo     TEXT NOT NULL,          -- tunel_caido, tunel_reiniciado, github_pages_fallo, ...
    mensaje  TEXT,
    leida    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_alertas_leida ON alertas(leida);
"""


def init():
    with db._lock, db.connect() as c:
        c.executescript(SCHEMA)


def registrar(tipo, mensaje="", nivel="error"):
    if nivel not in NIVELES:
        nivel = "error"
    try:
        with db._lock, db.connect() as c:
            c.executescript(SCHEMA)
            c.execute("INSERT INTO alertas(fecha,nivel,tipo,mensaje) VALUES(?,?,?,?)",
                      (db.now(), nivel, tipo, str(mensaje)[:500]))
    except Exception as e:  # nunca romper el cobro por una alerta
        log.error("No pude guardar la alerta %s: %s", tipo, e)


def listar(desde_id=0, limite=100, solo_no_leidas=False):
    """Alertas con id > desde_id, las más nuevas primero."""
    q = "SELECT * FROM alertas WHERE id > ?" + (" AND leida=0" if solo_no_leidas else "")
    with db.connect() as c:
        rows = c.execute(q + " ORDER BY id DESC LIMIT ?", (int(desde_id), int(limite))).fetchall()
        no_leidas = c.execute("SELECT COUNT(*) FROM alertas WHERE leida=0").fetchone()[0]
        ultimo = c.execute("SELECT COALESCE(MAX(id),0) FROM alertas").fetchone()[0]
    return {"alertas": [{**dict(r), "leida": bool(r["leida"])} for r in rows],
            "no_leidas": no_leidas, "ultimo_id": ultimo}


def marcar_leidas(ids=None, hasta_id=None):
    with db._lock, db.connect() as c:
        if ids:
            ph = ",".join("?" * len(ids))
            cur = c.execute(f"UPDATE alertas SET leida=1 WHERE leida=0 AND id IN ({ph})",
                            [int(i) for i in ids])
        elif hasta_id is not None:
            cur = c.execute("UPDATE alertas SET leida=1 WHERE leida=0 AND id<=?", (int(hasta_id),))
        else:
            cur = c.execute("UPDATE alertas SET leida=1 WHERE leida=0")
        return cur.rowcount
