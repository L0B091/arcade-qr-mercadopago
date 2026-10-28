# Arcade QR + Mercado Pago

Sistema de cobro por QR para **un gabinete arcade** con PC Windows. El jugador escanea el QR, paga **1 crédito** con Mercado Pago y el crédito se carga solo en el emulador abierto (MAME, SNES9x, FCEUX, VisualBoyAdvance, Project64, ePSXe, PCSX2, Kega Fusion o juegos de PC).

## Cómo funciona

```
QR fijo ─► frarcade-26.github.io (redirige) ─► https://xxxx.trycloudflare.com ─► PC del arcade :8000
                                                                             │
Jugador toca "Pagar 1 crédito" ─► Checkout Pro de Mercado Pago ─► paga       │
Mercado Pago ─► webhook (notification_url) ─► valida firma ─► consulta pago ─► SQLite ─► tecla de moneda
App Android (WiFi local) ─► http://192.168.1.50:8000/api/admin/*
```

- **Túnel gratis**: al arrancar, el servidor lanza `cloudflared`, lee la URL `trycloudflare.com` nueva y la sube al `index.html` del repo de GitHub Pages del cliente. El QR apunta a esa página fija, así que **nunca hay que reimprimirlo**.
- **Webhook sin configurar URL**: cada preferencia lleva `notification_url` con la URL del túnel del momento.
- **Seguridad**: firma `x-signature` (HMAC-SHA256), consulta del estado real con `GET /v1/payments/{id}`, idempotencia por `payment_id`.
- **Sin pérdidas**: cada pago y cada crédito pendiente queda en SQLite; si se corta la luz, los créditos aprobados que faltaban se cargan al reiniciar.
- **Precio**: guardado en SQLite (por defecto $2000), se cambia en vivo desde la app.

## QR del gabinete

<img src="docs/qr/qr_arcade.png" alt="QR del arcade" width="260">

Apunta a `QR_URL` (por defecto `https://frarcade-26.github.io/`), la página fija de GitHub Pages del cliente. `tunnel.py` actualiza el `index.html` de `GITHUB_PAGES_REPO` (`frarcade-26/frarcade-26.github.io`) con la URL del túnel en cada arranque, así el QR impreso no cambia nunca. Archivos: [PNG](docs/qr/qr_arcade.png) · [SVG](docs/qr/qr_arcade.svg) · [Sticker A6 (PDF)](docs/qr/sticker_A6.pdf). La app Android lo puede imprimir con `GET /admin/qr/imprimir` (ver `docs/API_APP_ANDROID.md`).

## Estructura

```
app/
  main.py         rutas web y webhook
  config.py       lectura del .env
  db.py           SQLite: pagos, ajustes, estadísticas
  mercadopago.py  API de MP con reintentos
  webhook.py      validación de firma
  credits.py      cola + SendInput (tecla de moneda)
  tunnel.py       cloudflared + página de GitHub Pages
  admin.py        API para la app Android (solo LAN)
  logger.py       log rotativo en logs/arcade.log
  templates/ static/
app/qr.py       genera el QR (PNG/SVG/página imprimible)
tools/generar_qr.py   regenera docs/qr/ con QR_URL
docs/qr/        QR listo: qr_arcade.png, qr_arcade.svg, sticker_A6.pdf
tools/probar_tecla.py prueba la tecla de crédito
tests/test_basico.py  pruebas (firma, idempotencia, flujo completo)
install.bat  start.bat  instalar_inicio_automatico.bat
docs/MANUAL_CLIENTE.md  docs/API_APP_ANDROID.md
```

## Instalación en la PC del arcade (Windows)

1. Instalá **Python 3.10+** desde <https://www.python.org/downloads/> tildando **"Add python.exe to PATH"**.
2. Descargá este proyecto (botón verde *Code → Download ZIP*) y descomprimilo en `C:\arcade-qr`.
3. Doble clic en **`install.bat`**: crea el entorno, instala dependencias, descarga `cloudflared.exe` y crea `.env`.
4. Abrí `.env` con el Bloc de notas y completá los datos (ver `.env.example` y `docs/MANUAL_CLIENTE.md`).
5. Configurá en **todos los emuladores** la tecla de moneda/coin igual a `CREDIT_KEY` (por defecto `5`, que en MAME ya es la moneda del jugador 1).
6. Doble clic en **`start.bat`**. En la ventana vas a ver `Túnel activo: https://...` y `Página del QR actualizada`.
7. Probá la tecla: `venv\Scripts\python tools\probar_tecla.py` con un emulador abierto.
8. El QR ya está generado en `docs/qr/` (ver abajo). Si cambiás `QR_URL`, regeneralo con `venv\Scripts\python tools\generar_qr.py`.
9. Arranque automático: clic derecho en **`instalar_inicio_automatico.bat` → Ejecutar como administrador** (crea la tarea "ArcadeQR" al iniciar sesión). Alternativa: poné un acceso directo a `start.bat` en `Win+R → shell:startup`.

