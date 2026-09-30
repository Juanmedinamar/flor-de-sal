@echo off
chcp 65001 >nul
title Vino Tracker

REM Cambiar al directorio del script
cd /d "%~dp0"

REM Verificar si Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    py --version >nul 2>&1
    if errorlevel 1 (
        echo.
        echo ========================================
        echo       VINO TRACKER - ERROR
        echo ========================================
        echo.
        echo Python no esta instalado.
        echo.
        echo Para usar Vino Tracker necesitas:
        echo.
        echo 1. Instalar Python 3.11 o superior desde:
        echo    https://www.python.org/downloads/
        echo.
        echo 2. Marcar la opcion "Add Python to PATH"
        echo    durante la instalacion.
        echo.
        echo 3. Reiniciar el ordenador.
        echo.
        echo ========================================
        pause
        exit /b 1
    ) else (
        set "PYTHON_CMD=py"
    )
) else (
    set "PYTHON_CMD=python"
)

REM Verificar si las dependencias están instaladas
%PYTHON_CMD% -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo.
    echo ========================================
    echo       VINO TRACKER - INSTALACION
    echo ========================================
    echo.
    echo Instalando dependencias por primera vez...
    echo.
    %PYTHON_CMD% -m pip install -r requirements.txt
    %PYTHON_CMD% -m playwright install chromium firefox
    echo.
    echo Instalacion completada.
    echo.
    pause
)

REM Iniciar Vino Tracker
echo.
echo ========================================
echo       VINO TRACKER
echo ========================================
echo.
echo Iniciando Vino Tracker...
echo.
echo Se abrira el navegador automaticamente.
echo.
echo Para cerrar, presiona Ctrl+C en esta ventana.
echo.

start "" /min cmd /c "%PYTHON_CMD% -m streamlit run app.py --server.headless true --server.port 8501"

REM Esperar un momento y abrir el navegador
timeout /t 5 /nobreak >nul
start http://localhost:8501

REM Mantener la ventana abierta
pause
