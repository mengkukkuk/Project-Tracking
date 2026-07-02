@echo off
:: ============================================================
:: Project Tracking Backend — NSSM Windows Service Installer
:: Single-origin deployment: Flask serves the built Vue SPA AND
:: the /api/* routes from one port (5000), and a public ngrok
:: domain tunnels straight to that port.
:: Run this script once as Administrator to install both services.
:: ============================================================

:: NSSM silently no-ops (install/set/start print "Administrator access is
:: needed" but exit 0) when not elevated, so a non-admin run can look like
:: it succeeded while actually installing nothing. Fail loudly instead.
net session >nul 2>&1
if errorlevel 1 (
    echo ERROR: This script must be run as Administrator.
    echo Right-click install_service.bat and choose "Run as administrator".
    goto :end
)

set SERVICE=ProjTracking
set NGROK_SVC=ProjTrackingNgrok

:: Derive the backend dir from this script's own location (portable across devices).
:: %~dp0 ends with a backslash — strip it so quoted paths don't escape the quote.
set BASE=%~dp0
if "%BASE:~-1%"=="\" set BASE=%BASE:~0,-1%

set PYTHON=%BASE%\.venv\Scripts\waitress-serve.exe
set LOGDIR=%BASE%\logs

:: Tools are bundled in this folder so deployment needs zero PATH setup.
set NSSM=%BASE%\nssm.exe
set NGROK=%BASE%\ngrok.exe

:: Pre-flight: the virtualenv must exist (run setup first — see README).
if not exist "%PYTHON%" (
    echo ERROR: %PYTHON% not found.
    echo Create the venv and install deps first:
    echo     py -3.11 -m venv "%BASE%\.venv"
    echo     "%BASE%\.venv\Scripts\pip" install -r "%BASE%\requirements.txt"
    goto :end
)

:: Pre-flight: the bundled service tools must be present.
if not exist "%NSSM%" (
    echo ERROR: %NSSM% not found. The bundled nssm.exe must sit next to this script.
    goto :end
)
if not exist "%NGROK%" (
    echo ERROR: %NGROK% not found. The bundled ngrok.exe must sit next to this script.
    goto :end
)

:: ============================================================
:: Load NGROK_AUTH_TOKEN / NGROK_DOMAIN from .env
:: ============================================================
if not exist "%BASE%\.env" (
    echo ERROR: "%BASE%\.env" not found.
    echo Copy .env.example to .env and set NGROK_AUTH_TOKEN / NGROK_DOMAIN first.
    goto :end
)

for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%BASE%\.env") do (
    if not "%%A"=="" if not "%%B"=="" set "%%A=%%B"
)

if not defined NGROK_AUTH_TOKEN (
    echo ERROR: NGROK_AUTH_TOKEN is not set in "%BASE%\.env".
    goto :end
)
if not defined NGROK_DOMAIN (
    echo ERROR: NGROK_DOMAIN is not set in "%BASE%\.env".
    goto :end
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
    goto :end
)
popd

:: Create log directory
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

:: ============================================================
:: Backend service — Flask/Waitress (serves API + built SPA)
:: ============================================================
echo.
echo Installing service: %SERVICE% ...

"%NSSM%" install %SERVICE% "%PYTHON%" --host=0.0.0.0 --port=5000 --threads=4 wsgi:app
"%NSSM%" set %SERVICE% AppDirectory "%BASE%"
"%NSSM%" set %SERVICE% DisplayName "Project Tracking Backend"
"%NSSM%" set %SERVICE% Description "Flask/Waitress REST API + SPA for Project Tracking"
"%NSSM%" set %SERVICE% Start SERVICE_AUTO_START

:: Redirect stdout/stderr to log files
"%NSSM%" set %SERVICE% AppStdout "%LOGDIR%\service.log"
"%NSSM%" set %SERVICE% AppStderr "%LOGDIR%\service_error.log"
"%NSSM%" set %SERVICE% AppRotateFiles 1
"%NSSM%" set %SERVICE% AppRotateSeconds 86400
"%NSSM%" set %SERVICE% AppRotateBytes 10485760

:: Restart on failure
"%NSSM%" set %SERVICE% AppExit Default Restart
"%NSSM%" set %SERVICE% AppRestartDelay 3000

echo.
echo Starting service ...
"%NSSM%" start %SERVICE%
"%NSSM%" status %SERVICE% | findstr /i "RUNNING" >nul
if errorlevel 1 (
    echo WARNING: %SERVICE% does not report RUNNING. Check "%LOGDIR%\service_error.log".
)

:: ============================================================
:: Ngrok tunnel — forwards https://%NGROK_DOMAIN% to port 5000
:: The authtoken is written to a repo-local config file (not the
:: interactive user's profile) because NSSM services run as
:: LocalSystem by default and would not see a per-user ngrok.yml.
:: ============================================================
set NGROK_CFG=%BASE%\ngrok.yml

echo.
echo Configuring ngrok authtoken ...
"%NGROK%" config add-authtoken %NGROK_AUTH_TOKEN% --config "%NGROK_CFG%"
if errorlevel 1 (
    echo ERROR: ngrok config add-authtoken failed using "%NGROK%".
    goto :end
)

echo.
echo Installing service: %NGROK_SVC% ...

"%NSSM%" install %NGROK_SVC% "%NGROK%"
:: nssm's "install ... args..." form loses quoting when it rejoins multi-word
:: arguments, so a repo path with a space (e.g. this one) breaks --config.
:: Setting AppParameters as one already-quoted string avoids that.
"%NSSM%" set %NGROK_SVC% AppParameters "http 5000 --url https://%NGROK_DOMAIN% --config ""%NGROK_CFG%"" --log stdout"
"%NSSM%" set %NGROK_SVC% AppDirectory "%BASE%"
"%NSSM%" set %NGROK_SVC% DisplayName "Project Tracking Ngrok Tunnel"
"%NSSM%" set %NGROK_SVC% Description "Forwards https://%NGROK_DOMAIN% to the local backend on port 5000"
"%NSSM%" set %NGROK_SVC% Start SERVICE_AUTO_START
"%NSSM%" set %NGROK_SVC% DependOnService %SERVICE%

"%NSSM%" set %NGROK_SVC% AppStdout "%LOGDIR%\ngrok.log"
"%NSSM%" set %NGROK_SVC% AppStderr "%LOGDIR%\ngrok_error.log"
"%NSSM%" set %NGROK_SVC% AppRotateFiles 1
"%NSSM%" set %NGROK_SVC% AppRotateSeconds 86400
"%NSSM%" set %NGROK_SVC% AppRotateBytes 10485760

"%NSSM%" set %NGROK_SVC% AppExit Default Restart
"%NSSM%" set %NGROK_SVC% AppRestartDelay 3000

echo.
echo Starting ngrok tunnel service ...
"%NSSM%" start %NGROK_SVC%
"%NSSM%" status %NGROK_SVC% | findstr /i "RUNNING" >nul
if errorlevel 1 (
    echo WARNING: %NGROK_SVC% does not report RUNNING. Check "%LOGDIR%\ngrok_error.log".
)

echo.
echo ============================================================
echo  Access URL
echo    https://%NGROK_DOMAIN%
echo ============================================================
echo.
echo Backend service commands:
echo   "%NSSM%" status  %SERVICE%
echo   "%NSSM%" restart %SERVICE%
echo   "%NSSM%" stop    %SERVICE%
echo   "%NSSM%" remove  %SERVICE% confirm
echo.
echo Ngrok service commands:
echo   "%NSSM%" status  %NGROK_SVC%
echo   "%NSSM%" restart %NGROK_SVC%
echo   "%NSSM%" stop    %NGROK_SVC%
echo   "%NSSM%" remove  %NGROK_SVC% confirm

:end
echo.
pause
