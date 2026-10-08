@echo off
rem Avvio con un click su Windows: avvia l'interfaccia web (se non attiva) e la apre nel browser.
cd /d "%~dp0"
set URL=http://127.0.0.1:8765
if not exist data mkdir data

curl -sf %URL%/api/status >/dev/null 2>&1 && goto open
start "" /b .venv\Scripts\pythonw.exe -m autosearch.web --port 8765 >> data\web.log 2>&1
for /l %%i in (1,1,15) do (
    curl -sf %URL%/api/status >/dev/null 2>&1 && goto open
    timeout /t 1 /nobreak >nul
)

:open
start "" %URL%
