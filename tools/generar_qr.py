"""Genera el QR fijo del gabinete en docs/qr/ (PNG grande, SVG y página para imprimir).
Uso: python tools/generar_qr.py            -> usa QR_URL del .env (por defecto https://frarcade-26.github.io/)
     python tools/generar_qr.py https://otra.url/
Imprimilo de al menos 6x6 cm.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config, qr  # noqa: E402

url = sys.argv[1] if len(sys.argv) > 1 else config.QR_URL
out = config.BASE_DIR / "docs" / "qr"
out.mkdir(parents=True, exist_ok=True)
(out / "qr_arcade.png").write_bytes(qr.make_png(url))
(out / "qr_arcade.svg").write_text(qr.make_svg(url), encoding="utf-8")
(out / "sticker_imprimir.html").write_text(qr.print_html("qr_arcade.png", url), encoding="utf-8")
print(f"Listo: {out}/qr_arcade.png / .svg / sticker_imprimir.html -> {url}")
