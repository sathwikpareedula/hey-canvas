# Bounded Ollama readiness via HTTP (never use unbounded `ollama list`).
param(
    [string]$BaseUrl = "http://127.0.0.1:11434",
    [int]$TimeoutSec = 5,
    [string]$RequiredModel = "llama3.2:3b"
)

$ErrorActionPreference = "Stop"
$summary = @{
    ok           = $false
    base_url     = $BaseUrl
    timeout_sec  = $TimeoutSec
    required_model = $RequiredModel
    model_count  = 0
    has_required = $false
    error        = $null
}

try {
    $uri = "$BaseUrl/api/tags"
    $resp = Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec $TimeoutSec
    if ($resp.StatusCode -lt 200 -or $resp.StatusCode -ge 300) {
        $summary.error = "http_$($resp.StatusCode)"
    } else {
        $data = $resp.Content | ConvertFrom-Json
        $names = @($data.models | ForEach-Object { $_.name })
        $summary.model_count = $names.Count
        $summary.has_required = $names -contains $RequiredModel
        $summary.ok = $summary.has_required
        if (-not $summary.has_required) {
            $summary.error = "missing_required_model"
        }
    }
} catch {
    $summary.error = $_.Exception.Message
}

$out = Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path ".hey-canvas\run\ollama-http-probe.json"
$outDir = Split-Path $out
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir -Force | Out-Null }
$summary | ConvertTo-Json | Set-Content -Path $out -Encoding UTF8
$summary | ConvertTo-Json -Compress
if (-not $summary.ok) { exit 1 }
exit 0
