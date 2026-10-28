# API para la app Android

> App Android: ver [android-app/README.md](android-app/README.md).

- Base: `http://<IP-de-la-PC>:8000` (ej. `http://192.168.1.50:8000`). **Solo WiFi local**, HTTP plano (en Android habilitá `usesCleartextTraffic` o un `network_security_config` para esa IP).
- Header obligatorio: `X-Admin-Key: <ADMIN_KEY>`.
- Respuestas JSON. Errores: `401` clave incorrecta, `403` fuera de la red local o vía túnel, `422` datos inválidos.

## GET /api/admin/stats
```json
{"currency":"ARS","price":2000.0,
 "today":{"income":6000.0,"credits":3,"payments":3},
 "week":{"income":14000.0,"credits":7,"payments":7},
 "total":{"income":50000.0,"credits":25,"payments":25},
 "credits_used":25,"credits_pending":0}
```
Semana = desde el lunes 00:00 (hora de la PC). Solo cuenta pagos `approved`.

## GET /api/admin/payments?limit=50&offset=0
```json
{"items":[{"payment_id":"123456789","external_ref":"a1b2...","status":"approved",
 "status_detail":"accredited","amount":2000.0,"credits":1,"credited":1,
 "created_at":"2026-10-28T20:15:03","updated_at":"2026-10-28T20:15:05"}]}
```
`credited`: 0 = no corresponde/aún no, 2 = en cola, 1 = cargado en el juego. Orden: más nuevo primero. `limit` máx. 500.

## GET /api/admin/status
```json
{"ok":true,"uptime_s":3600,"tunnel_url":"https://xxxx.trycloudflare.com",
 "tunnel_started":"2026-10-28T19:00:10","github_page_updated":"2026-10-28T19:00:12",
 "last_webhook":"2026-10-28T20:15:04","credit_key":"5","mp_configured":true}
```
Si `tunnel_url` es `null`, el arcade no puede cobrar (sin internet o túnel caído).

## PUT /api/admin/price
Body: `{"price": 2500}` → `{"price":2500.0}`. Se aplica al instante en la página de pago.

## GET /api/admin/qr.png
Devuelve el PNG del QR fijo del gabinete (apunta a `QR_URL`). Mismas protecciones que el resto: header `X-Admin-Key` y solo WiFi local.

## GET /admin/qr/imprimir?key=<ADMIN_KEY>
Página HTML lista para imprimir (QR grande + leyenda, tamaño A6) que abre sola el diálogo de impresión y tiene un botón **Imprimir QR**.
Como un navegador no puede mandar headers, **solo en esta página** la clave va en `?key=`. Sigue siendo solo WiFi local (403 si llega por el túnel o desde una IP pública).

## Botón Imprimir QR
En la app, agregá un botón **Imprimir QR** con una de estas dos opciones:

1. **Recomendada (más simple):** abrir en el navegador
   `http://192.168.1.50:8000/admin/qr/imprimir?key=<ADMIN_KEY>`
   ```kotlin
   startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("$baseUrl/admin/qr/imprimir?key=$adminKey")))
   ```
   Chrome abre el diálogo de impresión de Android (impresora WiFi o *Guardar como PDF*). Alternativa sin salir de la app: cargar la URL en un `WebView` y llamar a `PrintManager.print("QR Arcade", webView.createPrintDocumentAdapter("qr"), null)`.
2. **Descargar el PNG:** `GET /api/admin/qr.png` con `X-Admin-Key`, y imprimirlo con AndroidX:
   ```kotlin
   PrintHelper(context).apply { scaleMode = PrintHelper.SCALE_MODE_FIT }.printBitmap("QR Arcade", bitmap)
   ```

Nota: la clave en la URL puede quedar en el historial del navegador del celular; está bien porque solo sirve dentro del WiFi del local.

## Ejemplo (curl)
```
curl -H "X-Admin-Key: miclave" http://192.168.1.50:8000/api/admin/stats
curl -X PUT -H "X-Admin-Key: miclave" -H "Content-Type: application/json" -d "{\"price\":2500}" http://192.168.1.50:8000/api/admin/price
```
Sugerencia: refrescar `stats` y `status` cada 10–30 s. Firewall de Windows: permitir Python en redes **privadas** (puerto 8000).

## Alertas del vigilante

Eventos guardados en SQLite (tabla `alertas`). Igual que el resto: solo desde el WiFi del local y con header `X-Admin-Key`. Si llegan por el túnel → `403`.

Tipos (`tipo`): `backend_reiniciado` (info), `tunel_activo` (info), `tunel_sin_respuesta` (warning), `tunel_caido` (error), `tunel_reiniciado` (warning), `backend_sin_respuesta` (error), `github_pages_fallo` (error), `webhook_firma_invalida` (warning), `pago_error_consulta` (warning), `credito_no_aplicado` (error), `excepcion` (error). Niveles (`nivel`): `info`, `warning`, `error`.

### GET /api/admin/alertas?desde_id=0&limite=100&solo_no_leidas=false

Devuelve las alertas con `id > desde_id`, **las más nuevas primero** (máx. `limite`, 1–500). Para polling: guardá `ultimo_id` y la próxima vez pedí `?desde_id=<ultimo_id>`.

```json
{
  "alertas": [
    {"id": 42, "fecha": "2026-10-28T14:44:20", "nivel": "error", "tipo": "tunel_caido",
     "mensaje": "3 chequeos públicos fallidos", "leida": false}
  ],
  "no_leidas": 5,
  "ultimo_id": 42
}
```
`fecha` es hora local de la PC (sin zona), formato ISO.

### POST /api/admin/alertas/marcar_leidas

Body (todos opcionales; si no mandás nada o `{}` marca todas):
```json
{"ids": [40, 41, 42]}
```
o
```json
{"hasta_id": 42}
```
Respuesta:
```json
{"marcadas": 3}
```

### Campos del vigilante en GET /api/admin/status
```json
{"tunnel_url": "https://xxx.trycloudflare.com", "tunnel_alive": true, "tunnel_protocol": "http2",
 "tunnel_restarts": 2, "tunnel_restarts_total": 17, "tunnel_last_restart": "2026-10-28T14:44:20",
 "tunnel_last_restart_reason": "cloudflared terminó (código 1)", "tunnel_consecutive_fails": 0,
 "tunnel_last_check": "2026-10-28T15:00:00", "tunnel_last_ok": "2026-10-28T15:00:00",
 "backend_local_ok": true}
```
`tunnel_restarts` = desde que arrancó el programa; `tunnel_restarts_total` = histórico.
