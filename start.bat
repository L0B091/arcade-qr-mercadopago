@echo off
REM Arranca el servidor del arcade (que a su vez lanza y vigila el tunel de Cloudflare).
REM Si el servidor se cierra por cualquier motivo, lo vuelve a arrancar solo.
cd /d "%~dp0"
title Arcade QR - NO CERRAR
if not exist logs mkdir logs
:loop
call venv\Scripts\activate.bat
echo [%date% %time%] Arrancando servidor >> logs\supervisor.log
python run.py
echo [%date% %time%] El servidor se detuvo (codigo %errorlevel%). Reinicio en 5 s >> logs\supervisor.log
echo El servidor se detuvo. Reiniciando en 5 segundos...
REM Por si quedo un cloudflared huerfano
taskkill /im cloudflared.exe /f >nul 2>&1
timeout /t 5 /nobreak >nul
goto loop
