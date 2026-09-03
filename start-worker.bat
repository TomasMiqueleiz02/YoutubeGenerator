@echo off
REM ============================================================
REM  YouTube Clip Generator - local worker
REM
REM  Runs the processing worker on this PC instead of in the
REM  cloud. YouTube blocks datacenter IPs, but not home
REM  connections, so downloads work from here.
REM
REM  Leave this window open while videos are processing.
REM  Closing it just stops processing - nothing is lost, queued
REM  videos resume next time you start it.
REM ============================================================

cd /d "%~dp0backend"

if not exist ".env.local" (
    echo.
    echo   ERROR: backend\.env.local not found.
    echo   That file holds the database credentials.
    echo.
    pause
    exit /b 1
)

echo.
echo   Starting worker. Leave this window open.
echo   Press Ctrl+C to stop.
echo.

REM Load .env.local into the environment
for /f "usebackq tokens=1,* delims==" %%a in ("%~dp0backend\.env.local") do (
    echo %%a| findstr /b "#" >nul || if not "%%a"=="" set "%%a=%%b"
)

REM --pool=solo: Windows has no fork(), and the default prefork pool
REM misbehaves there. Solo runs one task at a time in-process.
python -m celery -A app.tasks.celery_app worker --loglevel=info --pool=solo

echo.
echo   Worker stopped.
pause
