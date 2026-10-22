"""Helpers generales de la UI: formatos, estilos de tabla, gráficos y zona horaria.

Aquí vive lo que usan dos o más paneles y no depende de `session_state`
(eso está en `app/ui/state.py`).
"""
from __future__ import annotations

import re
from datetime import date, datetime, tzinfo
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.ui.constantes import (
    _CFG0,
    BADGE_FASE,
    FONDO_FASE,
    NOMBRE_FASE,
    PLOTLY_CONFIG,
)
from src.pipeline import _hhmm


# --------------------------------------------------------------- zona horaria
def zona_config() -> tzinfo | None:
    """Zona horaria de `config.yaml` (`location.timezone`); None si no es válida.

    Fallback a la hora local del sistema si la zona no existe en este equipo,
    para que la UI nunca falle por la tz.
    """
    nombre = str(_CFG0.location.timezone or "")
    if not nombre:
        return None
    try:
        return ZoneInfo(nombre)
    except Exception:  # zona desconocida / base tzdata ausente → local
        return None


def ahora() -> datetime:
    """Fecha y hora actuales en la zona de `config.yaml` (fallback: local)."""
    tz = zona_config()
    return datetime.now(tz) if tz else datetime.now()


def hoy() -> date:
    """Fecha de hoy en la zona de `config.yaml` (fallback: local)."""
    return ahora().date()


# ------------------------------------------------------------- helpers generales
def _hhmm_decimal(hhmm: str | None) -> float | None:
    """'17:45' → 17.75 (para los ejes y líneas verticales de plotly)."""
    if not hhmm:
        return None
    try:
        h, m = str(hhmm).split(":")
        return int(h) + int(m) / 60.0
    except (ValueError, AttributeError):
        return None


def _texto_bias(bias: dict | None) -> str:
    """«temperatura +1,8 °C, HR −6 %, viento +0,4 m/s» (vacío si no hay sesgo)."""
    bias = bias or {}
    partes = []
    if bias.get("temp_c") is not None:
        partes.append(f"temperatura {bias['temp_c']:+.1f} °C")
    if bias.get("rh_pct") is not None:
        partes.append(f"HR {bias['rh_pct']:+.0f} %")
    if bias.get("wind_ms") is not None:
        partes.append(f"viento {bias['wind_ms']:+.1f} m/s")
    return ", ".join(partes)


def _css_fase(valor) -> str:
    """Estilo de badge por fase para Styler.map (columna 'Fase')."""
    m = re.search(r"(\d)", str(valor))
    n = int(m.group(1)) if m else -1
    fondo = FONDO_FASE.get(n, "#FFFFFF")
    return f"background-color: {fondo}; font-weight: 600;"


def _estilizar(tabla: pd.DataFrame):
    """Tabla con la columna 'Fase' pintada (fallback: tabla sin estilo)."""
    try:
        return tabla.style.map(_css_fase, subset=["Fase"])
    except Exception:  # pandas sin Styler.map u otro fallo cosmético
        return tabla


def _tabla_desde_sim(sim: pd.DataFrame) -> pd.DataFrame:
    """DataFrame mostrable (hora HH:MM, meteo, T agua, evaporación, C y fase)."""
    def _fase_txt(f) -> str:
        n = int(f)
        return f"{BADGE_FASE.get(n, '⚪')} {n} · {NOMBRE_FASE.get(n, '—')}"

    return pd.DataFrame({
        "Hora": [_hhmm(float(h)) for h in sim["hour"]],
        "T aire °C": sim["temp_c"].astype(float).round(1),
        "HR %": sim["rh_pct"].astype(float).round(0),
        "Viento m/s": sim["wind_ms"].astype(float).round(1),
        "T agua °C": sim["t_water_c"].astype(float).round(1),
        "Evap. mm/h": sim["evap_mm_h"].astype(float).round(3),
        "Concentración g/l": (sim["c_g_l"].astype(float)
                              .where(np.isfinite(sim["c_g_l"].astype(float))).round(1)),
        "Fase": [_fase_txt(f) for f in sim["fase"]],
    })


def _ejes_horas(fig: go.Figure, titulo_y: str = "", rango_y: list | None = None) -> None:
    """Ejes con horas en HH:MM (X) y rejilla suave (común a los gráficos de temporada)."""
    ticks = list(range(6, 22, 2))
    fig.update_xaxes(tickvals=ticks, ticktext=[f"{t:02d}:00" for t in ticks],
                     gridcolor="#E0E0E0", zeroline=False)
    ejey: dict = {"title": titulo_y, "gridcolor": "#E0E0E0", "zeroline": False}
    if rango_y:
        ejey["range"] = rango_y
    fig.update_yaxes(**ejey)


def _mostrar_grafico(fig: go.Figure) -> None:
    """`st.plotly_chart` estándar de la app (ancho completo, sin barra de herramientas)."""
    st.plotly_chart(fig, width="stretch", theme="streamlit", config=PLOTLY_CONFIG)
