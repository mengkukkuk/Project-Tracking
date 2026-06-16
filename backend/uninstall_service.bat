@echo off
:: ============================================================
:: Project Tracking — NSSM Service Uninstaller
:: Run as Administrator. Stops and removes both services.
:: ============================================================

set SERVICE=ProjTracking
set FRONTEND_SVC=ProjTrackingFrontend

echo Stopping and removing services...
echo.

:: ---- Backend -----------------------------------------------
nssm status %SERVICE% >nul 2>&1
if errorlevel 1 (
    echo [SKIP] %SERVICE% not found.
) else (
    echo Stopping %SERVICE% ...
    nssm stop %SERVICE% confirm
    echo Removing %SERVICE% ...
    nssm remove %SERVICE% confirm
    echo Done: %SERVICE% removed.
)

echo.

:: ---- Frontend ----------------------------------------------
nssm status %FRONTEND_SVC% >nul 2>&1
if errorlevel 1 (
    echo [SKIP] %FRONTEND_SVC% not found.
) else (
    echo Stopping %FRONTEND_SVC% ...
    nssm stop %FRONTEND_SVC% confirm
    echo Removing %FRONTEND_SVC% ...
    nssm remove %FRONTEND_SVC% confirm
    echo Done: %FRONTEND_SVC% removed.
)

echo.
echo All services removed.