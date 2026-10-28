"""Prueba del watchdog del túnel en Linux.

Modo simulado (por defecto): usa tests/fake_cloudflared.py, que imprime una URL
trycloudflare falsa y se muere a los pocos segundos. El chequeo público se hace
contra el backend local (la URL falsa no existe), y GitHub es un servidor falso.

Modo real: CLOUDFLARED_REAL=/ruta/a/cloudflared  -> usa un quick tunnel de verdad
y mata el proceso varias veces para forzar reinicios.

Uso: python3 tests/test_tunel_watchdog.py [ciclos]
"""
import json, os, signal, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CICLOS = int(sys.argv[1]) if len(sys.argv) > 1 else 5
REAL = os.getenv("CLOUDFLARED_REAL")
PUERTO, GH_PUERTO = 8765, 8766
puts = []


class FakeGitHub(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        self.send_response(404); self.end_headers(); self.wfile.write(b"{}")
    def do_PUT(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        puts.append(body["message"])
        self.send_response(201); self.end_headers(); self.wfile.write(b"{}")


def main():
    threading.Thread(target=HTTPServer(("127.0.0.1", GH_PUERTO), FakeGitHub).serve_forever,
                     daemon=True).start()
    tmp = tempfile.mkdtemp()
    env = dict(os.environ, PORT=str(PUERTO), HOST="127.0.0.1", ADMIN_KEY="k",
               DB_PATH=f"{tmp}/a.db", LOG_DIR=f"{tmp}/logs",
               GITHUB_TOKEN="falso", GITHUB_API=f"http://127.0.0.1:{GH_PUERTO}",
               TUNNEL_CHECK_INTERVAL="3" if not REAL else "10", TUNNEL_MAX_FAILS="2",
               TUNNEL_BACKOFF_MIN="1", TUNNEL_BACKOFF_MAX="4", TUNNEL_GRACE="0" if not REAL else "30",
               TUNNEL_URL_TIMEOUT="40")
    if REAL:
        env["CLOUDFLARED_PATH"] = REAL
    else:
        env["CLOUDFLARED_PATH"] = str(ROOT / "tests" / "fake_cloudflared.sh")
        env["FAKE_LIFETIME"] = "8"
    srv = subprocess.Popen([sys.executable, "run.py"], cwd=ROOT, env=env)
    import requests
    H = {"X-Admin-Key": "k"}
    st = lambda: requests.get(f"http://127.0.0.1:{PUERTO}/api/admin/status", headers=H, timeout=5).json()
    try:
        time.sleep(4)
        urls, ok = set(), True
        for i in range(CICLOS):
            # esperar URL nueva
            t0 = time.time()
            while time.time() - t0 < 90:
                s = st()
                if s.get("tunnel_url") and s["tunnel_url"] not in urls: break
                time.sleep(1)
            url = s.get("tunnel_url"); urls.add(url)
            pub = None
            if REAL:
                t1 = time.time()
                while time.time() - t1 < 60:
                    try:
                        pub = requests.get(url + "/health", timeout=10).status_code
                        if pub == 200: break
                    except Exception: pass
                    time.sleep(3)
                # matar cloudflared para forzar reinicio
                subprocess.run(["pkill", "-f", f"{REAL} tunnel"])
            print(f"ciclo {i+1}: url={url} publico={pub} reinicios={s['tunnel_restarts']} "
                  f"puts_github={len(puts)}", flush=True)
            if not url: ok = False
        time.sleep(3)
        s = st()
        al = requests.get(f"http://127.0.0.1:{PUERTO}/api/admin/alertas?desde_id=0", headers=H).json()
        tipos = {a["tipo"] for a in al["alertas"]}
        m = requests.post(f"http://127.0.0.1:{PUERTO}/api/admin/alertas/marcar_leidas",
                          headers=H, json={}).json()
        al2 = requests.get(f"http://127.0.0.1:{PUERTO}/api/admin/alertas?desde_id={al['ultimo_id']}",
                           headers=H).json()
        lan = requests.get(f"http://127.0.0.1:{PUERTO}/api/admin/alertas",
                           headers={**H, "CF-Connecting-IP": "1.2.3.4"}).status_code
        print("estado final:", json.dumps({k: v for k, v in s.items() if k.startswith("tunnel")}))
        print("alertas:", al["no_leidas"], sorted(tipos), "marcadas:", m, "nuevas tras ultimo_id:",
              len(al2["alertas"]), "acceso por tunel:", lan)
        checks = {
            "urls distintas por ciclo": len(urls - {None}) >= CICLOS,
            "reinicios >= ciclos-1": s["tunnel_restarts"] >= CICLOS - 1,
            "github actualizado por URL": len(puts) >= CICLOS,
            "alertas tunel_caido/reiniciado": {"tunel_caido", "tunel_reiniciado", "backend_reiniciado"} <= tipos,
            "marcar_leidas": m["marcadas"] == al["no_leidas"],
            "alertas bloqueadas desde internet": lan == 403,
        }
        for k, v in checks.items(): print(("OK  " if v else "FALLA ") + k)
        sys.exit(0 if ok and all(checks.values()) else 1)
    finally:
        srv.send_signal(signal.SIGINT); time.sleep(2); srv.kill()
        subprocess.run(["pkill", "-f", "fake_cloudflared"])


if __name__ == "__main__":
    main()
