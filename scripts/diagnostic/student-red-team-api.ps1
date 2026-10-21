# Student red-team API battery (synthetic DB, isolated port). No private data logged.
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$runDir = Join-Path $root ".hey-canvas\run"
$dbPath = Join-Path $runDir "student-red-team.db"
$backendPort = 18181
$env:HEY_CANVAS_BACKEND_PORT = "$backendPort"
$env:DATABASE_URL = "sqlite:///$($dbPath.Replace('\','/'))"
$env:ACADEMIC_MODEL_PROVIDER = "synthetic"
$env:HEY_CANVAS_FRONTEND_PORT = "13182"
$backendUrl = "http://127.0.0.1:$backendPort"
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
$launcher = Join-Path $root "launcher\windows"

if (-not (Test-Path $venvPy)) { throw "Missing venv: $venvPy" }
New-Item -ItemType Directory -Path $runDir -Force | Out-Null
if (Test-Path $dbPath) { Remove-Item $dbPath -Force }

Push-Location $root
& $venvPy -m app.dev_fixture --database-path $dbPath 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { throw "dev_fixture seed failed" }

& (Join-Path $launcher "Stop-HeyCanvas.ps1") | Out-Null
Start-Sleep -Seconds 1
& (Join-Path $launcher "Start-HeyCanvas.ps1") -NoBrowser 2>&1 | Out-Null

$deadline = 90
$ok = $false
for ($i = 0; $i -lt $deadline; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "$backendUrl/health" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $ok = $true; break }
    } catch {}
    Start-Sleep -Seconds 1
}
if (-not $ok) { throw "Backend not healthy on $backendUrl" }

$env:HEY_CANVAS_BACKEND_URL = $backendUrl
& $venvPy (Join-Path $PSScriptRoot "student_red_team_api.py")
$code = $LASTEXITCODE

& (Join-Path $launcher "Stop-HeyCanvas.ps1") | Out-Null
Pop-Location
exit $code
