@echo off
:: ============================================================
:: Project Tracking Backend — NSSM Windows Service Installer
:: Run this script once as Administrator to install the service.
:: ============================================================

set SERVICE=ProjTracking

:: Derive the backend dir from this script's own location (portable across devices).
:: %~dp0 ends with a backslash — strip it so quoted paths don't escape the quote.
set BASE=%~dp0
if "%BASE:~-1%"=="\" set BASE=%BASE:~0,-1%

set PYTHON=%BASE%\.venv\Scripts\waitress-serve.exe
set LOGDIR=%BASE%\logs

:: Pre-flight: the virtualenv must exist (run setup first — see README).
if not exist "%PYTHON%" (
    echo ERROR: %PYTHON% not found.
    echo Create the venv and install deps first:
    echo     py -3.11 -m venv "%BASE%\.venv"
    echo     "%BASE%\.venv\Scripts\pip" install -r "%BASE%\requirements.txt"
    goto :eof
)

:: Create log directory
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

echo Installing service: %SERVICE% ...

nssm install %SERVICE% "%PYTHON%" --host=0.0.0.0 --port=5000 --threads=4 wsgi:app
nssm set %SERVICE% AppDirectory "%BASE%"
nssm set %SERVICE% DisplayName "Project Tracking Backend"
nssm set %SERVICE% Description "Flask/Waitress REST API for Project Tracking"
nssm set %SERVICE% Start SERVICE_AUTO_START

:: Redirect stdout/stderr to log files
nssm set %SERVICE% AppStdout "%LOGDIR%\service.log"
nssm set %SERVICE% AppStderr "%LOGDIR%\service_error.log"
nssm set %SERVICE% AppRotateFiles 1
nssm set %SERVICE% AppRotateSeconds 86400
nssm set %SERVICE% AppRotateBytes 10485760

:: Restart on failure
nssm set %SERVICE% AppExit Default Restart
nssm set %SERVICE% AppRestartDelay 3000

echo.
echo Starting service ...
nssm start %SERVICE%

echo.
echo Done (backend). Use these commands to manage:
echo   nssm status %SERVICE%
echo   nssm restart %SERVICE%
echo   nssm stop %SERVICE%
echo   nssm remove %SERVICE% confirm

:: ============================================================
:: Frontend static server — TailScale deployment
:: Serves the built Vue SPA via 'serve' (npm) on port %FRONTEND_PORT%.
:: The SPA is built with a RELATIVE API base ("/api") so it works
:: behind the single-origin Tailscale Serve proxy (see bottom).
:: ============================================================

set FRONTEND_SVC=ProjTrackingFrontend

:: Frontend lives next to backend: ...\Project-Tracking\frontend
for %%I in ("%BASE%\..\frontend") do set FRONTEND_BASE=%%~fI
set FRONTEND_PORT=9000

:: Auto-detect this device's TailScale IPv4 (no hardcoded address).
set TAILSCALE_IP=
for /f "delims=" %%i in ('tailscale ip -4 2^>nul') do if not defined TAILSCALE_IP set TAILSCALE_IP=%%i
if not defined TAILSCALE_IP set TAILSCALE_IP=localhost

:: 1. Build the frontend with a relative API base (single-origin deployment).
echo.
echo Building frontend (relative /api — single origin) ...
pushd "%FRONTEND_BASE%"
set VITE_API_BASE=
call npm run build
if errorlevel 1 (
    echo ERROR: Frontend build failed. Aborting frontend service install.
    popd
    goto :eof
)
popd

:: 2. Ensure the 'serve' package is installed globally
where serve.cmd >nul 2>&1
if errorlevel 1 (
    echo Installing 'serve' globally ...
    npm install -g serve
)

:: 3. Locate node.exe and the global serve entry-point
for /f "delims=" %%i in ('where node.exe') do set NODE_EXE=%%i
for /f "delims=" %%i in ('npm root -g') do set NPM_GLOBAL=%%i

echo.
echo Installing service: %FRONTEND_SVC% ...

nssm install %FRONTEND_SVC% "%NODE_EXE%" "%NPM_GLOBAL%\serve\build\main.js" -s "%FRONTEND_BASE%\dist" -l tcp:0.0.0.0:%FRONTEND_PORT% --no-clipboard
nssm set %FRONTEND_SVC% AppDirectory "%FRONTEND_BASE%"
nssm set %FRONTEND_SVC% DisplayName "Project Tracking Frontend"
nssm set %FRONTEND_SVC% Description "Serves the built Vue SPA on port %FRONTEND_PORT% for TailScale access"
nssm set %FRONTEND_SVC% Start SERVICE_AUTO_START

nssm set %FRONTEND_SVC% AppStdout "%LOGDIR%\frontend.log"
nssm set %FRONTEND_SVC% AppStderr "%LOGDIR%\frontend_error.log"
nssm set %FRONTEND_SVC% AppRotateFiles 1
nssm set %FRONTEND_SVC% AppRotateSeconds 86400

nssm set %FRONTEND_SVC% AppExit Default Restart
nssm set %FRONTEND_SVC% AppRestartDelay 3000

echo.
echo Starting frontend service ...
nssm start %FRONTEND_SVC%

:: ============================================================
:: Tailscale Serve — single-origin HTTPS (portless access)
:: Reverse-proxies one HTTPS origin to the two local services:
::   /     -> frontend (serve)  on port %FRONTEND_PORT%
::   /api  -> backend  (Flask)  on port 5000  (re-prefixed)
:: Result: https://<device>.<tailnet>.ts.net  (no port, auto TLS)
:: ============================================================
echo.
echo Configuring Tailscale Serve (single-origin HTTPS) ...
tailscale serve --bg --https=443 --set-path=/ http://127.0.0.1:%FRONTEND_PORT% >nul 2>&1
tailscale serve --bg --https=443 --set-path=/api http://127.0.0.1:5000/api >nul 2>&1

:: Resolve this device's MagicDNS name for the banner (best-effort).
set TS_DNS=
for /f "tokens=2" %%i in ('tailscale status --self --json 2^>nul ^| findstr /i "DNSName"') do if not defined TS_DNS set TS_DNS=%%~i
if not defined TS_DNS set TS_DNS=%TAILSCALE_IP%

echo.
echo ============================================================
echo  Access URLs
echo    Single origin (recommended) : https://%TS_DNS%
echo    Direct frontend             : http://%TAILSCALE_IP%:%FRONTEND_PORT%
echo    Direct backend              : http://%TAILSCALE_IP%:5000
echo ============================================================
echo.
echo Frontend service commands:
echo   nssm status  %FRONTEND_SVC%
echo   nssm restart %FRONTEND_SVC%
echo   nssm stop    %FRONTEND_SVC%
echo   nssm remove  %FRONTEND_SVC% confirm
echo.
echo Tailscale Serve:
echo   tailscale serve status
echo   tailscale serve --https=443 off   ^(to disable^)
