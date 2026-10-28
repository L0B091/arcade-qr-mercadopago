@echo off
REM ==========================================================================
REM  Configura Windows para que el arcade NUNCA se duerma ni corte la red.
REM  Ejecutar UNA vez como ADMINISTRADOR (clic derecho -> Ejecutar como administrador).
REM ==========================================================================
net session >nul 2>&1 || (echo Tenes que ejecutarlo como ADMINISTRADOR. & pause & exit /b 1)

echo == Plan de energia: Alto rendimiento ==
powercfg -setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c 2>nul || powercfg -setactive SCHEME_MIN

echo == Nunca suspender / hibernar / apagar disco ==
powercfg -change -standby-timeout-ac 0
powercfg -change -standby-timeout-dc 0
powercfg -change -hibernate-timeout-ac 0
powercfg -change -hibernate-timeout-dc 0
powercfg -change -disk-timeout-ac 0
powercfg -change -disk-timeout-dc 0
powercfg -hibernate off
REM La pantalla puede apagarse? No: en un arcade la dejamos siempre prendida
powercfg -change -monitor-timeout-ac 0

echo == USB: desactivar suspension selectiva ==
powercfg -setacvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0
echo == PCI Express: sin ahorro de energia del enlace ==
powercfg -setacvalueindex SCHEME_CURRENT 501a4d13-42af-4429-9fd1-a8218c268e20 ee12f906-d277-404b-b6da-e5fa1a576df5 0
echo == WiFi: maximo rendimiento ==
powercfg -setacvalueindex SCHEME_CURRENT 19cbb8fa-5279-450e-9fac-8a3d5fedd0c1 12bbebe6-58d6-4636-95bb-3217ef867c1a 0
powercfg -setactive SCHEME_CURRENT

echo == Placas de red: que Windows no las apague para ahorrar energia ==
powershell -NoProfile -Command "Get-NetAdapter -Physical | ForEach-Object { try { Disable-NetAdapterPowerManagement -Name $_.Name -ErrorAction Stop; Write-Host ('  OK ' + $_.Name) } catch { Write-Host ('  (no soportado) ' + $_.Name) } }"
powershell -NoProfile -Command "Get-CimInstance -Namespace root\wmi -ClassName MSPower_DeviceEnable -ErrorAction SilentlyContinue | Where-Object { $_.InstanceName -match 'USB|PCI\\VEN' } | ForEach-Object { $_.Enable = $false; Set-CimInstance -InputObject $_ -ErrorAction SilentlyContinue }"

echo == Windows Update: no reiniciar solo con la sesion iniciada ==
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" /v NoAutoRebootWithLoggedOnUsers /t REG_DWORD /d 1 /f
REM Horario activo 8 a 2 (no reinicia en ese rango)
reg add "HKLM\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings" /v ActiveHoursStart /t REG_DWORD /d 8 /f
reg add "HKLM\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings" /v ActiveHoursEnd /t REG_DWORD /d 2 /f

echo == Arrancar sola despues de un corte de luz ==
echo   Esto NO se puede hacer desde Windows: entra al BIOS y activa
echo   "Restore on AC Power Loss" / "AC Back" = "Power On".
echo.
echo Listo. Revisa el resultado con:  powercfg /a   y   powercfg /q
pause
