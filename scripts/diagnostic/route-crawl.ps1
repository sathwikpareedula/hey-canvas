# HTTP crawl of intended Hey Canvas routes (requires running frontend).
param(
    [string]$BaseUrl = "http://localhost:3001"
)

$ErrorActionPreference = "Stop"
$routes = @(
    "/",
    "/startup",
    "/onboarding",
    "/today",
    "/dashboard",
    "/courses",
    "/settings",
    "/sync",
    "/changes",
    "/assignments",
    "/materials",
    "/study",
    "/study/guide",
    "/workload",
    "/notifications"
)

$results = @()
function Pass([string]$name) { $results += "PASS $name"; Write-Host "PASS $name" -ForegroundColor Green }
function Fail([string]$name, [string]$why) {
    $results += "FAIL ${name} - $why"
    Write-Host "FAIL ${name} - $why" -ForegroundColor Red
}

foreach ($path in $routes) {
    $url = "$BaseUrl$path"
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 30 -MaximumRedirection 5
        if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 400) {
            if ($r.Content -match "Application error|Internal Server Error") {
                Fail $path "error text in body"
            } else {
                Pass $path
            }
        } else {
            Fail $path "status $($r.StatusCode)"
        }
    } catch {
        Fail $path $_.Exception.Message
    }
}

$runDir = Join-Path $PSScriptRoot "..\..\.hey-canvas\run"
if (-not (Test-Path $runDir)) { New-Item -ItemType Directory -Path $runDir -Force | Out-Null }
$outFile = Join-Path (Resolve-Path $runDir).Path "route-crawl.txt"
$results | Set-Content $outFile -Encoding UTF8
Write-Host "Wrote $outFile"
if ($results -match "^FAIL") { exit 1 }
