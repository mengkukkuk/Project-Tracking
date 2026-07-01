@echo off
:: ============================================================
:: Project Tracking Backend — NSSM Windows Service Installer
:: Single-origin deployment: Flask serves the built Vue SPA AND
:: the /api/* routes from one port (5000), and a public ngrok
:: domain tunnels straight to that port.
:: Run this script once as Administrator to install both services.
:: ============================================================

set SERVICE=ProjTracking
set NGROK_SVC=ProjTrackingNgrok

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

:: ============================================================
:: Load NGROK_AUTH_TOKEN / NGROK_DOMAIN from .env
:: ============================================================
if not exist "%BASE%\.env" (
    echo ERROR: "%BASE%\.env" not found.
    echo Copy .env.example to .env and set NGROK_AUTH_TOKEN / NGROK_DOMAIN first.
    goto :eof
)

for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%BASE%\.env") do (
    if not "%%A"=="" if not "%%B"=="" set "%%A=%%B"
)

if not defined NGROK_AUTH_TOKEN (
    echo ERROR: NGROK_AUTH_TOKEN is not set in "%BASE%\.env".
    goto :eof
)
if not defined NGROK_DOMAIN (
    echo ERROR: NGROK_DOMAIN is not set in "%BASE%\.env".
    goto :eof
)

:: ============================================================
:: Build the frontend — single-origin (relative /api base) so
:: Flask can serve it from the same port as the API.
:: ============================================================
for %%I in ("%BASE%\..\frontend") do set FRONTEND_BASE=%%~fI

echo.
echo Building frontend (relative /api - single origin) ...
pushd "%FRONTEND_BASE%"
set VITE_API_BASE=
call npm run build
if errorlevel 1 (
    echo ERROR: Frontend build failed. Aborting service install.
    popd
    goto :eof
)
popd

:: Create log directory
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

:: ============================================================
:: Backend service — Flask/Waitress (serves API + built SPA)
:: ============================================================
echo.
echo Installing service: %SERVICE% ...

nssm install %SERVICE% "%PYTHON%" --host=0.0.0.0 --port=5000 --threads=4 wsgi:app
nssm set %SERVICE% AppDirectory "%BASE%"
nssm set %SERVICE% DisplayName "Project Tracking Backend"
nssm set %SERVICE% Description "Flask/Waitress REST API + SPA for Project Tracking"
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

:: ============================================================
:: Ngrok tunnel — forwards https://%NGROK_DOMAIN% to port 5000
:: The authtoken is written to a repo-local config file (not the
:: interactive user's profile) because NSSM services run as
:: LocalSystem by default and would not see a per-user ngrok.yml.
:: ============================================================
set NGROK_CFG=%BASE%\ngrok.yml

echo.
echo Configuring ngrok authtoken ...
ngrok config add-authtoken %NGROK_AUTH_TOKEN% --config "%NGROK_CFG%"
if errorlevel 1 (
    echo ERROR: ngrok config add-authtoken failed. Is ngrok installed and on PATH?
    goto :eof
)

set NGROK_EXE=
for /f "delims=" %%i in ('where ngrok.exe 2^>nul') do if not defined NGROK_EXE set NGROK_EXE=%%i
if not defined NGROK_EXE (
    echo ERROR: ngrok.exe not found on PATH. Install ngrok first: https://ngrok.com/download
    goto :eof
)

echo.
echo Installing service: %NGROK_SVC% ...

nssm install %NGROK_SVC% "%NGROK_EXE%" http 5000 --url https://%NGROK_DOMAIN% --config "%NGROK_CFG%" --log stdout
nssm set %NGROK_SVC% AppDirectory "%BASE%"
nssm set %NGROK_SVC% DisplayName "Project Tracking Ngrok Tunnel"
nssm set %NGROK_SVC% Description "Forwards https://%NGROK_DOMAIN% to the local backend on port 5000"
nssm set %NGROK_SVC% Start SERVICE_AUTO_START
nssm set %NGROK_SVC% DependOnService %SERVICE%

nssm set %NGROK_SVC% AppStdout "%LOGDIR%\ngrok.log"
nssm set %NGROK_SVC% AppStderr "%LOGDIR%\ngrok_error.log"
nssm set %NGROK_SVC% AppRotateFiles 1
nssm set %NGROK_SVC% AppRotateSeconds 86400
nssm set %NGROK_SVC% AppRotateBytes 10485760

nssm set %NGROK_SVC% AppExit Default Restart
nssm set %NGROK_SVC% AppRestartDelay 3000

echo.
echo Starting ngrok tunnel service ...
nssm start %NGROK_SVC%

echo.
echo ============================================================
echo  Access URL
echo    https://%NGROK_DOMAIN%
echo ============================================================
echo.
echo Backend service commands:
echo   nssm status  %SERVICE%
echo   nssm restart %SERVICE%
echo   nssm stop    %SERVICE%
echo   nssm remove  %SERVICE% confirm
echo.
echo Ngrok service commands:
echo   nssm status  %NGROK_SVC%
echo   nssm restart %NGROK_SVC%
echo   nssm stop    %NGROK_SVC%
echo   nssm remove  %NGROK_SVC% confirm
