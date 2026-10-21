@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo ERROR: Vino Tracker no esta instalado.
    echo Ejecuta primero instalar.bat
    echo.
    pause
    exit /b 1
)

set "PATH=%~dp0.venv\Scripts;%PATH%"

echo.
echo ========================================
echo          VINO TRACKER
echo ========================================
echo.
echo Iniciando la aplicacion...
echo.

".venv\Scripts\python.exe" -m streamlit run app.py

pause
