# Arcade Admin (app Android)

App para el dueño del arcade: ingresos, créditos usados, estado del equipo, historial de pagos,
cambio de precio, alertas e impresión del QR. Diseño gamer moderno (dashboard tipo esports) en azul/naranja.
Funciona **solo dentro del WiFi del local** (habla directo con la PC del arcade por `http://IP:8000`).

## Instalar
1. Descargá `arcade-admin-debug.apk` desde la sección **Releases** del repo (o desde Actions → último build → Artifacts).
2. Abrilo en el celular. Si Android lo bloquea: **Ajustes → Seguridad → Instalar apps desconocidas** y permití al navegador / Archivos.
3. Instalá y abrí **Arcade Admin**. Aceptá el permiso de **notificaciones** (para las alertas del Vigilante).

## Primera configuración
1. Conectá el celular al **mismo WiFi** que el arcade.
2. En **CONFIG** escribí la IP y puerto de la PC, ej. `192.168.1.50:8000` (la IP fija que se configuró en el router).
3. Escribí la **clave de administrador** (`ADMIN_KEY` del archivo `.env` de la PC).
4. Tocá **PROBAR CONEXIÓN** → debe decir "¡Conectado!". Después **GUARDAR**.

Si falla: revisá que la PC esté prendida, que el programa esté corriendo y que el Firewall de Windows permita Python en redes privadas.

## Pantallas
- **INICIO**: gráfico de ingresos de los últimos 7 días, contadores animados, ingresos hoy/semana/total, créditos usados, estado de la PC y del túnel, último pago (se refresca solo cada 15 s), aviso de alertas sin leer, botones **IMPRIMIR QR** (usa la impresión de Android) y **ABRIR PÁGINA IMPRIMIBLE**.
- **PAGOS**: historial con estado (aprobado / pendiente / rechazado) y si el crédito se cargó.
- **PRECIO**: ver y cambiar el precio del crédito (pide confirmación, se aplica al instante).
- **ALERTAS**: lista coloreada por nivel (info celeste, warning naranja, error rojo) y "marcar todas leídas".
- **CONFIG**: IP:puerto y clave (guardadas cifradas en el teléfono).

## Vigilante (notificaciones)
Cada 15 minutos (y cada minuto con la app abierta) revisa alertas nuevas de nivel warning/error y avisa
con una notificación. Si la PC no responde 2 veces seguidas, avisa "PC del arcade sin respuesta".
Si el servidor todavía no tiene `/api/admin/alertas`, la app lo ignora sin romperse.

## Compilar (desarrolladores)
JDK 17 + Android SDK 34: `cd android-app && ./gradlew assembleDebug`. También lo compila GitHub Actions en cada push.
Fuentes: Rajdhani (títulos) e Inter (texto), SIL OFL 1.1 — ver `licenses/`. Íconos: Material Icons (Apache 2.0).
