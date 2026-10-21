"""Pipeline diario: orquesta ingesta → asimilación → Monte Carlo → veredicto.

    run_daily(db, date)            # usa la previsión (la descarga si no existe)
    recalc_with_field_data(db, date)  # recalcula con las lecturas reales del día

Notas:
    - Un SOLO ensemble por día (auditoría G8): el Monte Carlo y la curva de
      Márkov se derivan del mismo EnsembleResult (montecarlo.simulate_ensemble
      → simulate_day_desde_ensemble + markov.curva_markov_desde_ensemble).
    - Los tiempos del veredicto (hora_veredicto, computed_at y la hora usada
      para la fase actual) se expresan en la zona horaria de la salina
      (cfg.location.timezone, p.ej. Europa/Madrid), no en la del servidor
      (auditoría M9); si la tz no está disponible, se usa la hora local.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

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
    # Un único n_iter para MC y Márkov (auditoría M4: coherencia por construcción).
    if n_iter is None:
        n_iter = int(cfg.montecarlo.iterations)
    forecast = _ensure_forecast(db, date, cfg)
    readings = db.get_readings(date)
    bias = (assimilation.compute_bias(
        forecast, readings,
        max_hours_back=int(cfg.assimilation.max_hours_back))
        if len(readings) else {})
    ajuste = assimilation.apply_bias(forecast, bias) if bias else forecast

    # Un SOLO ensemble por día (auditoría G8): antes el pipeline ejecutaba el
    # Monte Carlo dos veces (simulate_day + curva_markov, que llama a
    # simulate_ensemble internamente con los mismos argumentos). Ahora ambas
    # capas se derivan del mismo EnsembleResult (mismo seed → mismos números).
    ens = montecarlo.simulate_ensemble(ajuste, cfg, n_iter=n_iter,
                                       seed=cfg.montecarlo.seed)
    r = montecarlo.simulate_day_desde_ensemble(ens)

    # Curva de estados de Márkov (semáforo probabilístico hora a hora),
    # coherente con la misma semántica y el mismo ensemble del veredicto.
    curva = markov.curva_markov_desde_ensemble(ens, cfg)
    estados = [{k: (round(float(v), 4) if isinstance(v, float) else int(v))
                for k, v in fila.items()}
               for fila in curva.to_dict("records")]

    # Tiempos del veredicto en la zona horaria de la SALINA (auditoría M9).
    ahora = _ahora_salina(cfg)
    hora_actual = ahora.strftime("%H:%M")
    fase_actual, fase_txt = _fase_actual(ajuste, cfg, readings, ahora.hour)
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
        "computed_at": ahora.isoformat(timespec="seconds"),
        "hora_veredicto": hora_actual,
    }
    db.save_prediction(date, veredicto["computed_at"], veredicto)
    return veredicto


def recalc_with_field_data(db: Database, date: str, cfg: Config | None = None,
                           n_iter: int | None = None) -> dict:
    """Recalcula el veredicto priorizando las lecturas reales del día (bias)."""
    return run_daily(db, date, cfg=cfg, n_iter=n_iter)


# ---------------------------------------------------------------- helpers

def _ahora_salina(cfg: Config) -> datetime:
    """Hora actual en la zona horaria de la salina (cfg.location.timezone).

    Auditoría M9: el veredicto debe "pensar" en la hora local de la salina
    (p.ej. Europa/Madrid), no en la del servidor. Si la tz no está disponible
    (nombre inválido o sin tzdata en el sistema), se cae a la hora local.
    """
    try:
        tz = ZoneInfo(str(cfg.location.timezone))
    except (KeyError, ValueError):   # tz inexistente / mal formada / sin tzdata
        return datetime.now()
    return datetime.now(tz)


def _hhmm(x: float | None) -> str | None:
    """Decimal horario → 'HH:MM' (17.25 → '17:15'); NaN → None."""
    import math
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    h = int(x)
    m = round((x - h) * 60)
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


def _fase_actual(forecast, cfg: Config, readings,
                 hora_veredicto: int) -> tuple[int, str]:
    """Fase del momento según el modelo del día (o lecturas recientes).

    `hora_veredicto` es la hora (0-23) en la zona horaria de la SALINA
    (auditoría M9): la fila de fase que se muestra es la de la salina, no la
    del servidor.
    """
    from src import physics
    sim = physics.concentrations_over_day(forecast, cfg)
    fila = sim[sim["hour"] <= hora_veredicto]
    fila = fila.iloc[-1] if len(fila) else sim.iloc[-1]
    fase = int(fila["fase"])
    return fase, descripcion_fase(fase)
