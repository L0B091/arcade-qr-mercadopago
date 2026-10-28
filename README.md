# Arcade QR + Mercado Pago

Sistema de cobro por QR para **un gabinete arcade** con PC Windows. El jugador escanea el QR, paga **1 crédito** con Mercado Pago y el crédito se carga solo en el emulador abierto (MAME, SNES9x, FCEUX, VisualBoyAdvance, Project64, ePSXe, PCSX2, Kega Fusion o juegos de PC).

## Cómo funciona

```
QR fijo ─► usuario.github.io (redirige) ─► https://xxxx.trycloudflare.com ─► PC del arcade :8000
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
tools/generar_qr.py   genera el PNG del QR
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
8. Generá el QR: `venv\Scripts\python tools\generar_qr.py` → imprimí `qr_arcade.png`.
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

## Logs y datos

- `logs/arcade.log` (rotativo, 5 × 2 MB): cada preferencia, aviso, estado y crédito cargado.
- `data/arcade.db`: SQLite con tablas `payments`, `preferences`, `settings`. Se puede abrir con *DB Browser for SQLite*.

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
