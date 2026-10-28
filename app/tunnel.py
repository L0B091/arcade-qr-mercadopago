"""Túnel gratuito de Cloudflare (quick tunnel, sin cuenta) con watchdog.

Qué hace:
1. Arranca `cloudflared tunnel --no-autoupdate --protocol <auto|http2|quic> --url http://localhost:PUERTO`.
2. Lee su salida hasta encontrar https://xxxx.trycloudflare.com.
3. Guarda la URL en SQLite (se usa como notification_url de Mercado Pago).
4. Sube un index.html al repo de GitHub Pages del cliente que redirige a esa URL (con reintentos).
5. WATCHDOG: cada TUNNEL_CHECK_INTERVAL segundos verifica:
   - que el proceso cloudflared siga vivo,
   - que el backend local responda en http://127.0.0.1:PUERTO/health,
   - que la URL pública responda <tunel>/health (ida y vuelta por Cloudflare).
   Si la URL pública falla TUNNEL_MAX_FAILS veces seguidas (o el proceso murió),
   mata cloudflared y lo vuelve a lanzar con espera exponencial (5s, 10s, 20s… hasta 5 min).
   Si la página de GitHub no se pudo actualizar, lo reintenta en cada chequeo.
Todo queda en el log y en el estado que ve la app de Android (/api/admin/status).
"""
import base64
import logging
import re
import subprocess
import threading
import time
import requests
from . import alertas, config, db

log = logging.getLogger("tunnel")
URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")

# Ajustes del watchdog (opcionales en .env)
PROTOCOL = config._get("TUNNEL_PROTOCOL", "http2")      # http2 | quic | auto
CHECK_INTERVAL = float(config._get("TUNNEL_CHECK_INTERVAL", "30"))
MAX_FAILS = int(config._get("TUNNEL_MAX_FAILS", "3"))
URL_TIMEOUT = float(config._get("TUNNEL_URL_TIMEOUT", "60"))   # espera máx. para que aparezca la URL
BACKOFF_MIN = float(config._get("TUNNEL_BACKOFF_MIN", "5"))
BACKOFF_MAX = float(config._get("TUNNEL_BACKOFF_MAX", "300"))
# Al arrancar, DNS de trycloudflare puede tardar en propagar: no contamos fallas durante este margen
GRACE = float(config._get("TUNNEL_GRACE", "45"))

