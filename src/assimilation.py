"""Asimilación de datos de campo — corrección por sesgo (rolling forecast).

A medida que avanza el día, la previsión matutina se compara con lo medido en la
salina y se calcula el sesgo medio (real − previsto) de las últimas horas. Ese
desplazamiento se aplica a las horas restantes de la previsión antes de la
simulación de Monte Carlo: la predicción se "ancla" a la realidad y la campana
de probabilidad se estrecha.
"""
from __future__ import annotations

import pandas as pd

# Variables con sesgo y su columna equivalente en las lecturas de campo.
_VARS = {"temp_c": "t_ambiente_c", "rh_pct": "rh_pct", "wind_ms": "wind_ms"}


def compute_bias(forecast_df: pd.DataFrame, readings_df: pd.DataFrame,
                 max_hours_back: int = 6) -> dict:
    """Sesgo medio (real − previsto) de las últimas horas con lecturas.

    Cruza por hora (reading_time "HH:MM" → hour). Solo se incluye una variable si
    hay al menos una pareja; se ignoran NaN. Devuelve p.ej.
    {'temp_c': 1.8, 'rh_pct': -6.0, 'wind_ms': 0.4} (posiblemente vacío).
    """
    if readings_df is None or readings_df.empty:
        return {}
    f = forecast_df.set_index(forecast_df["hour"].astype(int))
    r = readings_df.copy()
    r["hour"] = (r["reading_time"].astype(str).str.slice(0, 2).astype(int))
    r = r[r["hour"].isin(f.index)]

    bias: dict = {}
    for var, col in _VARS.items():
        if col not in r.columns:
            continue
        pairs = r[["hour", col]].dropna()
        if pairs.empty:
            continue
        pairs = pairs.sort_values("hour").tail(max_hours_back)
        delta = (pairs[col].astype(float)
                 - f.loc[pairs["hour"], var].astype(float).to_numpy())
        if len(delta):
            bias[var] = float(delta.mean())
    return bias


def apply_bias(forecast_df: pd.DataFrame, bias: dict) -> pd.DataFrame:
    """Copia de la previsión con el sesgo aplicado (HR en [0,100], viento >= 0)."""
    out = forecast_df.copy()
    for var in _VARS:
        if var in bias and pd.notna(bias[var]):
            out[var] = out[var].astype(float) + float(bias[var])
    if "rh_pct" in out:
        out["rh_pct"] = out["rh_pct"].clip(0.0, 100.0)
    if "wind_ms" in out:
        out["wind_ms"] = out["wind_ms"].clip(lower=0.0)
    return out
