@echo off
:: ============================================================
:: Project Tracking Backend — NSSM Windows Service Installer
:: Run this script once as Administrator to install the service.
:: ============================================================

set SERVICE=ProjTracking
set BASE=G:\Code\proj-tracking\Project-Tracking\backend
set PYTHON=%BASE%\.venv\Scripts\waitress-serve.exe
set LOGDIR=%BASE%\logs

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
echo Done. Use these commands to manage:
echo   nssm status %SERVICE%
echo   nssm restart %SERVICE%
echo   nssm stop %SERVICE%
echo   nssm remove %SERVICE% confirm
