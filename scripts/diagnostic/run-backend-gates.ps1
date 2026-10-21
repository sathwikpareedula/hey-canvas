# Backend quality gates with Windows-safe pytest temp dir.
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$tmp = Join-Path $root ".hey-canvas\pytest-tmp"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$env:TMP = $tmp
$env:TEMP = $tmp
$py = Join-Path $root ".venv\Scripts\python.exe"
Push-Location $root
& $py -m ruff check backend
& $py -m mypy
& $py -m pytest backend/tests -q
Pop-Location
