@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-HeyCanvas.ps1" %*
if errorlevel 1 (
  echo.
  echo Hey Canvas could not start. See .hey-canvas\run\logs for details.
  pause
)
endlocal
