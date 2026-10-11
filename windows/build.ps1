# Builds dist\AutoSearch-Setup-<version>.exe from a clean checkout.
# Needs: Python 3 (python.org) and Inno Setup 6 (winget install JRSoftware.InnoSetup).
#     powershell -ExecutionPolicy Bypass -File windows\build.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$py = ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "== creo .venv =="
    $base = "py"
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) { $base = "python" }
    & $base -m venv .venv
}
Write-Host "== dipendenze =="
# invoked as python -m: the pip-generated pyinstaller.exe shim is unsigned and
# Smart App Control blocks it on machines where it is enabled
& $py -m pip install --upgrade pip --quiet
& $py -m pip install -r requirements.txt pyinstaller --quiet

Write-Host "== icona =="
& $py windows\make_icon.py

Write-Host "== exe =="
& $py -m PyInstaller windows\autosearch.spec --noconfirm --distpath dist --workpath build

Write-Host "== installer =="
$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "ISCC.exe non trovato: winget install JRSoftware.InnoSetup" }
& $iscc windows\installer.iss

# the installer ships inside the repo, so whoever downloads it gets Windows and
# Linux in one go: keep the copy in the root in step with the build
Write-Host "== copia in radice =="
Get-ChildItem "$root\AutoSearch-Setup-*.exe" -ErrorAction SilentlyContinue | Remove-Item -Force
Copy-Item dist\AutoSearch-Setup-*.exe $root -Force

Write-Host "`nPronto:" -ForegroundColor Green
Get-ChildItem "$root\AutoSearch-Setup-*.exe" | Select-Object Name, @{n="MB";e={[math]::Round($_.Length/1MB,1)}}
