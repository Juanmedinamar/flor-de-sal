import PyInstaller.__main__
import os
import sys

# Configuración del ejecutable
app_name = "VinoTracker"
app_script = "app.py"
icon_path = os.path.join("assets", "vino_tracker_icon.ico")

# Argumentos de PyInstaller
args = [
    app_script,
    f"--name={app_name}",
    "--onefile",
    "--windowed",
    f"--icon={icon_path}",
    "--add-data=assets;assets",
    "--add-data=data;data",
    "--hidden-import=streamlit",
    "--hidden-import=pandas",
    "--hidden-import=requests",
    "--hidden-import=bs4",
    "--hidden-import=playwright",
    "--hidden-import=scrapers",
    "--hidden-import=scrapers.carrefour",
    "--hidden-import=scrapers.alcampo",
    "--hidden-import=scrapers.bodeboca",
    "--hidden-import=scrapers.hermanos_martin",
    "--hidden-import=scrapers.corte_ingles",
    "--hidden-import=scrapers.hipercor",
    "--hidden-import=scrapers.makro",
    "--hidden-import=scrapers.mercadona",
    "--hidden-import=scrapers.decantalo",
    "--hidden-import=scrapers.grauonline",
    "--hidden-import=scrapers.vinoseleccion",
    "--hidden-import=scrapers.common",
    "--collect-all=playwright",
    "--collect-all=streamlit",
]

# Ejecutar PyInstaller
PyInstaller.__main__.run(args)
