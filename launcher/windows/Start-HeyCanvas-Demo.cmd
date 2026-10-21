@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-HeyCanvas.ps1" -Demo %*
if errorlevel 1 (
  echo.
  echo Hey Canvas demo could not start. See .hey-canvas\run\logs for details.
  pause
)
endlocal
