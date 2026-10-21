# Hey Canvas launcher configuration (project-relative; override via environment).
$ErrorActionPreference = "Stop"

function Get-HeyCanvasRepoRoot {
    $scriptDir = Split-Path -Parent $MyInvocation.PSCommandPath
    return (Resolve-Path (Join-Path $scriptDir "..\..")).Path
}

function Get-HeyCanvasConfig {
    $root = Get-HeyCanvasRepoRoot
    $runDir = Join-Path $root ".hey-canvas\run"
    if (-not (Test-Path $runDir)) {
        New-Item -ItemType Directory -Path $runDir -Force | Out-Null
    }

    $backendPort = if ($env:HEY_CANVAS_BACKEND_PORT) { [int]$env:HEY_CANVAS_BACKEND_PORT } else { 8000 }
    $frontendPort = if ($env:HEY_CANVAS_FRONTEND_PORT) { [int]$env:HEY_CANVAS_FRONTEND_PORT } else { 3001 }
    $backendHost = if ($env:HEY_CANVAS_BACKEND_HOST) { $env:HEY_CANVAS_BACKEND_HOST } else { "127.0.0.1" }
    $frontendHost = if ($env:HEY_CANVAS_FRONTEND_HOST) { $env:HEY_CANVAS_FRONTEND_HOST } else { "localhost" }

    $ollamaHost = if ($env:HEY_CANVAS_OLLAMA_HOST) { $env:HEY_CANVAS_OLLAMA_HOST } else { "127.0.0.1" }
    $ollamaPort = if ($env:HEY_CANVAS_OLLAMA_PORT) { [int]$env:HEY_CANVAS_OLLAMA_PORT } else { 11434 }

    return @{
        RepoRoot       = $root
        RunDir         = $runDir
        StateFile      = Join-Path $runDir "processes.json"
        LogDir         = Join-Path $runDir "logs"
        BackendPort    = $backendPort
        FrontendPort   = $frontendPort
        BackendUrl     = "http://${backendHost}:$backendPort"
        FrontendUrl    = "http://${frontendHost}:$frontendPort"
        OllamaUrl      = "http://${ollamaHost}:$ollamaPort"
        OllamaWaitSec  = 45
        VenvPython     = if ($env:HEY_CANVAS_VENV_PYTHON) {
            $env:HEY_CANVAS_VENV_PYTHON
        } else {
            Join-Path $root ".venv\Scripts\python.exe"
        }
        FrontendDir    = Join-Path $root "frontend"
        HealthTimeoutSec = 90
        FrontendTimeoutSec = 120
    }
}
