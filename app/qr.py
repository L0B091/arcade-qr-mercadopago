"""Generación del QR fijo del gabinete (PNG con leyenda, SVG y página imprimible).

El QR apunta a QR_URL (la página fija de GitHub Pages del cliente), NO a la URL
del túnel: así nunca hay que reimprimirlo.
Si la librería `qrcode` no está instalada, se sirve el PNG pregenerado de docs/qr/.
"""
import io
from pathlib import Path
from . import config

CAPTION = "Escaneá para jugar — 1 crédito"
PREGEN_PNG = config.BASE_DIR / "docs" / "qr" / "qr_arcade.png"


def _font(size):
    from PIL import ImageFont
    # Probamos fuentes comunes de Windows y Linux; si no hay, la de Pillow.
    for f in ("arialbd.ttf", "C:/Windows/Fonts/arialbd.ttf", "DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def make_png(url=None, caption=CAPTION, box_size=30):
    """Devuelve los bytes de un PNG grande: QR (corrección H) + leyenda abajo."""
    try:
        import qrcode
        from PIL import Image, ImageDraw
    except ImportError:
        return PREGEN_PNG.read_bytes()  # respaldo: PNG ya generado
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H,
                       box_size=box_size, border=4)
    qr.add_data(url or config.QR_URL)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    w, h = img.size
    draw = ImageDraw.Draw(img)
    size = max(24, w // 14)
    font = _font(size)
    # Achicamos la letra hasta que la leyenda entre con margen
    while draw.textlength(caption, font=font) > w * 0.9 and size > 12:
        size -= 2
        font = _font(size)
    tw = draw.textlength(caption, font=font)
    pad = int(font.size * 1.8)
    out = Image.new("RGB", (w, h + pad), "white")
    out.paste(img, (0, 0))
    ImageDraw.Draw(out).text(((w - tw) / 2, h - font.size * 0.4), caption, fill="black", font=font)
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


def make_svg(url=None, caption=CAPTION):
    """SVG vectorial (ideal para imprenta), con la leyenda como texto."""
    import qrcode
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, border=4)
    qr.add_data(url or config.QR_URL)
    qr.make(fit=True)
    m = qr.get_matrix()  # incluye el borde
    n = len(m)
    rects = "".join(f'<rect x="{x}" y="{y}" width="1" height="1"/>'
                    for y, row in enumerate(m) for x, v in enumerate(row) if v)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n} {n + 5}" '
            f'width="{n * 20}" height="{(n + 5) * 20}" shape-rendering="crispEdges">'
            f'<rect width="100%" height="100%" fill="#fff"/><g fill="#000">{rects}</g>'
            f'<text x="{n / 2}" y="{n + 2}" font-family="Arial,Helvetica,sans-serif" '
            f'font-weight="bold" font-size="2.4" text-anchor="middle">{caption}</text></svg>')


def print_html(img_src, url=None, caption=CAPTION):
    """Página lista para imprimir (tamaño A6, también sirve en A5/A4)."""
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Imprimir QR del arcade</title>
<style>
 @page {{ size: A6; margin: 8mm; }}
 body {{ font-family: Arial, sans-serif; text-align: center; margin: 0; }}
 .sticker {{ padding: 6mm; }}
 h1 {{ font-size: 20pt; margin: 2mm 0; }}
 img {{ width: 90mm; max-width: 95vw; height: auto; }}
 p {{ font-size: 10pt; color: #444; word-break: break-all; }}
 button {{ font-size: 18pt; padding: 10px 28px; margin: 14px; }}
 @media print {{ .no-print {{ display: none; }} }}
</style></head><body>
<div class="no-print"><button onclick="window.print()">🖨️ Imprimir QR</button></div>
<div class="sticker">
 <h1>🕹️ ARCADE</h1>
 <img src="{img_src}" alt="QR para pagar">
 <p>{url or config.QR_URL}</p>
</div>
<script>window.addEventListener('load', () => setTimeout(() => window.print(), 600));</script>
</body></html>"""
