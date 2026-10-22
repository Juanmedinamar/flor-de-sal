"""Estado y caché de la UI: base de datos, calibración y resultados cacheados.

Solo estado: nada visible aquí. Los valores de calibración viven en
`session_state` (inicializados antes de instanciar sus widgets) y los cálculos
caros (Monte Carlo del día y `season_runs`) en `st.cache_data` con ttl=5 min.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from app.ui.constantes import _CFG0, CALIB
from app.ui.helpers import _hhmm_decimal, _tabla_desde_sim
from src import assimilation, montecarlo, physics
from src.config import DB_PATH, Config, load_config
from src.db import Database
from src.pipeline import run_daily

RAIZ = Path(__file__).resolve().parents[2]   # raíz del proyecto

# Ruta de la base de datos: data/flor_desal.db salvo que se indique lo contrario
# (variable opcional, pensada para pruebas: no toca la DB real del proyecto).
DB_RUTA: str = str(os.environ.get("FLOR_DESAL_DB") or DB_PATH)


def _db() -> Database:
    """Conexión a la base de datos local (una por operación, sin estado)."""
    return Database(DB_RUTA)


# ------------------------------------------------------------- calibración
def _valor_defecto(spec: dict):
    """Valor por defecto (config.yaml) del parámetro de calibración `spec`."""
    return getattr(getattr(_CFG0, spec["sec"]), spec["attr"])


def _inicializar_calibracion() -> None:
    """Copia los valores por defecto (o el reset pendiente) a session_state.

    Se ejecuta SIEMPRE antes de instanciar los widgets del panel de calibración
    (Streamlit no deja modificar la clave de un widget ya instanciado).
    """
    if st.session_state.pop("reset_calibracion", False):
        for spec in CALIB:
            st.session_state[f"calib_{spec['key']}"] = _valor_defecto(spec)
        st.session_state["aviso"] = ("ok", "Calibración restablecida a los valores de config.yaml.")
    for spec in CALIB:
        st.session_state.setdefault(f"calib_{spec['key']}", _valor_defecto(spec))


def _valores_calibracion() -> tuple:
    """Tuple (hashable) con los valores actuales del panel → clave de caché."""
    return tuple(st.session_state[f"calib_{spec['key']}"] for spec in CALIB)


def _cfg_calibrado(valores: dict) -> Config:
    """Config fresco (config.yaml) con los overrides de la UI aplicados."""
    cfg = load_config()
    for spec in CALIB:
        setattr(getattr(cfg, spec["sec"]), spec["attr"], valores[spec["key"]])
    return cfg


# --------------------------------------------------------- caché del día (Hoy)
@st.cache_data(ttl=300, show_spinner="Calculando el veredicto (Monte Carlo)…")
def _calcular(fecha: str, n_lecturas: int, calibracion: tuple,
              rev: int, db_ruta: str = DB_RUTA) -> dict:
    """Veredicto + campana + tabla horaria del día (cacheados 5 min).

    La clave incluye nº de lecturas (nueva lectura → recálculo con sesgo),
    parámetros de calibración (cambio → recálculo) y un contador `rev` que se
    incrementa al descargar previsión o guardar lecturas. NO incluye la hora
    del sistema: los 5 min de ttl bastan para refrescar la fase a mitad de día
    sin invalidar la campana entera cada hora.
    """
    cfg = _cfg_calibrado(dict(zip([s["key"] for s in CALIB], calibracion, strict=False)))
    db = Database(db_ruta)
    veredicto = run_daily(db, fecha, cfg=cfg)
    datos: dict = {"veredicto": veredicto, "tabla": None, "forecast": None,
                   "hist_hours": np.array([]), "hist_probs": np.array([])}

    prev = db.get_forecast(fecha)
    if prev is None or prev.empty:
        return datos

    bias = veredicto.get("bias") or {}
    ajuste = assimilation.apply_bias(prev, bias) if bias else prev
    datos["forecast"] = ajuste   # previsión horaria (con sesgo si hay lecturas)

    # Misma simulación que el pipeline (misma semilla) para la campana de prob.
    r = montecarlo.simulate_day(ajuste, cfg)
    datos["hist_hours"] = r.hist_hours
    datos["hist_probs"] = r.hist_probs

    # Tabla horaria: modelo hora a hora solo sobre las horas simuladas (06-21),
    # igual que hace el Monte Carlo, para que fase y concentración coincidan.
    h0, h1 = int(cfg.simulation.hora_inicio), int(cfg.simulation.hora_fin)
    base = ajuste[(ajuste["hour"] >= h0) & (ajuste["hour"] <= h1)].sort_values("hour")
    datos["tabla"] = _tabla_desde_sim(physics.concentrations_over_day(base, cfg))
    return datos


# ------------------------------------------------------------ datos de temporada
def _rango_temporada() -> tuple[str, str]:
    """(inicio, fin) de la temporada de config.yaml (sección `season`)."""
    return str(_CFG0.season.start_date), str(_CFG0.season.end_date)


def _rev_temporada() -> int:
    """Contador que invalida la caché de `season_runs` tras una re-simulación."""
    return int(st.session_state.get("rev_temporada", 0))


@st.cache_data(ttl=300, show_spinner=False)
def _cargar_temporada(start: str, end: str, rev: int,
                      db_ruta: str = DB_RUTA) -> pd.DataFrame:
    """season_runs del rango [start, end] (cacheado 5 min; `rev` lo invalida)."""
    return Database(db_ruta).get_season_runs(start, end)


def _ejecutar_simulacion_temporada() -> None:
    """Ejecuta `scripts/season_simulation.py` (≈15 s) y refresca la caché."""
    cmd = [sys.executable, str(RAIZ / "scripts" / "season_simulation.py")]
    try:
        with st.spinner("Simulando la temporada con meteorología observada (ERA5)…"):
            r = subprocess.run(cmd, check=False, cwd=str(RAIZ), capture_output=True,
                               text=True, timeout=600, encoding="utf-8",
                               errors="replace")
    except Exception as exc:  # timeout, permisos, intérprete no encontrado…
        st.session_state["aviso"] = ("err", f"No se pudo ejecutar la simulación: {exc}")
        st.rerun()
        return

    salida = (r.stdout or "") + (f"\n{r.stderr}" if r.stderr else "")
    st.session_state["salida_temporada"] = salida.strip()
    st.session_state["rev_temporada"] = _rev_temporada() + 1
    if r.returncode == 0:
        resumen = next((ln for ln in salida.splitlines() if ln.startswith("Días simulados")),
                       "temporada guardada en la tabla season_runs")
        st.session_state["aviso"] = ("ok", f"✅ Temporada simulada: {resumen}.")
    else:
        st.session_state["aviso"] = ("err",
                                     (f"La simulación falló (código {r.returncode}): "
                                      f"{salida.strip()[-400:]}"))
    st.cache_data.clear()   # season_runs + veredicto del día, todo a cero
    st.rerun()


def _preparar_temporada(df: pd.DataFrame) -> pd.DataFrame:
    """Columnas derivadas para todos los gráficos de la pestaña Temporada.

    Añade: fecha (datetime), mes/día del calendario, `hora_dec` (hora óptima en
    decimal), `ini_dec`/`fin_dec` (ventana en decimal) y la marca booleana
    `ventana` (¿ese día abrió ventana de cosecha?).
    """
    out = df.copy()
    out["fecha"] = pd.to_datetime(out["date"], errors="coerce")
    out["mes"] = out["fecha"].dt.month.astype("Int64")
    out["dia"] = out["fecha"].dt.day.astype("Int64")
    out["hora_dec"] = pd.to_numeric(out["hora_optima"].map(_hhmm_decimal),
                                    errors="coerce").astype(float)
    out["ini_dec"] = pd.to_numeric(out["window_start"].map(_hhmm_decimal),
                                   errors="coerce").astype(float)
    out["fin_dec"] = pd.to_numeric(out["window_end"].map(_hhmm_decimal),
                                   errors="coerce").astype(float)
    out["prob_ventana"] = pd.to_numeric(out["prob_ventana"], errors="coerce").fillna(0.0)
    out["prob_riesgo"] = pd.to_numeric(out["prob_riesgo"], errors="coerce").fillna(0.0)
    out["ventana"] = out["hora_dec"].notna()
    return out
