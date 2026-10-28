"""Genera qr_arcade.png con la URL de la página fija (GitHub Pages).
Uso: python tools/generar_qr.py https://usuario.github.io/
Si no pasás URL, la arma a partir de GITHUB_PAGES_REPO del .env.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import qrcode
from app import config

if len(sys.argv) > 1:
    url = sys.argv[1]
else:
    user, repo = config.GITHUB_PAGES_REPO.split("/")
    url = f"https://{user}.github.io/" + ("" if repo.lower() == f"{user.lower()}.github.io" else f"{repo}/")
img = qrcode.make(url, box_size=20, border=4)
img.save("qr_arcade.png")
print(f"Listo: qr_arcade.png -> {url}  (imprimilo de al menos 6x6 cm)")