> Configurá Windows para iniciar sesión automáticamente (`netplwiz`) y la PC con IP fija en el router (ej. `192.168.1.50`) para la app Android.

## Cloudflare Tunnel

**Temporal (gratis, lo que usa por defecto):** el servidor ejecuta solo
`cloudflared tunnel --no-autoupdate --url http://localhost:8000`. Para probarlo a mano: `cloudflared.exe tunnel --url http://localhost:8000`.

**Con nombre (URL fija, opcional, requiere dominio en Cloudflare):**
```
cloudflared tunnel login
cloudflared tunnel create arcade
cloudflared tunnel route dns arcade arcade.tudominio.com
cloudflared tunnel run --url http://localhost:8000 arcade
cloudflared service install   (para que arranque como servicio)
```
Después poné `PUBLIC_URL=https://arcade.tudominio.com` en `.env`: el servidor no lanza el túnel temporal y no hace falta GitHub Pages (el QR puede apuntar directo al dominio).

## Mercado Pago

Solo hacen falta dos datos en `.env`: **Access Token de producción** (`MP_ACCESS_TOKEN`) y **Clave secreta** de webhooks (`MP_WEBHOOK_SECRET`). En *Tus integraciones → Webhooks* se carga como URL `https://<url-del-túnel>/api/mercadopago/webhook` y el evento **Pagos**; esto es solo para obtener la clave secreta, porque cada pago ya informa su propia `notification_url`.

Estados: `approved` → se carga el crédito; `pending`/`in_process` → se registra y se espera el próximo aviso; `rejected`/`cancelled` → se registra, no se carga nada.

## Que no se caiga (vigilante del túnel)

- **Watchdog** (`app/tunnel.py`): lanza `cloudflared tunnel --no-autoupdate --protocol http2 --url http://localhost:PORT`; cada `TUNNEL_CHECK_INTERVAL` (30 s) verifica proceso vivo + `GET http://127.0.0.1:PORT/health` + `GET <url-túnel>/health`. Con `TUNNEL_MAX_FAILS` (3) fallas seguidas o si cloudflared muere, lo mata y relanza con backoff exponencial (5 s → 5 min), lee la nueva URL `trycloudflare.com` y actualiza `index.html` de GitHub Pages con reintentos (y reintenta en cada chequeo si quedó desactualizada). `TUNNEL_PROTOCOL=quic|auto` si `http2` anduviera mal.
- Estado en `GET /api/admin/status`: `tunnel_url`, `tunnel_alive`, `tunnel_restarts`, `tunnel_restarts_total`, `tunnel_last_restart`, `tunnel_last_restart_reason`, `tunnel_last_ok`, `backend_local_ok`.
- Alertas en SQLite (`alertas`) y `GET /api/admin/alertas` (ver `docs/API_APP_ANDROID.md`).
- **`start.bat`** relanza `run.py` si termina (log en `logs/supervisor.log`).
- **`instalar_inicio_automatico.bat`** (admin) importa `windows/ArcadeQR_tarea.xml`: al iniciar sesión, reintento cada 1 min, sin límite de tiempo, sin cortar por batería.
- **`configurar_windows.bat`** (admin): plan alto rendimiento, sin suspensión/hibernación, sin suspensión selectiva USB/PCIe/WiFi, sin ahorro de energía en placas de red, `NoAutoRebootWithLoggedOnUsers` de Windows Update. Activá en BIOS "Restore on AC Power Loss".
- Prueba en Linux: `python3 tests/test_tunel_watchdog.py 5` (cloudflared simulado) o `CLOUDFLARED_REAL=/ruta/cloudflared python3 tests/test_tunel_watchdog.py 5`.

## Logs y datos

- `logs/arcade.log` (rotativo, 5 × 2 MB): cada preferencia, aviso, estado y crédito cargado.
- `data/arcade.db`: SQLite con tablas `payments`, `preferences`, `settings`, `alertas`. Se puede abrir con *DB Browser for SQLite*.

## Pruebas

```
venv\Scripts\pip install pytest httpx
venv\Scripts\python -m pytest tests
```
Fuera de Windows el presionador de teclas es simulado.

## Seguridad

- `.env`, la base y los logs están en `.gitignore`: nunca subas tus claves.
- La API de administración exige `X-Admin-Key`, IP privada y rechaza cualquier pedido que venga por Cloudflare.
- El token de GitHub debe ser *fine-grained* y con acceso **solo** al repo de la página.
