@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo L'app non e' ancora installata. Avvia prima install_windows.bat
    pause
    exit /b 1
)

echo Avvio Fanta Auction Lab...
echo Per fermare l'app, torna in questa finestra e premi Ctrl+C.
".venv\Scripts\python.exe" -m streamlit run app.py

if errorlevel 1 (
    echo.
    echo L'app si e' chiusa con un errore. Leggi il messaggio sopra.
    pause
)
