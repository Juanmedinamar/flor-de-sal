"""App Streamlit — Flor de Sal (punto de entrada delgado).

App con DOS secciones (radio en el menú lateral): **🌞 Hoy** y **📆 Temporada**.

🌞 HOY — el veredicto del día que produce `pipeline.run_daily` (previsión
Open-Meteo + datos de campo + Monte Carlo):

  1. Selector de fecha y botón de descarga de previsión (sidebar).
  2. Panel de veredicto: semáforo de fase (0 gris · 1 naranja · 2 verde · 3 rojo),
     ventana más probable, hora óptima con IC95, probabilidad de ventana y de
     riesgo (st.progress) y alertas por nivel.
  3. Semáforo probabilístico (Márkov): áreas apiladas hora a hora con los 5
     estados y línea vertical «ahora».
  4. Campana de probabilidad de la hora óptima (plotly, con sombreado del IC95 y
     línea en la mediana) + tabla horaria del día con badge de color por fase.
  5. Previsión vs lecturas reales (T, HR y V) con el sesgo aplicado.
  6. Evolución de la predicción del día (hora óptima + IC95 por cálculo).
  7. Formulario "Datos reales de campo" → db.save_reading y recálculo con
     corrección por sesgo; debajo, las lecturas del día y el bias aplicado.
  8. Panel de calibración (expander) con los parámetros del modelo y botón de
     restablecer.

📆 TEMPORADA — la simulación histórica de `scripts/season_simulation.py`
(tabla `season_runs`): KPIs, mapa de calor calendario, serie diaria de
probabilidad, distribución de horas óptimas + cobertura por hora, box plot por
mes, barras mensuales y Top-10 de días, con botón de (re)simulación.

El código de los paneles vive en el paquete `app/ui/` (constantes, textos,
helpers, estado/caché, sidebar y los dos paneles de sección). Este fichero solo
prepara el path, configura la página y llama a `main()`.

Uso:  python3 -m streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from app.ui.constantes import LOGO_BYTES

st.set_page_config(page_title="Flor de Sal — Hora óptima de recolección",
                   page_icon=LOGO_BYTES if LOGO_BYTES else "🧂", layout="wide")

from app.ui.main import main  # noqa: E402

main()
