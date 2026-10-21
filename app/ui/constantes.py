"""Constantes de la UI: marca, colores, estados, espec de calibración y datos fijos.

Todo lo que comparten dos o más paneles y no cambia durante la sesión vive aquí
(o en `app/ui/textos.py`, si es texto visible). `_CFG0` es la configuración del
proyecto (`config.yaml`) cargada una sola vez al importar.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.config import load_config

# Logo de la salina (app/assets/logo.png): favicon de la pestaña y cabecera.
# Si no existe, se usa el emoji 🧂 como marca de agua (no debe romper el arranque).
LOGO_PATH = Path(__file__).resolve().parents[1] / "assets" / "logo.png"
try:
    LOGO_BYTES = LOGO_PATH.read_bytes() if LOGO_PATH.exists() else None
except OSError:
    LOGO_BYTES = None

# ------------------------------------------------------------------ colores
TEAL = "#00695C"          # color primario (.streamlit/config.toml)
ROJO = "#C62828"
COLORES_FASE: dict[int, str] = {0: "#9E9E9E", 1: "#EF6C00", 2: TEAL, 3: ROJO}
BADGE_FASE: dict[int, str] = {0: "⬜", 1: "🟧", 2: "🟩", 3: "🟥"}
NOMBRE_FASE: dict[int, str] = {
    0: "Inactividad",
    1: "Nucleación",
    2: "Ventana óptima",
    3: "Cierre/riesgo",
}
FONDO_FASE: dict[int, str] = {0: "#EEEEEE", 1: "#FFE0B2", 2: "#C8E6C9", 3: "#FFCDD2"}

# Estados de la capa de Márkov (AGENTS.md): (columna del veredicto, nombre, color).
# El orden del gráfico apilado es de abajo arriba: inactivo → … → degradación.
ESTADOS_MARKOV: list[tuple[str, str, str]] = [
    ("P_inactivo", "Inactivo", "#9E9E9E"),
    ("P_concentracion_critica", "Concentración crítica", "#FFC107"),
    ("P_nucleacion", "Nucleación", "#FF9800"),
    ("P_ventana", "Ventana", "#2E7D32"),
    ("P_degradacion", "Degradación", "#C62828"),
]

MESES: list[str] = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
MESES_CORTO: list[str] = ["ene", "feb", "mar", "abr", "may", "jun",
                          "jul", "ago", "sep", "oct", "nov", "dic"]
GRIS_CELDA = "#EEEEEE"      # celdas del calendario sin ventana / no simuladas

_CFG0 = load_config()

# --------------------------------------------------------------- plotly fijo
# Configuración y layout por defecto de TODOS los gráficos de la app (M6):
# sin barra de herramientas y con fondo transparente sobre el tema de Streamlit.
PLOTLY_CONFIG: dict = {"displayModeBar": False}
LAYOUT_BASE: dict = {
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "font": {"color": "#212121"},
}

# Especificación del panel de calibración:
#   key → clave de widget, sec → sección del Config, attr → atributo de esa sección
CALIB: list[dict] = [
    {"key": "dalton_a", "sec": "physics", "attr": "dalton_a",
     "label": "Dalton · a (mm/día por kPa)", "min": 0.1, "max": 1.5, "step": 0.01,
     "fmt": "%.2f",
     "ayuda": "Evaporación con viento cero. Literatura para lámina libre: 0,17; "
              "la lámina somera del cristalizador evapora más."},
    {"key": "dalton_b", "sec": "physics", "attr": "dalton_b",
     "label": "Dalton · b (mm/día por kPa·m/s)", "min": 0.5, "max": 5.0, "step": 0.01,
     "fmt": "%.2f",
     "ayuda": "Aumento de evaporación por cada m/s de viento. Literatura: 0,87."},
    {"key": "sigma_temp", "sec": "montecarlo", "attr": "sigma_temp_c",
     "label": "σ temperatura (°C)", "min": 0.1, "max": 5.0, "step": 0.1, "fmt": "%.1f",
     "ayuda": "Incertidumbre de la previsión de temperatura en el Monte Carlo."},
    {"key": "sigma_rh", "sec": "montecarlo", "attr": "sigma_rh_pct",
     "label": "σ HR (%)", "min": 1.0, "max": 20.0, "step": 0.5, "fmt": "%.1f",
     "ayuda": "Incertidumbre de la humedad relativa: más σ → campana más ancha."},
    {"key": "sigma_wind", "sec": "montecarlo", "attr": "sigma_wind_ms",
     "label": "σ viento (m/s)", "min": 0.05, "max": 3.0, "step": 0.05, "fmt": "%.2f",
     "ayuda": "Incertidumbre del viento previsto."},
    {"key": "umbral", "sec": "water", "attr": "umbral_sobresaturacion_g_l",
     "label": "Umbral de sobresaturación (g/l)", "min": 300.0, "max": 340.0,
     "step": 1.0, "fmt": "%.0f",
     "ayuda": "Concentración a la que empieza la nucleación (rango del PDF: 315-320)."},
    {"key": "profundidad", "sec": "water", "attr": "profundidad_lamina_cm",
     "label": "Profundidad de lámina (cm)", "min": 5.0, "max": 10.0, "step": 0.5,
     "fmt": "%.1f",
     "ayuda": "Tiraje del cristalizador: lámina más fina concentra antes."},
    {"key": "crecimiento", "sec": "simulation", "attr": "minutos_crecimiento",
     "label": "Minutos de crecimiento (min)", "min": 30, "max": 240, "step": 15,
     "fmt": "%d",
     "ayuda": "Tiempo que la película crece tras la nucleación antes de ser "
              "cosechable (por defecto 120 min)."},
]

COLUMNAS_LECTURAS = {
    "reading_time": "Hora",
    "t_calentador_c": "T calentador °C",
    "t_cristalizador_c": "T cristalizador °C",
    "concentration_g_l": "Concentración g/l",
    "t_ambiente_c": "T ambiente °C",
    "rh_pct": "HR %",
    "wind_ms": "Viento m/s",
    "notes": "Notas",
}

CONFIG_TABLA = {
    "T aire °C": st.column_config.NumberColumn("T aire °C", format="%.1f"),
    "HR %": st.column_config.NumberColumn("HR %", format="%.0f"),
    "Viento m/s": st.column_config.NumberColumn("Viento m/s", format="%.1f"),
    "T agua °C": st.column_config.NumberColumn("T agua °C", format="%.1f"),
    "Evap. mm/h": st.column_config.NumberColumn("Evap. mm/h", format="%.3f"),
    "Concentración g/l": st.column_config.NumberColumn("Concentración g/l", format="%.1f"),
    "Fase": st.column_config.TextColumn("Fase", width="medium"),
}
