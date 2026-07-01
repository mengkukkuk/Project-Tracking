@echo off
:: ============================================================
:: Project Tracking — NSSM Service Uninstaller
:: Run as Administrator. Stops and removes the backend + ngrok
:: services, and best-effort cleans up leftovers from the older
:: Tailscale-based deployment (start_service.bat).
:: ============================================================

set SERVICE=ProjTracking
set NGROK_SVC=ProjTrackingNgrok
set LEGACY_FRONTEND_SVC=ProjTrackingFrontend

set BASE=%~dp0
if "%BASE:~-1%"=="\" set BASE=%BASE:~0,-1%

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

:: ---- Ngrok tunnel --------------------------------------------
nssm status %NGROK_SVC% >nul 2>&1
if errorlevel 1 (
    echo [SKIP] %NGROK_SVC% not found.
) else (
    echo Stopping %NGROK_SVC% ...
    nssm stop %NGROK_SVC% confirm
    echo Removing %NGROK_SVC% ...
    nssm remove %NGROK_SVC% confirm
    echo Done: %NGROK_SVC% removed.
)

echo.

:: ---- Legacy cleanup: old Tailscale-based frontend service ---
nssm status %LEGACY_FRONTEND_SVC% >nul 2>&1
if errorlevel 1 (
    echo [SKIP] %LEGACY_FRONTEND_SVC% not found.
) else (
    echo Stopping legacy %LEGACY_FRONTEND_SVC% ...
    nssm stop %LEGACY_FRONTEND_SVC% confirm
    echo Removing legacy %LEGACY_FRONTEND_SVC% ...
    nssm remove %LEGACY_FRONTEND_SVC% confirm
    echo Done: %LEGACY_FRONTEND_SVC% removed.
)

echo.

:: ---- Legacy cleanup: Tailscale Serve config -------------------
where tailscale >nul 2>&1
if errorlevel 1 (
    echo [SKIP] tailscale not found on PATH.
) else (
    echo Disabling legacy Tailscale Serve config ...
    tailscale serve --https=443 off >nul 2>&1
)

echo.

:: ---- Legacy cleanup: local ngrok config (holds the authtoken) -
if exist "%BASE%\ngrok.yml" (
    echo Removing "%BASE%\ngrok.yml" ...
    del /f /q "%BASE%\ngrok.yml"
)

echo.
echo All services removed.
