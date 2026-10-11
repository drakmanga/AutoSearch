@echo off
rem Installazione con un click su Windows: crea l'ambiente Python, installa le
rem dipendenze e mette AutoSearch sul Desktop. Si puo' rilanciare dopo un
rem aggiornamento del codice per aggiornare le dipendenze.
setlocal
cd /d "%~dp0"

echo === AutoSearch: installazione ===
echo.

rem Python 3: il launcher py, poi python nel PATH. Lo stub del Microsoft Store
rem esce con 9009, quindi non viene preso per buono.
set "PY="
py -3 --version >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if not defined PY (
    python --version >nul 2>&1
    if not errorlevel 1 set "PY=python"
)
rem PATH non ancora aggiornato (tipico subito dopo l'installazione di Python):
rem cerco nelle cartelle in cui python.org installa di default
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" set "PY="%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" -3"
if not defined PY for /f "delims=" %%d in ('dir /b /ad /o-n "%LOCALAPPDATA%\Programs\Python\Python3*" 2^>nul') do if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\%%d\python.exe" set "PY="%LOCALAPPDATA%\Programs\Python\%%d\python.exe""
if not defined PY for /f "delims=" %%d in ('dir /b /ad /o-n "%ProgramFiles%\Python3*" 2^>nul') do if not defined PY if exist "%ProgramFiles%\%%d\python.exe" set "PY="%ProgramFiles%\%%d\python.exe""

if not defined PY (
    echo Python 3 non trovato.
    echo.
    echo Installalo da https://www.python.org/downloads/ ricordando di spuntare
    echo "Add python.exe to PATH", poi rilancia questo file.
    echo.
    pause
    exit /b 1
)

if exist .venv (
    echo [1/4] ambiente Python: gia presente
) else (
    echo [1/4] creo l'ambiente Python...
    %PY% -m venv .venv || goto fail
)

echo [2/4] installo le dipendenze...
.venv\Scripts\python.exe -m pip install --upgrade pip --quiet || goto fail
.venv\Scripts\python.exe -m pip install -r requirements.txt --quiet || goto fail

echo [3/4] preparo l'icona...
.venv\Scripts\python.exe windows\make_icon.py || goto fail

echo [4/4] creo il collegamento sul Desktop...
powershell -NoProfile -ExecutionPolicy Bypass -File windows\make_shortcut.ps1 || goto fail

echo.
echo === Fatto: trovi AutoSearch sul Desktop. Lo apro. ===
start "" .venv\Scripts\pythonw.exe windows\launcher.py
exit /b 0

:fail
echo.
echo Installazione interrotta: l'errore e' qui sopra.
pause
exit /b 1
