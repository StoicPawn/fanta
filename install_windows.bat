@echo off
setlocal
cd /d "%~dp0"

echo [Fanta Auction Lab] Preparazione ambiente Windows...

py -3.12 --version >nul 2>&1
if not errorlevel 1 (
    set "FANTA_PYTHON=py -3.12"
) else (
    py -3 --version >nul 2>&1
    if not errorlevel 1 (
        set "FANTA_PYTHON=py -3"
    ) else (
        python --version >nul 2>&1
        if errorlevel 1 goto :python_missing
        set "FANTA_PYTHON=python"
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo Creo l'ambiente virtuale...
    %FANTA_PYTHON% -m venv .venv
    if errorlevel 1 goto :failed
)

echo Installo o aggiorno le dipendenze...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed

echo.
echo Installazione completata. Ora fai doppio clic su run_windows.bat
pause
exit /b 0

:python_missing
echo.
echo Python non trovato. Installa Python 3.12 da https://www.python.org/downloads/windows/
echo Durante l'installazione seleziona "Add python.exe to PATH", poi riesegui questo file.
pause
exit /b 1

:failed
echo.
echo Installazione non riuscita. Leggi l'errore sopra prima di chiudere la finestra.
pause
exit /b 1
