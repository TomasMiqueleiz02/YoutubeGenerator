@echo off
REM Doble click aca para que el worker arranque solo con Windows.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-autostart.ps1"
pause
