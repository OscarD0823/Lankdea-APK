@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0descargar-paquete.ps1"
if errorlevel 1 echo No se completo el paquete. Revisa el mensaje anterior.
pause
