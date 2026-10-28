@echo off
REM Instalación (una sola vez). Requiere Python 3.10+ instalado con "Add to PATH".
cd /d "%~dp0"
python -m venv venv || (echo No se encontro Python. Instalalo desde python.org & pause & exit /b 1)
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist .env copy .env.example .env
if not exist cloudflared.exe (
  echo Descargando cloudflared...
  powershell -Command "Invoke-WebRequest https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe -OutFile cloudflared.exe"
)
echo.
echo Listo. Ahora edita el archivo .env con tus datos y ejecuta start.bat
pause
