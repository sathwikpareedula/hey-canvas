# Creates a Desktop shortcut to Start-HeyCanvas.cmd (student-facing entry).
. (Join-Path $PSScriptRoot "config.ps1")
$cfg = Get-HeyCanvasConfig

$cmdPath = Join-Path $PSScriptRoot "Start-HeyCanvas.cmd"
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "Hey Canvas.lnk"

$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $cmdPath
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.WindowStyle = 7
$shortcut.Description = "Start Hey Canvas on this computer"
$shortcut.Save()

Write-Host "Created shortcut: $shortcutPath"
