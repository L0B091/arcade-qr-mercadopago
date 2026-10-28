@echo off
REM Arranca el servidor del arcade + el tunel de Cloudflare. Si se cae, lo reinicia.
cd /d "%~dp0"
:loop
call venv\Scripts\activate.bat
python run.py
echo El servidor se detuvo. Reiniciando en 5 segundos...
timeout /t 5 /nobreak >nul
goto loop
