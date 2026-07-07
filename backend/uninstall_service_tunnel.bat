@echo off
:: ============================================================
:: Project Tracking — NSSM Service Uninstaller
:: Run as Administrator. Stops and removes the backend + ngrok
:: services, and best-effort cleans up leftovers from the older
:: Tailscale-based deployment (start_service.bat).
:: ============================================================

:: NSSM silently no-ops (prints "Administrator access is needed" but exits 0)
:: when not elevated, so failures here would otherwise go unnoticed.
net session >nul 2>&1
if errorlevel 1 (
    echo ERROR: This script must be run as Administrator.
    echo Right-click uninstall_service.bat and choose "Run as administrator".
    goto :end
)

set SERVICE=ProjTrackApi
set NGROK_SVC=ProjTrackTunnel
set LEGACY_FRONTEND_SVC=ProjTrackingFrontend

set BASE=%~dp0
if "%BASE:~-1%"=="\" set BASE=%BASE:~0,-1%

:: Bundled service manager — no PATH dependency.
set NSSM=%BASE%\nssm.exe
if not exist "%NSSM%" (
    echo ERROR: %NSSM% not found. The bundled nssm.exe must sit next to this script.
    goto :end
)

echo Stopping and removing services...
echo.

:: ---- Backend -----------------------------------------------
"%NSSM%" status %SERVICE% >nul 2>&1
if errorlevel 1 (
    echo [SKIP] %SERVICE% not found.
) else (
    echo Stopping %SERVICE% ...
    "%NSSM%" stop %SERVICE% confirm
    echo Removing %SERVICE% ...
    "%NSSM%" remove %SERVICE% confirm
    echo Done: %SERVICE% removed.
)

echo.

:: ---- Ngrok tunnel --------------------------------------------
"%NSSM%" status %NGROK_SVC% >nul 2>&1
if errorlevel 1 (
    echo [SKIP] %NGROK_SVC% not found.
) else (
    echo Stopping %NGROK_SVC% ...
    "%NSSM%" stop %NGROK_SVC% confirm
    echo Removing %NGROK_SVC% ...
    "%NSSM%" remove %NGROK_SVC% confirm
    echo Done: %NGROK_SVC% removed.
)

echo.

:: ---- Orphan cleanup: NSSM stops the tunnel service by killing --
:: powershell.exe, which can leave its cloudflared child running and
:: holding the metrics port. Kill any leftover cloudflared.exe so a
:: later reinstall/start isn't wedged by a dead port bind.
:: NOTE: intentionally not piping through "find" — on machines with Git
:: for Windows on PATH, its usr\bin\find.exe (GNU find) can shadow the
:: real System32\find.exe and silently break `find /i "..."` detection.
:: taskkill self-reports via errorlevel, so no detection step is needed.
echo Cleaning up any leftover cloudflared.exe ...
taskkill /f /im cloudflared.exe >nul 2>&1
if errorlevel 128 (
    echo [SKIP] No leftover cloudflared.exe process.
) else if errorlevel 1 (
    echo [WARN] Could not stop cloudflared.exe - access denied. Re-run this script as Administrator.
) else (
    echo Done: cloudflared.exe cleaned up.
)

echo.

:: ---- Legacy cleanup: old Tailscale-based frontend service ---
"%NSSM%" status %LEGACY_FRONTEND_SVC% >nul 2>&1
if errorlevel 1 (
    echo [SKIP] %LEGACY_FRONTEND_SVC% not found.
) else (
    echo Stopping legacy %LEGACY_FRONTEND_SVC% ...
    "%NSSM%" stop %LEGACY_FRONTEND_SVC% confirm
    echo Removing legacy %LEGACY_FRONTEND_SVC% ...
    "%NSSM%" remove %LEGACY_FRONTEND_SVC% confirm
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

:end
echo.
pause
