# Start isolated Hey Canvas RC stack (does not use live V1.1 ports).
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Run = Join-Path $Root ".hey-canvas\verify-rc"
New-Item -ItemType Directory -Force -Path $Run | Out-Null

$BackendPort = if ($env:HEY_CANVAS_RC_BACKEND_PORT) { [int]$env:HEY_CANVAS_RC_BACKEND_PORT } else { 18410 }
$FrontendPort = if ($env:HEY_CANVAS_RC_FRONTEND_PORT) { [int]$env:HEY_CANVAS_RC_FRONTEND_PORT } else { 18411 }
$DbPath = Join-Path $Run "rc.db"
$NextDist = ".next-verify-$FrontendPort"

$env:DATABASE_URL = "sqlite:///./.hey-canvas/verify-rc/rc.db"
$env:ACADEMIC_MODEL_PROVIDER = "synthetic"
$env:LOCAL_API_GUARD_ENABLED = "true"
$env:HEY_CANVAS_NEXT_DIST_DIR = $NextDist
$env:NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:$BackendPort"
$env:NEXT_PUBLIC_ACADEMIC_API_MODE = "http"

Write-Host "Seeding demo DB at $DbPath"
Push-Location $Root
if (-not (Test-Path $DbPath)) {
    uv run academic-seed-demo --database-path $DbPath | Out-Host
}
Write-Host "Backend http://127.0.0.1:$BackendPort (logs: $Run\backend.log)"
$backendCmd = "cd `"$Root`"; `$env:DATABASE_URL='$($env:DATABASE_URL)'; `$env:ACADEMIC_MODEL_PROVIDER='synthetic'; `$env:LOCAL_API_GUARD_ENABLED='true'; uv run uvicorn app.main:app --host 127.0.0.1 --port $BackendPort --app-dir backend"
Start-Process powershell -ArgumentList "-NoProfile","-Command",$backendCmd -WindowStyle Minimized
Start-Sleep -Seconds 4
$health = Invoke-RestMethod "http://127.0.0.1:$BackendPort/health" -TimeoutSec 10
Write-Host "Backend health: $($health | ConvertTo-Json -Compress)"

Write-Host "Frontend http://127.0.0.1:$FrontendPort distDir=$NextDist"
$frontendCmd = "cd `"$Root\frontend`"; `$env:HEY_CANVAS_NEXT_DIST_DIR='$NextDist'; `$env:NEXT_PUBLIC_API_BASE_URL='http://127.0.0.1:$BackendPort'; `$env:NEXT_PUBLIC_ACADEMIC_API_MODE='http'; npx --yes next dev -p $FrontendPort -H 127.0.0.1"
Start-Process powershell -ArgumentList "-NoProfile","-Command",$frontendCmd -WindowStyle Minimized
Write-Host "Wait ~15s then open http://127.0.0.1:$FrontendPort/dashboard"
Pop-Location
