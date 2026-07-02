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

set NSSM_EXE=
for %%i in (nssm.exe) do set "NSSM_EXE=%%~$PATH:i"
if not defined NSSM_EXE if exist "%USERPROFILE%\Desktop\files\nssm-2.24-101-g897c7ad\win64\nssm.exe" set "NSSM_EXE=%USERPROFILE%\Desktop\files\nssm-2.24-101-g897c7ad\win64\nssm.exe"
if not defined NSSM_EXE if exist "%USERPROFILE%\Desktop\files\nssm.exe" set "NSSM_EXE=%USERPROFILE%\Desktop\files\nssm.exe"
if not defined NSSM_EXE (
    echo ERROR: nssm.exe not found. Install NSSM or add it to PATH.
    goto :eof
)
set NSSM_CMD="%NSSM_EXE%"

set NGROK_EXE=
for %%i in (ngrok.exe) do set "NGROK_EXE=%%~$PATH:i"
if not defined NGROK_EXE if exist "%USERPROFILE%\Desktop\files\ngrok.exe" set "NGROK_EXE=%USERPROFILE%\Desktop\files\ngrok.exe"
if not defined NGROK_EXE (
    echo ERROR: ngrok.exe not found. Install it or add it to PATH.
    goto :eof
)

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

%NSSM_CMD% install %SERVICE% "%PYTHON%" --host=0.0.0.0 --port=5000 --threads=4 wsgi:app
%NSSM_CMD% set %SERVICE% AppDirectory "%BASE%"
%NSSM_CMD% set %SERVICE% DisplayName "Project Tracking Backend"
%NSSM_CMD% set %SERVICE% Description "Flask/Waitress REST API + SPA for Project Tracking"
%NSSM_CMD% set %SERVICE% Start SERVICE_AUTO_START

:: Redirect stdout/stderr to log files
%NSSM_CMD% set %SERVICE% AppStdout "%LOGDIR%\service.log"
%NSSM_CMD% set %SERVICE% AppStderr "%LOGDIR%\service_error.log"
%NSSM_CMD% set %SERVICE% AppRotateFiles 1
%NSSM_CMD% set %SERVICE% AppRotateSeconds 86400
%NSSM_CMD% set %SERVICE% AppRotateBytes 10485760

:: Restart on failure
%NSSM_CMD% set %SERVICE% AppExit Default Restart
%NSSM_CMD% set %SERVICE% AppRestartDelay 3000

echo.
echo Starting service ...
%NSSM_CMD% start %SERVICE%

:: ============================================================
:: Ngrok tunnel — forwards https://%NGROK_DOMAIN% to port 5000
:: The authtoken is written to a repo-local config file (not the
:: interactive user's profile) because NSSM services run as
:: LocalSystem by default and would not see a per-user ngrok.yml.
:: ============================================================
set NGROK_CFG=%BASE%\ngrok.yml

echo.
echo Configuring ngrok authtoken ...
"%NGROK_EXE%" config add-authtoken "%NGROK_AUTH_TOKEN%" --config "%NGROK_CFG%"
if errorlevel 1 (
    echo ERROR: ngrok config add-authtoken failed.
    goto :eof
)

echo.
echo Installing service: %NGROK_SVC% ...

%NSSM_CMD% install %NGROK_SVC% "%NGROK_EXE%" http 5000 --domain "%NGROK_DOMAIN%" --config "%NGROK_CFG%" --log stdout
%NSSM_CMD% set %NGROK_SVC% AppDirectory "%BASE%"
%NSSM_CMD% set %NGROK_SVC% DisplayName "Project Tracking Ngrok Tunnel"
%NSSM_CMD% set %NGROK_SVC% Description "Forwards https://%NGROK_DOMAIN% to the local backend on port 5000"
%NSSM_CMD% set %NGROK_SVC% Start SERVICE_AUTO_START
%NSSM_CMD% set %NGROK_SVC% DependOnService %SERVICE%

%NSSM_CMD% set %NGROK_SVC% AppStdout "%LOGDIR%\ngrok.log"
%NSSM_CMD% set %NGROK_SVC% AppStderr "%LOGDIR%\ngrok_error.log"
%NSSM_CMD% set %NGROK_SVC% AppRotateFiles 1
%NSSM_CMD% set %NGROK_SVC% AppRotateSeconds 86400
%NSSM_CMD% set %NGROK_SVC% AppRotateBytes 10485760

%NSSM_CMD% set %NGROK_SVC% AppExit Default Restart
%NSSM_CMD% set %NGROK_SVC% AppRestartDelay 3000

echo.
echo Starting ngrok tunnel service ...
%NSSM_CMD% start %NGROK_SVC%

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
