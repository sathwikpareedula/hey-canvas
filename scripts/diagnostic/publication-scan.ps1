# Bounded publication hygiene scan (tracked files only; no secret values printed).
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Push-Location $root

$tracked = git ls-files
$issues = @()

foreach ($path in $tracked) {
    if ($path -match '(^|/)\.env$|(^|/)credentials\.|\.pem$|id_rsa') {
        $issues += "tracked sensitive name: $path"
    }
}

$patterns = @(
    'sk-[a-zA-Z0-9]{20,}',
    'Bearer\s+[a-zA-Z0-9._-]{20,}',
    'CANVAS_TOKEN\s*=\s*[^\s\$\{][A-Za-z0-9_-]{16,}'
)
foreach ($path in $tracked) {
    if ($path -match '\.(png|jpg|jpeg|gif|webp|ico|woff2?|pdf|db|sqlite)$') { continue }
    $full = Join-Path $root $path
    if (-not (Test-Path $full -PathType Leaf)) { continue }
    $text = Get-Content $full -Raw -ErrorAction SilentlyContinue
    if (-not $text) { continue }
    foreach ($pat in $patterns) {
        if ($text -match $pat) {
            $issues += "pattern match in $path ($pat)"
        }
    }
}

$out = Join-Path $root ".hey-canvas\run\publication-scan.txt"
$report = @("gitleaks: not run (not installed)", "tracked_files: $($tracked.Count)")
if ($issues.Count -eq 0) {
    $report += "issues: none"
} else {
    $report += $issues
}
$report | Set-Content $out -Encoding UTF8
Write-Host "Wrote $out ($($issues.Count) issues)"
Pop-Location
if ($issues.Count -gt 0) { exit 1 }
