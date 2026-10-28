@echo off
REM Ejecutar como ADMINISTRADOR (clic derecho -> Ejecutar como administrador).
REM Crea la tarea "ArcadeQR": arranca el arcade al iniciar sesion y lo reinicia si falla.
cd /d "%~dp0"
set "RUTA=%~dp0"
set "RUTA=%RUTA:~0,-1%"
powershell -NoProfile -Command "(Get-Content -Raw 'windows\ArcadeQR_tarea.xml') -replace 'RUTA_ARCADE', $env:RUTA | Set-Content -Encoding Unicode \"$env:TEMP\ArcadeQR_tarea.xml\""
schtasks /create /tn "ArcadeQR" /xml "%TEMP%\ArcadeQR_tarea.xml" /f
if errorlevel 1 (
  echo No se pudo crear con XML. Uso el metodo simple.
  schtasks /create /tn "ArcadeQR" /tr "\"%~dp0start.bat\"" /sc onlogon /rl highest /f
)
echo.
echo Tarea "ArcadeQR" lista. El arcade va a arrancar solo al prender la PC.
pause
