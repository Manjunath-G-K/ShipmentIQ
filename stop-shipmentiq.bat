@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
set "RUNTIME=%ROOT%.shipmentiq-runtime"

if exist "%RUNTIME%\backend.pid" call :stop_marked_process "%RUNTIME%\backend.pid" "ShipmentIQ Backend" "uvicorn"
if exist "%RUNTIME%\frontend.pid" call :stop_marked_process "%RUNTIME%\frontend.pid" "ShipmentIQ Frontend" "npm run dev"

if exist "%RUNTIME%\backend.pid" del /q "%RUNTIME%\backend.pid" >nul 2>&1
if exist "%RUNTIME%\frontend.pid" del /q "%RUNTIME%\frontend.pid" >nul 2>&1
if exist "%RUNTIME%" rmdir "%RUNTIME%" >nul 2>&1

where docker >nul 2>&1
if errorlevel 1 (
  echo Docker CLI not found; no PostgreSQL stop command was issued.
  exit /b 1
)
docker compose version >nul 2>&1
if errorlevel 1 (
  echo Docker Compose is unavailable; no PostgreSQL stop command was issued.
  exit /b 1
)

echo Stopping only the ShipmentIQ PostgreSQL service; the named volume is preserved.
docker compose stop postgres
if errorlevel 1 (
  echo WARNING: PostgreSQL could not be stopped. No volume deletion was attempted.
  exit /b 1
)
echo ShipmentIQ backend, frontend launcher windows, and PostgreSQL service were stopped when present.
exit /b 0

:stop_marked_process
set "PID_FILE=%~1"
set "EXPECTED_TITLE=%~2"
set "EXPECTED_COMMAND=%~3"
set "SHIPMENTIQ_PID="
set /p SHIPMENTIQ_PID=<"%PID_FILE%"
if not defined SHIPMENTIQ_PID exit /b 0
set "SHIPMENTIQ_PID=%SHIPMENTIQ_PID: =%"
set "SHIPMENTIQ_ROOT=%ROOT%"
set "SHIPMENTIQ_EXPECTED_TITLE=%EXPECTED_TITLE%"
set "SHIPMENTIQ_EXPECTED_COMMAND=%EXPECTED_COMMAND%"
powershell -NoProfile -Command "$id=[int]$env:SHIPMENTIQ_PID; $p=Get-CimInstance Win32_Process -Filter ('ProcessId = ' + $id); if (-not $p) { Write-Output ('No process with recorded PID ' + $id + ' was found.'); exit 0 }; $cmd=[string]$p.CommandLine; if (($cmd -like ('*' + $env:SHIPMENTIQ_ROOT + '*')) -and ($cmd -like ('*' + $env:SHIPMENTIQ_EXPECTED_COMMAND + '*'))) { taskkill /PID $id /T /F | Out-Null; Write-Output ('Stopped ' + $env:SHIPMENTIQ_EXPECTED_TITLE + ' process tree.'); exit 0 }; Write-Output ('Recorded PID ' + $id + ' did not match the ShipmentIQ launcher signature; it was not terminated.'); exit 1"
exit /b %errorlevel%
