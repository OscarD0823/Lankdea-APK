@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ejecutar-lankdea.ps1"
if errorlevel 1 echo No se pudo iniciar Lankdea. Revisa el mensaje anterior.
pause
