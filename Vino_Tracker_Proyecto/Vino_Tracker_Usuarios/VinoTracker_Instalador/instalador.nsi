; Instalador NSIS para Vino Tracker
!include "MUI2.nsh"

; Nombre del instalador
Name "Vino Tracker"
OutFile "VinoTracker_Setup.exe"
InstallDir "$PROGRAMFILES\VinoTracker"
RequestExecutionLevel admin

; Interfaz
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; Idiomas
!insertmacro MUI_LANGUAGE "Spanish"

; Sección de instalación
Section "Vino Tracker" SecVinoTracker

    ; Crear directorio de instalación
    SetOutPath "$INSTDIR"
    
    ; Copiar todos los archivos
    File /r "app.py"
    File /r "database.py"
    File /r "productos.py"
    File /r "actualizar_todo.py"
    File /r "requirements.txt"
    File /r "scrapers"
    File /r "assets"
    File /r "data"
    File /r ".streamlit"
    
    ; Crear acceso directo en el escritorio
    CreateDirectory "$SMPROGRAMS\Vino Tracker"
    CreateShortCut "$SMPROGRAMS\Vino Tracker\Vino Tracker.lnk" "$INSTDIR\VinoTracker.bat" "" "$INSTDIR\assets\vino_tracker_icon.ico"
    CreateShortCut "$DESKTOP\Vino Tracker.lnk" "$INSTDIR\VinoTracker.bat" "" "$INSTDIR\assets\vino_tracker_icon.ico"
    
    ; Crear acceso directo en el menú inicio
    CreateShortCut "$SMPROGRAMS\Vino Tracker\Desinstalar.lnk" "$INSTDIR\uninstall.exe"
    
    ; Escribir información del desinstalador
    WriteUninstaller "$INSTDIR\uninstall.exe"
    
    ; Escribir información en el registro
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\VinoTracker" "DisplayName" "Vino Tracker"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\VinoTracker" "UninstallString" "$INSTDIR\uninstall.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\VinoTracker" "InstallLocation" "$INSTDIR"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\VinoTracker" "DisplayIcon" "$INSTDIR\assets\vino_tracker_icon.ico"

SectionEnd

; Sección de desinstalación
Section "Uninstall"

    ; Eliminar archivos
    Delete "$INSTDIR\app.py"
    Delete "$INSTDIR\database.py"
    Delete "$INSTDIR\productos.py"
    Delete "$INSTDIR\actualizar_todo.py"
    Delete "$INSTDIR\requirements.txt"
    Delete "$INSTDIR\VinoTracker.bat"
    RMDir /r "$INSTDIR\scrapers"
    RMDir /r "$INSTDIR\assets"
    RMDir /r "$INSTDIR\data"
    RMDir /r "$INSTDIR\.streamlit"
    
    ; Eliminar accesos directos
    Delete "$SMPROGRAMS\Vino Tracker\Vino Tracker.lnk"
    Delete "$SMPROGRAMS\Vino Tracker\Desinstalar.lnk"
    RMDir "$SMPROGRAMS\Vino Tracker"
    Delete "$DESKTOP\Vino Tracker.lnk"
    
    ; Eliminar directorio de instalación
    RMDir "$INSTDIR"
    
    ; Eliminar información del registro
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\VinoTracker"

SectionEnd
