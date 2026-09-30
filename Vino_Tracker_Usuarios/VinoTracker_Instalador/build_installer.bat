@echo off
chcp 65001 >nul
title Vino Tracker - Compilar Instalador

echo.
echo ========================================
echo       VINO TRACKER - COMPILADOR
echo ========================================
echo.

REM Verificar si NSIS está instalado
where makensis >nul 2>&1
if errorlevel 1 (
    echo NSIS no esta instalado.
    echo.
    echo Descarga NSIS desde:
    echo https://nsis.sourceforge.io/Download
    echo.
    echo Instala NSIS y vuelve a ejecutar este script.
    echo.
    pause
    exit /b 1
)

echo Compilando instalador...
echo.

makensis instalador.nsi

if errorlevel 1 (
    echo.
    echo Error al compilar el instalador.
    pause
    exit /b 1
)

echo.
echo ========================================
echo       INSTALADOR COMPILADO
echo ========================================
echo.
echo El instalador se encuentra en:
echo %~dp0VinoTracker_Setup.exe
echo.
echo Puedes distribuir este archivo para instalar
echo Vino Tracker en cualquier ordenador.
echo.
pause
