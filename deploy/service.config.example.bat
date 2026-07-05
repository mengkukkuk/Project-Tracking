@echo off
REM ============================================================================
REM  Copy this file to  service.config.bat  and fill in your real values.
REM  install-services-tunnel.bat loads it automatically (no manual typing).
REM  service.config.bat holds secrets — do NOT commit it.
REM ============================================================================

REM Cloudflare API token scoped to "Workers KV Storage: Edit"
set "CLOUDFLARE_API_TOKEN=cf-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

REM Your Cloudflare account id
set "CF_ACCOUNT_ID=0123456789abcdef0123456789abcdef"

REM id of the "CONFIG" KV namespace (wrangler kv namespace create CONFIG)
set "CF_KV_NAMESPACE_ID=33032bdc02b24980baaa4732b9545741"

REM Optional: full path to nssm.exe if it is not on PATH
REM set "NSSM=C:\tools\nssm\win64\nssm.exe"
