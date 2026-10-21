@echo off
setlocal
cd /d "%~dp0"

echo.
echo ========================================
echo       VINO TRACKER - INSTALACION
echo ========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no esta instalado.
    echo Instala Python 3.11 o superior y vuelve a ejecutar este archivo.
    echo.
    pause
    exit /b 1
)

echo Python encontrado:
python --version
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Creando entorno virtual...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR creando el entorno virtual.
        pause
        exit /b 1
    )
) else (
    echo El entorno virtual ya existe.
)

echo.
echo Actualizando pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip

if errorlevel 1 (
    echo ERROR actualizando pip.
    pause
    exit /b 1
)

echo.
echo Instalando Vino Tracker y sus dependencias...
".venv\Scripts\python.exe" -m pip install -r requirements.txt

if errorlevel 1 (
    echo ERROR instalando las dependencias.
    pause
    exit /b 1
)

echo.
echo Instalando Chromium para Playwright...
".venv\Scripts\python.exe" -m playwright install chromium

if errorlevel 1 (
    echo ERROR instalando Chromium.
    pause
    exit /b 1
)

echo.
echo ========================================
echo       INSTALACION COMPLETADA
echo ========================================
echo.
echo Ya puedes ejecutar iniciar.bat
echo.
pause
