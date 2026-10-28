# Manual para el dueño del arcade

Son pasos que hacés **una sola vez**. Anotá cada dato que copies, porque después va en el archivo `.env`.

## 1. Cuenta de GitHub y página del QR

1. Entrá a <https://github.com/signup> y creá una cuenta gratis (ej. usuario `frarcade-26`).
2. Arriba a la derecha: **+ → New repository**.
   - Nombre: `frarcade-26.github.io` (tu usuario + `.github.io`).
   - Marcá **Public** y tildá **Add a README file**. Clic en **Create repository**.
3. En el repo: **Settings → Pages** → *Source*: **Deploy from a branch**, rama **main**, carpeta **/(root)** → **Save**.
4. Creá el token: tu foto → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**.
   - Nombre: `arcade`. Vencimiento: el más largo posible (anotá la fecha para renovarlo).
   - *Repository access*: **Only select repositories** → elegí `frarcade-26.github.io`.
   - *Permissions → Repository permissions → Contents*: **Read and write**.
   - **Generate token** y copiá el código `github_pat_...` (se muestra una sola vez).
5. En `.env`:
   ```
   GITHUB_TOKEN=github_pat_...
   GITHUB_PAGES_REPO=frarcade-26/frarcade-26.github.io
   ```
Tu QR va a apuntar a `https://frarcade-26.github.io/`.

### Tu QR (ya está listo)

![QR del arcade](qr/qr_arcade.png)

Este es **el QR definitivo** de tu arcade. Apunta a `https://frarcade-26.github.io/`, tu página fija de GitHub. Cada vez que el arcade arranca, el programa actualiza esa página para que mande al jugador a la dirección del momento, así que **no hace falta reimprimirlo nunca**.

- Para imprimir: usá [`qr/sticker_A6.pdf`](qr/sticker_A6.pdf) (tamaño A6, ideal para pegar) o [`qr/qr_arcade.png`](qr/qr_arcade.png). Para imprenta o vinilo: [`qr/qr_arcade.svg`](qr/qr_arcade.svg).
- Tamaño mínimo: **6 x 6 cm**. Pegalo a la altura de los ojos, donde no le dé el reflejo de luces.
- También lo podés imprimir desde la app del celular con el botón **Imprimir QR**.
- Si algún día cambiás de página, poné la nueva en `QR_URL` del `.env` y corré `venv\Scripts\python tools\generar_qr.py`.

## 2. Mercado Pago

1. Entrá a <https://www.mercadopago.com.ar/developers/panel/app> con tu cuenta de Mercado Pago.
2. **Crear aplicación** → nombre `Arcade` → tipo de pago **Pagos online** → producto **Checkout Pro** → crear.
3. En el menú de la aplicación: **Credenciales de producción** (si pide activarlas, completá los datos del negocio). Copiá el **Access Token** (`APP_USR-...`).
4. Menú **Webhooks → Configurar notificaciones**:
   - Modo productivo. URL: la que aparece en la ventana del arcade como `Túnel activo: https://....trycloudflare.com`, agregándole `/api/mercadopago/webhook`.
   - Evento: tildá solo **Pagos**. **Guardar**.
   - Copiá la **Clave secreta** que aparece ahí.
5. En `.env`:
   ```
   MP_ACCESS_TOKEN=APP_USR-...
   MP_WEBHOOK_SECRET=la_clave_secreta
   ```
> No hace falta volver a tocar esto aunque la URL del túnel cambie: el sistema le avisa a Mercado Pago la URL correcta en cada pago.

## 3. Tecla de moneda en los emuladores

Todos tienen que usar la **misma tecla** para "Insertar moneda/Coin" (por defecto `5`):

| Emulador | Dónde se configura |
|---|---|
| MAME | `Tab` → Input (general) → Player 1 → Coin 1 (ya es `5`) |
| SNES9x / FCEUX / VBA / Kega Fusion | Configurar controles → asignar `5` a **Select** (o la tecla de moneda del juego) |
| Project64 / ePSXe / PCSX2 | Configuración de controles/plugin de mando → asignar `5` a Select |
| Juegos de PC | En sus opciones de controles, asignar `5` a la acción de crédito/inicio |

Para probar: con un juego abierto ejecutá `tools\probar_tecla.py` y fijate que sume un crédito.

## 4. Clave de administrador

Inventá una clave larga en `ADMIN_KEY=` del `.env`. Es la que vas a escribir en la app de Android.

## 5. Uso diario

- Prendé el arcade: arranca todo solo.
- Si un jugador dice que pagó y no se cargó: mirá `logs\arcade.log` o el historial en la app.
- Si cambiás de router, revisá que la PC siga con la misma IP para la app.
