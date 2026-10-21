# Build frontend, run production server on isolated port, crawl routes (no dev overlay).
param(
    [int]$Port = 13102
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$frontend = Join-Path $root "frontend"
$logDir = Join-Path $root ".hey-canvas\run\logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

Push-Location $frontend
$env:NEXT_PUBLIC_ACADEMIC_API_MODE = "http"
if (-not $env:NEXT_PUBLIC_API_BASE_URL) {
    $env:NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000"
}
npm run build | Out-Null
$proc = Start-Process -FilePath "cmd.exe" -ArgumentList @("/c", "npx next start -p $Port") `
    -WorkingDirectory $frontend -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $logDir "prod-smoke.log") `
    -RedirectStandardError (Join-Path $logDir "prod-smoke.err.log")
Pop-Location

$base = "http://localhost:$Port"
$deadline = (Get-Date).AddSeconds(90)
$ready = $false
while ((Get-Date) -lt $deadline) {
    try {
        $r = Invoke-WebRequest -Uri "$base/startup" -UseBasicParsing -TimeoutSec 5
        if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 300 -and $r.Content -match "Hey Canvas") {
            $ready = $true
            break
        }
    } catch { }
    Start-Sleep -Seconds 2
}
if (-not $ready) {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    throw "Production server did not become ready on port $Port"
}

try {
    $courses = Invoke-RestMethod -Uri "$base/api/courses" -TimeoutSec 15
    if (-not ($courses -is [Array]) -or $courses.Count -lt 1) {
        throw "Production proxy returned no courses (rewrites may target wrong backend - rebuild with NEXT_PUBLIC_API_BASE_URL)"
    }
} catch {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    throw $_
}

& (Join-Path $PSScriptRoot "route-crawl.ps1") -BaseUrl $base
$exit = $LASTEXITCODE
Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
exit $exit
