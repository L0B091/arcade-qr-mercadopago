@echo off
REM Crea una tarea programada que arranca el arcade al iniciar sesion en Windows.
cd /d "%~dp0"
schtasks /create /tn "ArcadeQR" /tr "\"%~dp0start.bat\"" /sc onlogon /rl highest /f
echo Tarea "ArcadeQR" creada. El arcade va a arrancar solo al prender la PC.
pause
