"""Pipeline diario: orquesta ingesta → asimilación → Monte Carlo → veredicto.

    run_daily(db, date)            # usa la previsión (la descarga si no existe)
    recalc_with_field_data(db, date)  # recalcula con las lecturas reales del día
"""
from __future__ import annotations

from datetime import datetime

from src import assimilation, markov, montecarlo, weather
from src.alerts import descripcion_fase, evaluar_riesgos
from src.config import Config, load_config
from src.db import Database


def _ensure_forecast(db: Database, date: str, cfg: Config):
    """Devuelve la previsión del día; si no está en la DB, la descarga y la guarda."""
    df = db.get_forecast(date)
    if df is None or df.empty:
        df = weather.fetch_forecast(cfg.location.latitude, cfg.location.longitude,
                                    date, cfg.location.timezone)
        db.save_forecast(date, df)
    return df


def run_daily(db: Database, date: str, cfg: Config | None = None,
              n_iter: int | None = None) -> dict:
    """Veredicto del día: descarga previsión (si falta), simula y guarda el resultado.

    Si ya hay lecturas de campo para el día, se aplica la corrección por sesgo
    (bias) antes de simular. Devuelve el veredicto (ver docstring del módulo y
    AGENTS.md) y lo persiste con db.save_prediction.
    """
    cfg = cfg or load_config()
    forecast = _ensure_forecast(db, date, cfg)
    readings = db.get_readings(date)
    bias = assimilation.compute_bias(forecast, readings) if len(readings) else {}
    ajuste = assimilation.apply_bias(forecast, bias) if bias else forecast
    r = montecarlo.simulate_day(ajuste, cfg, n_iter=n_iter)

    # Curva de estados de Márkov (semáforo probabilístico hora a hora), coherente
    # con la misma semántica y semilla del Monte Carlo del veredicto.
    curva = markov.curva_markov(ajuste, cfg, n_iter=n_iter,
                                seed=cfg.montecarlo.seed)
    estados = [{k: (round(float(v), 4) if isinstance(v, float) else int(v))
                for k, v in fila.items()}
               for fila in curva.to_dict("records")]

    hora_actual = datetime.now().strftime("%H:%M")
    fase_actual, fase_txt = _fase_actual(ajuste, cfg, readings)
    veredicto = {
        "fecha": date,
        "fase_actual": fase_actual,
        "fase_descripcion": fase_txt,
        "ventana_inicio": _hhmm(r.window_start_median),
        "ventana_fin": _hhmm(r.window_end_median),
        "hora_optima": _hhmm(r.median_hour),
        "hora_optima_ci": [_hhmm(r.ci_low), _hhmm(r.ci_high)],
        "prob_ventana": round(r.prob_ventana, 3),
        "prob_riesgo": round(r.prob_fase3, 3),
        "estados_por_hora": estados,
        "alertas": evaluar_riesgos(*_ultimo_meteo(ajuste, readings), cfg),
        "bias": bias,
        "n_iter": r.n_iter,
        "computed_at": datetime.now().isoformat(timespec="seconds"),
        "hora_veredicto": hora_actual,
    }
    db.save_prediction(date, veredicto["computed_at"], veredicto)
    return veredicto


def recalc_with_field_data(db: Database, date: str, cfg: Config | None = None,
                           n_iter: int | None = None) -> dict:
    """Recalcula el veredicto priorizando las lecturas reales del día (bias)."""
    return run_daily(db, date, cfg=cfg, n_iter=n_iter)


# ---------------------------------------------------------------- helpers

def _hhmm(x: float | None) -> str | None:
    """Decimal horario → 'HH:MM' (17.25 → '17:15'); NaN → None."""
    import math
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    h = int(x)
    m = int(round((x - h) * 60))
    if m == 60:
        h, m = h + 1, 0
    return f"{h:02d}:{m:02d}"


def _ultimo_meteo(forecast, readings) -> tuple[float, float, float]:
    """(T, HR, V) más recientes: lectura real si existe; si no, la previsión."""
    if readings is not None and len(readings):
        ult = readings.dropna(subset=["t_ambiente_c", "rh_pct", "wind_ms"]).tail(1)
        if len(ult):
            f = ult.iloc[0]
            return float(f["t_ambiente_c"]), float(f["rh_pct"]), float(f["wind_ms"])
    f = forecast.iloc[-1]
    return float(f["temp_c"]), float(f["rh_pct"]), float(f["wind_ms"])


def _fase_actual(forecast, cfg: Config, readings) -> tuple[int, str]:
    """Fase del momento según el modelo del día (o lecturas recientes)."""
    from src import physics
    sim = physics.concentrations_over_day(forecast, cfg)
    hora_veredicto = datetime.now().hour
    fila = sim[sim["hour"] <= hora_veredicto]
    fila = fila.iloc[-1] if len(fila) else sim.iloc[-1]
    fase = int(fila["fase"])
    return fase, descripcion_fase(fase)
