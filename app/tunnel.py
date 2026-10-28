"""Túnel gratuito de Cloudflare + actualización de la página de redirección en GitHub Pages.

1. Arranca `cloudflared tunnel --url http://localhost:PUERTO`.
2. Lee su salida hasta encontrar https://xxxx.trycloudflare.com.
3. Guarda la URL en SQLite (se usa como notification_url).
4. Sube un index.html al repo de GitHub Pages del cliente que redirige a esa URL.
Si cloudflared se cae, lo vuelve a arrancar solo.
"""
import base64
import logging
import re
import subprocess
import threading
import time
import requests
from . import config, db

log = logging.getLogger("tunnel")
URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")

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
    api = f"https://api.github.com/repos/{config.GITHUB_PAGES_REPO}/contents/index.html"
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
                return True
            log.error("GitHub respondió %s: %s", r.status_code, r.text[:200])
        except requests.RequestException as e:
            log.error("Error actualizando GitHub: %s", e)
        time.sleep(2 ** attempt)
    return False


class QuickTunnel:
    def __init__(self):
        self.proc = None
        self.thread = threading.Thread(target=self._run, daemon=True, name="tunnel")

    def start(self):
        if config.PUBLIC_URL:
            log.info("Usando URL fija (túnel con nombre): %s", config.PUBLIC_URL)
            return
        if config.DISABLE_TUNNEL:
            log.info("Túnel desactivado por configuración")
            return
        self.thread.start()

    def _run(self):
        while True:
            try:
                log.info("Arrancando cloudflared…")
                self.proc = subprocess.Popen(
                    [config.CLOUDFLARED_PATH, "tunnel", "--no-autoupdate",
                     "--url", f"http://localhost:{config.PORT}"],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                for line in self.proc.stdout:
                    m = URL_RE.search(line)
                    if m:
                        url = m.group(0)
                        log.info("Túnel activo: %s", url)
                        db.set_setting("tunnel_url", url)
                        db.set_setting("tunnel_started", db.now())
                        threading.Thread(target=update_github_page, args=(url,),
                                         daemon=True).start()
                self.proc.wait()
                log.error("cloudflared terminó (código %s). Reinicio en 10s", self.proc.returncode)
            except FileNotFoundError:
                log.error("No encuentro cloudflared en '%s'. Revisá CLOUDFLARED_PATH",
                          config.CLOUDFLARED_PATH)
            except Exception as e:
                log.exception("Error en el túnel: %s", e)
            db.set_setting("tunnel_url", "")
            time.sleep(10)

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
