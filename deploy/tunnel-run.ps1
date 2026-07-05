#Requires -Version 5.1
<#
.SYNOPSIS
  Starts a Cloudflare quick tunnel to the local Flask backend and keeps the
  Worker's KV key "backend_url" in sync with the (random, per-restart) tunnel URL.

.DESCRIPTION
  cloudflared quick tunnels expose http://127.0.0.1:<BackendPort> at a random
  https://<random>.trycloudflare.com hostname that changes on every restart.
  This script launches cloudflared, reads the current hostname from its local
  metrics endpoint (/quicktunnel), and PUTs "https://<hostname>" into Cloudflare
  Workers KV so the deployed Worker/SPA keeps working with no rebuild or redeploy.

  Intended to run as a Windows service via NSSM (see deploy/README.md).

.REQUIRED ENVIRONMENT VARIABLES
  CLOUDFLARE_API_TOKEN   API token scoped to "Workers KV Storage: Edit"
  CF_ACCOUNT_ID          Cloudflare account id
  CF_KV_NAMESPACE_ID     id of the "CONFIG" KV namespace (from: wrangler kv namespace create CONFIG)
#>

param(
  [int]$BackendPort     = 5000,
  [int]$MetricsPort     = 5054,
  [string]$KvKey        = "backend_url",
  [string]$CloudflaredExe = "cloudflared",
  [int]$PollSeconds     = 5
)

$ErrorActionPreference = "Stop"

foreach ($name in "CLOUDFLARE_API_TOKEN", "CF_ACCOUNT_ID", "CF_KV_NAMESPACE_ID") {
  if (-not (Test-Path "Env:$name")) {
    throw "Missing required environment variable: $name"
  }
}

$metricsUrl = "http://127.0.0.1:$MetricsPort/quicktunnel"
$kvUrl = "https://api.cloudflare.com/client/v4/accounts/$($env:CF_ACCOUNT_ID)/storage/kv/namespaces/$($env:CF_KV_NAMESPACE_ID)/values/$KvKey"
$authHeader = @{ Authorization = "Bearer $($env:CLOUDFLARE_API_TOKEN)" }

function Publish-BackendUrl([string]$hostname) {
  $value = "https://$hostname"
  Invoke-RestMethod -Method Put -Uri $kvUrl -Headers $authHeader -Body $value -ContentType "text/plain" | Out-Null
  Write-Host "[tunnel] published backend_url = $value"
}

Write-Host "[tunnel] starting cloudflared quick tunnel -> http://127.0.0.1:$BackendPort (metrics :$MetricsPort)"
$cfArgs = @(
  "tunnel", "--no-autoupdate",
  "--url", "http://127.0.0.1:$BackendPort",
  "--metrics", "127.0.0.1:$MetricsPort"
)
$proc = Start-Process -FilePath $CloudflaredExe -ArgumentList $cfArgs -PassThru -NoNewWindow

$lastHostname = $null
try {
  while (-not $proc.HasExited) {
    try {
      $info = Invoke-RestMethod -Uri $metricsUrl -TimeoutSec 5
      if ($info.hostname -and $info.hostname -ne $lastHostname) {
        $lastHostname = $info.hostname
        Publish-BackendUrl $lastHostname
      }
    }
    catch {
      # metrics endpoint not ready yet, or a transient failure — retry next loop.
    }
    Start-Sleep -Seconds $PollSeconds
  }
}
finally {
  if ($proc -and -not $proc.HasExited) {
    Write-Host "[tunnel] stopping cloudflared (pid $($proc.Id))"
    $proc.Kill()
  }
}

Write-Host "[tunnel] cloudflared exited with code $($proc.ExitCode)"
exit $proc.ExitCode
