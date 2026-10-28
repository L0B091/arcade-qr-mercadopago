"""Prueba la tecla de crédito: python tools/probar_tecla.py
Tenés 5 segundos para abrir el emulador; después aprieta la tecla de moneda 1 vez."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config
from app.credits import CreditWorker

print(f"Apretando la tecla '{config.CREDIT_KEY}' en 5 segundos…")
time.sleep(5)
CreditWorker().presser.press(config.CREDIT_KEY)
print("Listo. ¿El juego sumó un crédito?")