REDIRECT_HTML = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="0; url={url}">
<title>Arcade</title></head>
<body style="font-family:sans-serif;text-align:center;padding-top:40px">
<p>Redirigiendo al arcade…</p><p><a href="{url}">Tocá acá si no avanza</a></p>
<script>location.replace("{url}");</script>
<!-- actualizado {ts} -->
</body></html>
"""


def public_url():
    """URL pública actual: la fija (túnel con nombre) o la del túnel temporal."""
    return config.PUBLIC_URL or db.get_setting("tunnel_url", "")


def update_github_page(url, retries=5):
    if not (config.GITHUB_TOKEN and config.GITHUB_PAGES_REPO):
        log.warning("GITHUB_TOKEN/GITHUB_PAGES_REPO vacíos: no se actualiza la página del QR")
        return False
    api = f"{config._get('GITHUB_API', 'https://api.github.com')}/repos/{config.GITHUB_PAGES_REPO}/contents/index.html"
    h = {"Authorization": f"Bearer {config.GITHUB_TOKEN}",
         "Accept": "application/vnd.github+json"}
    html = REDIRECT_HTML.format(url=url, ts=db.now())
    for attempt in range(retries):
        try:
            r = requests.get(api, headers=h, params={"ref": config.GITHUB_PAGES_BRANCH}, timeout=15)
            sha = r.json().get("sha") if r.status_code == 200 else None
            body = {"message": f"Arcade: nueva URL {url}",
                    "content": base64.b64encode(html.encode()).decode(),
                    "branch": config.GITHUB_PAGES_BRANCH}
            if sha:
                body["sha"] = sha
            r = requests.put(api, headers=h, json=body, timeout=15)
            if r.status_code in (200, 201):
                log.info("Página del QR actualizada -> %s", url)
                db.set_setting("github_page_updated", db.now())
                db.set_setting("github_page_url", url)
                return True
            log.error("GitHub respondió %s: %s", r.status_code, r.text[:200])
            err = f"HTTP {r.status_code}"
        except (requests.RequestException, ValueError) as e:
            log.error("Error actualizando GitHub: %s", e)
            err = str(e)
        time.sleep(min(2 ** attempt, 30))
    alertas.registrar("github_pages_fallo", f"No se pudo actualizar la página del QR a {url}: {err}")
    return False


def _get_ok(url, timeout=10):
    try:
        return requests.get(url, timeout=timeout).status_code == 200
    except requests.RequestException:
        return False


class QuickTunnel:
    def __init__(self):
        self.proc = None
        self.url = ""
        self.restarts = 0
        self.last_restart = None
        self.last_reason = None
        self.fails = 0
        self.last_check = None
        self.last_ok = None
        self.local_ok = None
        self._url_event = threading.Event()
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True, name="tunnel")

    # ---------- ciclo de vida ----------
    def start(self):
        if config.PUBLIC_URL:
            log.info("Usando URL fija (túnel con nombre): %s", config.PUBLIC_URL)
            return
        if config.DISABLE_TUNNEL:
            log.info("Túnel desactivado por configuración")
            return
        self.thread.start()

    def stop(self):
        self._stop.set()
        self._kill()

    def status(self):
        return {"tunnel_url": self.url or None,
                "tunnel_alive": bool(self.proc and self.proc.poll() is None),
                "tunnel_protocol": PROTOCOL,
                "tunnel_restarts": self.restarts,
                "tunnel_last_restart": self.last_restart,
                "tunnel_last_restart_reason": self.last_reason,
                "tunnel_consecutive_fails": self.fails,
                "tunnel_last_check": self.last_check,
                "tunnel_last_ok": self.last_ok,
                "backend_local_ok": self.local_ok}

    # ---------- cloudflared ----------
    def _cmd(self):
        cmd = [config.CLOUDFLARED_PATH, "tunnel", "--no-autoupdate"]
        if PROTOCOL in ("http2", "quic", "auto"):
            cmd += ["--protocol", PROTOCOL]
        return cmd + ["--url", f"http://localhost:{config.PORT}"]

    def _launch(self):
        self.url = ""
        self._url_event.clear()
        db.set_setting("tunnel_url", "")
        log.info("Arrancando cloudflared: %s", " ".join(self._cmd()))
        self.proc = subprocess.Popen(
            self._cmd(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        threading.Thread(target=self._reader, args=(self.proc,), daemon=True).start()

    def _reader(self, proc):
        """Lee la salida de cloudflared (si no se lee, el buffer se llena y se cuelga)."""
        try:
            for line in proc.stdout:
                m = URL_RE.search(line)
                if m and proc is self.proc and not self.url:
                    self.url = m.group(0)
                    log.info("Túnel activo: %s", self.url)
                    db.set_setting("tunnel_url", self.url)
                    db.set_setting("tunnel_started", db.now())
                    self._url_event.set()
                    alertas.registrar("tunel_activo", f"Túnel activo en {self.url}", "info")
                    threading.Thread(target=update_github_page, args=(self.url,),
                                     daemon=True).start()
        except Exception:
            pass

    def _kill(self):
        p = self.proc
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(10)
            except subprocess.TimeoutExpired:
                p.kill()

    # ---------- watchdog ----------
    def _run(self):
        backoff = BACKOFF_MIN
        while not self._stop.is_set():
            reason = None
            try:
                self._launch()
                if not self._url_event.wait(URL_TIMEOUT):
                    reason = "cloudflared no entregó URL a tiempo"
                else:
                    started = time.time()
                    self.fails = 0
                    reason = self._watch(started)
                    if reason and time.time() - started > 600:
                        backoff = BACKOFF_MIN   # anduvo bien un buen rato: reiniciamos la espera
            except FileNotFoundError:
                reason = f"no encuentro cloudflared en '{config.CLOUDFLARED_PATH}'"
            except Exception as e:
                log.exception("Error en el túnel")
                reason = f"error: {e}"
            if self._stop.is_set():
                break
            self._kill()
            db.set_setting("tunnel_url", "")
            self.restarts += 1
            self.last_restart = db.now()
            self.last_reason = reason
            db.set_setting("tunnel_restarts_total",
                           int(db.get_setting("tunnel_restarts_total", 0) or 0) + 1)
            log.error("Reinicio de túnel #%d: %s. Espero %.0fs", self.restarts, reason, backoff)
            alertas.registrar("tunel_caido", reason, "error")
            alertas.registrar("tunel_reiniciado",
                              f"Reinicio #{self.restarts}, próximo intento en {backoff:.0f}s", "warning")
            self._stop.wait(backoff)
            backoff = min(backoff * 2, BACKOFF_MAX)

    def _watch(self, started):
        """Devuelve el motivo del reinicio (o None si se pidió parar)."""
        while not self._stop.wait(CHECK_INTERVAL):
            self.last_check = db.now()
            if self.proc.poll() is not None:
                return f"cloudflared terminó (código {self.proc.returncode})"
            self.local_ok = _get_ok(f"http://127.0.0.1:{config.PORT}/health", 5)
            if not self.local_ok:
                # Si el backend local no responde, reiniciar el túnel no sirve: lo resuelve start.bat
                log.error("El backend local no responde en /health")
                alertas.registrar("backend_sin_respuesta", "El backend local no responde en /health")
                continue
            if _get_ok(f"{self.url}/health", 15):
                self.fails = 0
                self.last_ok = db.now()
                if db.get_setting("github_page_url", "") != self.url:
                    threading.Thread(target=update_github_page, args=(self.url, 2),
                                     daemon=True).start()
                continue
            if time.time() - started < GRACE:
                continue
            self.fails += 1
            alertas.registrar("tunel_sin_respuesta", f"Chequeo {self.fails + 1}/{MAX_FAILS} falló", "warning")
            log.warning("Túnel sin respuesta (%d/%d) en %s", self.fails, MAX_FAILS, self.url)
            if self.fails >= MAX_FAILS:
                return f"{self.fails} chequeos públicos fallidos"
        return None
