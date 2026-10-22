"""Textos compartidos de la UI (español).

La app es solo español (sin i18n), pero los textos que se pintan en más de un
sitio (o textos largos de una sola responsabilidad, como el pie) viven aquí para
que cambiarlos sea un cambio único.
"""
from __future__ import annotations

from app.ui.constantes import _CFG0

# Menú lateral: el bloque de leyenda se pinta igual en «Hoy» y en «Temporada».
SEMAFORO_FASES = "**Semáforo de fases**"

# Sección Temporada: avisos repetidos en varios gráficos.
SIN_DIAS_CON_VENTANA = "Sin días con ventana en la temporada."

# Cabecera de la app (título de la pestaña: ver streamlit_app.py).
TITULO_APP = "🧂 Flor de Sal — Hora óptima de recolección"
SUBTITULO_SIDEBAR = "Predicción probabilística de la ventana de cosecha"

# Pie de fuentes (se pinta al final de ambas secciones).
PIE_FUENTE = (
    "**Fuente del modelo:** «Modelo flor de sal.pdf» (Ley de Dalton modificada, "
    "umbral de sobresaturación y fases 0–3) · **Previsión:** Open-Meteo (sin API key) "
    "· **Simulación:** Monte Carlo con corrección por sesgo sobre datos de campo."
)
PIE_AVISO = (
    "⚠️ La predicción es una **estimación probabilística**, no una garantía: las "
    "condiciones reales de la salina prevalecen siempre. Los coeficientes del "
    "modelo (Dalton a/b, sigmas, umbral, lámina y minutos de crecimiento) se "
    "calibran con datos reales mediante el panel de calibración y la corrección "
    "por sesgo, por lo que la predicción mejora a medida que registras lecturas."
)


def texto_coordenadas() -> str:
    """«Salina Córdoba · 37.8882, -4.7794» (base de los captions de ubicación)."""
    loc = _CFG0.location
    return f"{loc.name} · {loc.latitude}, {loc.longitude}"


def texto_ubicacion(sufijo: str) -> str:
    """Coordenadas + un sufijo contextual («día …», «temporada …», «tz …»)."""
    return f"{texto_coordenadas()} · {sufijo}"
