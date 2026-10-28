# API para la app Android

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

## Ejemplo (curl)
```
curl -H "X-Admin-Key: miclave" http://192.168.1.50:8000/api/admin/stats
curl -X PUT -H "X-Admin-Key: miclave" -H "Content-Type: application/json" -d "{\"price\":2500}" http://192.168.1.50:8000/api/admin/price
```
Sugerencia: refrescar `stats` y `status` cada 10–30 s. Firewall de Windows: permitir Python en redes **privadas** (puerto 8000).
