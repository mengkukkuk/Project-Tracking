@echo off
REM ============================================================================
REM  install-services-tunnel.bat  —  installs both Windows services with NSSM,
REM  non-interactively (no NSSM GUI), using paths derived from this script's
REM  own location so it is portable across machines.
REM
REM  Services:
REM    ProjTrackApi     -> backend\.venv\Scripts\python.exe backend\server.py
REM    ProjTrackTunnel  -> powershell deploy\tunnel-run.ps1  (quick tunnel + KV updater)
REM
REM  Secrets for ProjTrackTunnel are read from deploy\service.config.bat
REM  (copy service.config.example.bat -> service.config.bat and fill it in).
REM  If any are still missing you'll be prompted once.
REM
REM  USAGE: right-click -> "Run as administrator"   (or run from an elevated cmd)
REM ============================================================================
setlocal EnableExtensions

REM --- Resolve repo root (this script lives in <root>\deploy) ------------------
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT=%%~fI"

REM --- Paths / names ----------------------------------------------------------
set "API_SVC=ProjTrackApi"
set "TUN_SVC=ProjTrackTunnel"
set "PYTHON=%ROOT%\backend\.venv\Scripts\python.exe"
set "SERVER=%ROOT%\backend\server.py"
set "TUNNEL_PS1=%ROOT%\deploy\tunnel-run.ps1"
set "LOGDIR=%ROOT%\deploy\logs"
if not defined NSSM set "NSSM=nssm"  
REM optional override in service.config.bat

REM --- Must be Administrator ---------------------------------------------------
net session >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Please run this script as Administrator.
  goto :end_fail
)

REM --- Load secrets (optional file), then validate -----------------------------
if exist "%SCRIPT_DIR%service.config.bat" call "%SCRIPT_DIR%service.config.bat"

if not defined CLOUDFLARE_API_TOKEN set /p "CLOUDFLARE_API_TOKEN=Enter CLOUDFLARE_API_TOKEN: "
if not defined CF_ACCOUNT_ID        set /p "CF_ACCOUNT_ID=Enter CF_ACCOUNT_ID: "
if not defined CF_KV_NAMESPACE_ID   set /p "CF_KV_NAMESPACE_ID=Enter CF_KV_NAMESPACE_ID: "

REM --- Sanity checks ----------------------------------------------------------
if exist "%NSSM%" ( rem NSSM points directly at an existing file - OK
) else (
  where %NSSM% >nul 2>&1 || ( echo [ERROR] nssm not found on PATH. Install it, or set NSSM=C:\path\to\nssm.exe & goto :end_fail )
)
if not exist "%PYTHON%"     ( echo [ERROR] Python venv missing: "%PYTHON%"    & goto :end_fail )
if not exist "%SERVER%"     ( echo [ERROR] server.py missing:  "%SERVER%"     & goto :end_fail )
if not exist "%TUNNEL_PS1%" ( echo [ERROR] tunnel script missing: "%TUNNEL_PS1%" & goto :end_fail )
for %%V in (CLOUDFLARE_API_TOKEN CF_ACCOUNT_ID CF_KV_NAMESPACE_ID) do (
  if not defined %%V ( echo [ERROR] Missing %%V. & goto :end_fail )
)

if not exist "%LOGDIR%" mkdir "%LOGDIR%"

echo(
echo Repo root : %ROOT%
echo Installing services with NSSM...
echo(

REM ============================================================================
REM  1) Backend API service (waitress on 127.0.0.1:5000)
REM ============================================================================
call :reinstall "%API_SVC%"
%NSSM% install "%API_SVC%" "%PYTHON%"                           || goto :end_fail
%NSSM% set "%API_SVC%" AppParameters "\"%SERVER%\""             || goto :end_fail
%NSSM% set "%API_SVC%" AppDirectory "%ROOT%\backend"            || goto :end_fail
%NSSM% set "%API_SVC%" Start SERVICE_AUTO_START                 >nul
%NSSM% set "%API_SVC%" AppStdout "%LOGDIR%\api.out.log"         >nul
%NSSM% set "%API_SVC%" AppStderr "%LOGDIR%\api.err.log"         >nul
%NSSM% set "%API_SVC%" AppExit Default Restart                  >nul

REM ============================================================================
REM  2) Tunnel + KV updater service (powershell deploy\tunnel-run.ps1)
REM ============================================================================
call :reinstall "%TUN_SVC%"
%NSSM% install "%TUN_SVC%" "powershell.exe"                                              || goto :end_fail
%NSSM% set "%TUN_SVC%" AppParameters "-ExecutionPolicy Bypass -NoProfile -File \"%TUNNEL_PS1%\"" || goto :end_fail
%NSSM% set "%TUN_SVC%" AppDirectory "%ROOT%\deploy"                                      || goto :end_fail
%NSSM% set "%TUN_SVC%" AppEnvironmentExtra "CLOUDFLARE_API_TOKEN=%CLOUDFLARE_API_TOKEN%" "CF_ACCOUNT_ID=%CF_ACCOUNT_ID%" "CF_KV_NAMESPACE_ID=%CF_KV_NAMESPACE_ID%" || goto :end_fail
%NSSM% set "%TUN_SVC%" Start SERVICE_AUTO_START                 >nul
%NSSM% set "%TUN_SVC%" AppStdout "%LOGDIR%\tunnel.out.log"      >nul
%NSSM% set "%TUN_SVC%" AppStderr "%LOGDIR%\tunnel.err.log"      >nul
%NSSM% set "%TUN_SVC%" AppExit Default Restart                  >nul

echo(
echo Starting services...
%NSSM% start "%API_SVC%"
%NSSM% start "%TUN_SVC%"

echo(
echo Done. Manage with:  nssm status/stop/restart/remove ^<service^>
goto :end_ok

REM --- helper: stop+remove a service if it already exists (idempotent) --------
:reinstall
%NSSM% status %1 >nul 2>&1
if not errorlevel 1 (
  echo   %~1 already exists - reinstalling...
  %NSSM% stop %1 >nul 2>&1
  %NSSM% remove %1 confirm >nul 2>&1
)
exit /b 0

:end_fail
echo(
echo [FAILED] See message above.
endlocal & exit /b 1

:end_ok
endlocal & exit /b 0
