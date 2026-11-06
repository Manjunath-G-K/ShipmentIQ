@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
set "RUNTIME=%ROOT%.shipmentiq-runtime"

where docker >nul 2>&1
if errorlevel 1 (
  echo ERROR: Docker Desktop/Docker CLI was not found on PATH.
  exit /b 1
)
docker compose version >nul 2>&1
if errorlevel 1 (
  echo ERROR: Docker Compose is unavailable. Start Docker Desktop and verify Docker Compose v2.
  exit /b 1
)

echo Starting only the ShipmentIQ PostgreSQL service...
docker compose up -d postgres
if errorlevel 1 (
  echo ERROR: PostgreSQL could not be started. Existing data and volumes were not removed.
  exit /b 1
)

if not exist "%ROOT%backend\.venv\Scripts\python.exe" (
  echo ERROR: Backend virtual environment not found at backend\.venv.
  echo Create it and install backend\requirements.txt before using this launcher.
  exit /b 1
)
where npm >nul 2>&1
if errorlevel 1 (
  echo ERROR: npm was not found on PATH.
  exit /b 1
)
if not exist "%ROOT%frontend\node_modules" (
  echo ERROR: frontend\node_modules was not found.
  echo Run npm install from the frontend directory before using this launcher.
  exit /b 1
)

if not exist "%RUNTIME%" mkdir "%RUNTIME%"

echo Starting the backend in a separate terminal window...
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$p=Start-Process -FilePath 'cmd.exe' -ArgumentList '/k','title ShipmentIQ Backend ^& cd /d ""%ROOT%backend"" ^& ""%ROOT%backend\.venv\Scripts\python.exe"" -m uvicorn app.main:app --host 127.0.0.1 --port 8000' -WorkingDirectory '%ROOT%backend' -PassThru; $p.Id"`) do set "BACKEND_PID=%%I"
>"%RUNTIME%\backend.pid" echo %BACKEND_PID%

echo Starting the frontend in a separate terminal window...
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$p=Start-Process -FilePath 'cmd.exe' -ArgumentList '/k','title ShipmentIQ Frontend ^& cd /d ""%ROOT%frontend"" ^& npm run dev -- --host 127.0.0.1' -WorkingDirectory '%ROOT%frontend' -PassThru; $p.Id"`) do set "FRONTEND_PID=%%I"
>"%RUNTIME%\frontend.pid" echo %FRONTEND_PID%

echo.
echo ShipmentIQ launcher started.
echo Frontend:      http://127.0.0.1:5173
echo Backend health: http://127.0.0.1:8000/api/v1/health
echo Swagger:       http://127.0.0.1:8000/docs
echo Use stop-shipmentiq.bat to stop only these launcher windows and PostgreSQL.
exit /b 0
