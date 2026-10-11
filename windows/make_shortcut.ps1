# Creates the Desktop shortcut that starts AutoSearch from source (called by setup.bat).
# Target is the venv's pythonw.exe: signed by the PSF, so it runs where Smart App
# Control would refuse an unsigned exe.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$target = Join-Path $root ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $target)) { throw "ambiente Python mancante: $target" }

$lnk = Join-Path ([Environment]::GetFolderPath("Desktop")) "AutoSearch.lnk"
$shell = New-Object -ComObject WScript.Shell
$s = $shell.CreateShortcut($lnk)
$s.TargetPath = $target
$s.Arguments = "windows\launcher.py"
$s.WorkingDirectory = $root
$s.Description = "AutoSearch - offerte di lavoro e concorsi"
$icon = Join-Path $root "windows\autosearch.ico"
if (Test-Path $icon) { $s.IconLocation = $icon }
$s.Save()
Write-Host "collegamento creato: $lnk"
