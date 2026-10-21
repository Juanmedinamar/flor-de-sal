"""Simulación de Monte Carlo — distribución de probabilidad de la hora óptima.

Recorre el día con el modelo físico (src.physics) n veces muestreando la
incertidumbre de la previsión (T, HR, V con las σ de cfg.montecarlo) y, para cada
escenario, determina la ventana de cosecha:

  - nucleación:  primera hora en que C_sup >= umbral(T_agua)   (Fase 1)
  - apertura:    nucleación + cfg.simulation.minutos_crecimiento/60  (Fase 2)
  - cierre:      primera hora >= apertura con Fase 3 (viento > viento_peligro_ms,
                 o repunte de HR >= hr_cierre_tarde_pct tras el mínimo del día, o
                 HR > hr_peligro_pct); si no se produce, fin de simulación.
  - hora óptima: centro de la ventana (apertura + 0.5·duración) — el tramo final es
                 el más espeso pero el más arriesgado; el centro es el momento
                 representativo más seguro para cosechar.

Implementación vectorizada (NumPy): todos los escenarios se calculan a la vez como
una matriz (n_iter × horas) — <0,1 s para 1000 escenarios. La semántica de fase es
idéntica a src/alerts.evaluar_fase; la ruta escalar de physics.concentrations_over_day
es la referencia y los tests verifican que ambas coinciden.

Capas públicas:
  - simulate_ensemble(...)  → EnsembleResult (matrices crudas por escenario/hora;
                              la usa la capa de Márkov, src/markov.py).
  - simulate_day(...)       → DayResult (veredicto resumido del día).
  - simulate_day_desde_ensemble(ens) → DayResult a partir de un ensemble YA
                               simulado (evita el doble Monte Carlo, auditoría G8).
  - simulate_day_referenciaEscalar(...) → ruta de referencia para tests.

El núcleo (_run_ensemble) está partido en tres funciones puras y testables
(auditoría G2), con la misma semántica numérica (mismo seed → mismo ensemble):
  - _muestrear(...)          → (t_air, rh, wind) con ruido gausiano truncado.
  - _fisica_vectorizada(...) → (c_g_l, umbral) — T_agua, VPD, Dalton, ΣE.
  - _estados_y_ventanas(...) → EnsembleResult (nucleación, fases, ventana).

`prob_fase3` solo cuenta los cierres por condición DURA de riesgo (viento >
viento_peligro_ms o HR > hr_peligro_pct); el cierre natural por repunte de HR de la
tarde no es riesgo y no se cuenta.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src import physics
from src.config import ConfigProto

_BINSIZE_H = 0.25


@dataclass
class DayResult:
    median_hour: float          # hora óptima mediana (decimal; 17.25 = 17:15)
    ci_low: float               # percentil 5
    ci_high: float              # percentil 95
    prob_ventana: float         # fracción de escenarios con ventana de cosecha
    hist_hours: np.ndarray      # centros de bines (0.25 h) de la campana
    hist_probs: np.ndarray      # densidad por bine (el área total integra 1)
    prob_fase3: float           # fracción de escenarios que cierran por RIESGO (Fase 3 dura)
    window_start_median: float  # mediana de la apertura de ventana
    window_end_median: float    # mediana del cierre de ventana
    n_iter: int


@dataclass
class EnsembleResult:
    """Matrices crudas del ensemble (n escenarios × h horas) — insumo de Márkov."""
    hours: np.ndarray      # (h,) horas del día simulado
    c_g_l: np.ndarray      # (n, h) concentración superficial por escenario/hora
    umbral: np.ndarray     # (n, h) umbral de sobresaturación por escenario/hora
    fase: np.ndarray       # (n, h) fase 0-3 (semántica idéntica a alerts.evaluar_fase)
    apertura: np.ndarray   # (n,) hora de apertura de ventana (inf si no hay)
    cierre: np.ndarray     # (n,) hora de cierre (fin de sim si no hubo Fase 3)
    optima: np.ndarray     # (n,) hora óptima (NaN si no hay ventana)
    valid: np.ndarray      # (n,) bool: hubo ventana aprovechable
    riesgo_duro: np.ndarray  # (n,) bool: cerró por condición dura (viento/HR peligro)
    n_iter: int


def _muestrear(base: pd.DataFrame, cfg: ConfigProto, bias: dict,
               n_iter: int, seed: int | None) -> tuple[np.ndarray, np.ndarray,
                                                        np.ndarray]:
    """Muestrea T, HR y V con ruido gausiano truncado (corregido por sesgo si hay).

    Para cada variable: X ~ N(previsto + bias, σ) y truncado físico
    (T en [-20, 60] °C, HR en [5, 99] %, V >= 0 m/s). El orden de los draws
    gausianos (T, HR, V) es fijo para que un mismo seed dé siempre el mismo
    ensemble (reproducibilidad).

    Devuelve (t_air, rh, wind), cada uno un ndarray (n_escenarios, h_horas).
    """
    rng = np.random.default_rng(seed)
    m = cfg.montecarlo
    n_horas = len(base)

    # Muestreo: T, HR y V con ruido gausiano truncado (corrigido por sesgo si hay)
    t_air = (base["temp_c"].to_numpy(float)[None, :]
             + bias.get("temp_c", 0.0)
             + rng.normal(0.0, m.sigma_temp_c, (n_iter, n_horas)))
    rh = (base["rh_pct"].to_numpy(float)[None, :]
          + bias.get("rh_pct", 0.0)
          + rng.normal(0.0, m.sigma_rh_pct, (n_iter, n_horas)))
    wind = (base["wind_ms"].to_numpy(float)[None, :]
            + bias.get("wind_ms", 0.0)
            + rng.normal(0.0, m.sigma_wind_ms, (n_iter, n_horas)))
    t_air = np.clip(t_air, -20.0, 60.0)
    rh = np.clip(rh, 5.0, 99.0)
    wind = np.clip(wind, 0.0, None)
    return t_air, rh, wind


def _fisica_vectorizada(t_air: np.ndarray, rh: np.ndarray, wind: np.ndarray,
                        hours: np.ndarray, rad: np.ndarray, cfg: ConfigProto
                        ) -> tuple[np.ndarray, np.ndarray]:
    """Física vectorizada del día (idéntica a las funciones escalares de physics).

    Por escenario/hora calcula, con las mismas ecuaciones de src/physics.py:
      T_agua = max(T_amb + coef_solar·(rad/1000) + extra_mañana(h), 15)  [°C]
      VPD    = max((Psat(T_agua) − HR/100·Psat(T_amb)) / 10, 0)          [kPa]
      E_hora = (a + b·V) · VPD / 24                                       [mm/h]
      C_t    = C0 / (1 − ΣE/h_mm)     (inf si ΣE >= h; "masa", ver physics)
      umbral = C_umbral_ref + pend·(T_agua − T_ref)                      [g/l]

    Devuelve (c_g_l, umbral), ndarray (n_escenarios, h_horas).
    """
    extra = np.where(hours < 12.0,
                     cfg.physics.t_extra_manana_c
                     * np.clip((12.0 - hours) / (12.0 - float(cfg.simulation.hora_inicio)),
                               0.0, 1.0),
                     0.0)[None, :]
    t_water = np.maximum(t_air + cfg.physics.coef_solar_agua * rad / 1000.0 + extra,
                         15.0)
    vpd = np.maximum((physics.psat_hpa_arr(t_water)
                      - rh / 100.0 * physics.psat_hpa_arr(t_air)) / 10.0, 0.0)
    evap = (cfg.physics.dalton_a + cfg.physics.dalton_b * wind) * vpd / 24.0  # mm/h

    sigma_e = np.cumsum(evap, axis=1)                        # ΣE [mm]
    depth_mm = float(cfg.water.profundidad_lamina_cm) * 10.0
    frac = sigma_e / depth_mm
    c_g_l = np.where(frac < 1.0, float(cfg.water.entrada_cristalizador_g_l) / (1 - frac),
                     np.inf)
    umbral = (float(cfg.water.umbral_sobresaturacion_g_l)
              + float(cfg.water.umbral_pendiente_g_l_c)
              * (t_water - float(cfg.water.umbral_temp_ref_c)))
    return c_g_l, umbral


def _estados_y_ventanas(c_g_l: np.ndarray, umbral: np.ndarray, rh: np.ndarray,
                        wind: np.ndarray, hours: np.ndarray, cfg: ConfigProto
                        ) -> EnsembleResult:
    """Nucleación, fases y ventana de cosecha por escenario (semántica = alerts).

    Reglas (por escenario, idénticas a alerts.evaluar_fase):
      - nucleación:  primera hora con C >= umbral(T_agua)
      - Fase 3 dura: viento > viento_peligro_ms o HR > hr_peligro_pct
      - repunte:     HR >= hr_cierre_tarde_pct y > mínimo del día + 3, tras
                     nucleación + minutos_crecimiento (cierre natural)
      - apertura = nucleación + crecimiento; cierre = primera Fase 3 >= apertura
        (si no, fin de simulación); óptima = centro de la ventana.

    Devuelve el EnsembleResult con las matrices crudas (n escenarios × h horas).
    """
    n_iter = int(c_g_l.shape[0])
    h1 = float(cfg.simulation.hora_fin)

    # Nucleación: primera hora con C >= umbral
    mascara_nuc = c_g_l >= umbral
    tiene_nuc = mascara_nuc.any(axis=1)
    idx_nuc = np.where(tiene_nuc, mascara_nuc.argmax(axis=1), -1)
    hora_nuc = np.where(tiene_nuc, hours[np.maximum(idx_nuc, 0)], np.inf)

    # Fase 3 por hora: condición DURA (viento/HR de peligro) o repunte de HR tras
    # el mínimo acumulado (cierre natural de la ventana por la tarde).
    hr_min_ahora = np.minimum.accumulate(rh, axis=1)
    growth_h = float(cfg.simulation.minutos_crecimiento) / 60.0
    L = cfg.limits
    duro = (wind > L.viento_peligro_ms) | (rh > L.hr_peligro_pct)
    repunte = ((rh >= L.hr_cierre_tarde_pct) & (rh > hr_min_ahora + 3.0)
               & (hours[None, :] >= hora_nuc[:, None] + growth_h))
    fase3 = duro | repunte

    # Fases 0/1/2 (semántica idéntica a alerts.evaluar_fase)
    es_nuc = (c_g_l >= umbral) & ~duro
    post = es_nuc & (hours[None, :] >= hora_nuc[:, None] + growth_h)
    fase = np.zeros(c_g_l.shape, dtype=np.int8)
    fase = np.where(es_nuc & ~post, 1, fase)
    fase = np.where(post & ~repunte, 2, fase)
    fase = np.where(repunte | duro, 3, fase)

    # Cierre de ventana: primera hora >= apertura con Fase 3 (si no, fin de sim)
    apertura = hora_nuc + growth_h
    post_ap = hours[None, :] >= apertura[:, None]
    masc_cierre = fase3 & post_ap & tiene_nuc[:, None]
    tiene_cierre = masc_cierre.any(axis=1)
    idx_cierre = np.where(tiene_cierre, masc_cierre.argmax(axis=1), len(hours) - 1)
    cierre = np.where(tiene_cierre, hours[idx_cierre], h1)

    dur = cierre - apertura
    valid = tiene_nuc & (apertura <= h1) & (dur > 0)
    # apertura puede ser inf (sin nucleación): se enmascara antes de operar
    apertura_seg = np.where(valid, apertura, 0.0)
    optima = np.where(valid, apertura_seg + 0.5 * dur, np.nan)
    riesgo = np.zeros(n_iter, dtype=bool)
    if valid.any():
        riesgo[valid] = duro[valid][np.arange(valid.sum()), idx_cierre[valid]]

    return EnsembleResult(hours=hours, c_g_l=c_g_l, umbral=umbral, fase=fase,
                          apertura=apertura, cierre=cierre, optima=optima,
                          valid=valid, riesgo_duro=riesgo, n_iter=n_iter)


def _run_ensemble(base: pd.DataFrame, cfg: ConfigProto, bias: dict,
                  n_iter: int, seed: int | None) -> EnsembleResult:
    """Núcleo vectorizado: muestrea el día n veces y devuelve matrices crudas.

    Compone las tres fases puras del núcleo (auditoría G2):
    _muestrear → _fisica_vectorizada → _estados_y_ventanas.
    """
    hours = base["hour"].to_numpy(float)
    rad = base["radiation_w_m2"].to_numpy(float)[None, :]
    t_air, rh, wind = _muestrear(base, cfg, bias, n_iter, seed)
    c_g_l, umbral = _fisica_vectorizada(t_air, rh, wind, hours, rad, cfg)
    return _estados_y_ventanas(c_g_l, umbral, rh, wind, hours, cfg)


def simulate_ensemble(forecast_df: pd.DataFrame, cfg: ConfigProto,
                      bias: dict | None = None,
                      n_iter: int | None = None,
                      seed: int | None = None) -> EnsembleResult:
    """Ensemble completo del día (punto de entrada para src/markov.py)."""
    bias = bias or {}
    n_iter = int(n_iter or cfg.montecarlo.iterations)
    seed = cfg.montecarlo.seed if seed is None else seed
    h0, h1 = float(cfg.simulation.hora_inicio), float(cfg.simulation.hora_fin)
    base = (forecast_df[(forecast_df["hour"] >= h0) & (forecast_df["hour"] <= h1)]
            .sort_values("hour").reset_index(drop=True))
    if base.empty:
        vacio = np.zeros((n_iter, 0))
        return EnsembleResult(np.array([]), vacio, vacio, vacio.astype(np.int8),
                              np.array([]), np.array([]), np.array([]),
                              np.zeros(n_iter, bool), np.zeros(n_iter, bool), n_iter)
    return _run_ensemble(base, cfg, bias, n_iter, seed)


def simulate_day(forecast_df: pd.DataFrame, cfg: ConfigProto,
                 bias: dict | None = None,
                 n_iter: int | None = None,
                 seed: int | None = None) -> DayResult:
    """Simula `n_iter` escenarios y devuelve el veredicto resumido del día.

    `bias` desplaza la media de la previsión (corrección por sesgo, ver
    src/assimilation.py). `seed` (default cfg.montecarlo.seed) hace reproducible
    la simulación. El resumen (percentiles 5/50/95, histograma, prob. ventana/
    riesgo) lo hace :func:`simulate_day_desde_ensemble` sobre el ensemble.
    """
    ens = simulate_ensemble(forecast_df, cfg, bias=bias, n_iter=n_iter, seed=seed)
    return simulate_day_desde_ensemble(ens)


def simulate_day_desde_ensemble(ens: EnsembleResult) -> DayResult:
    """Veredicto resumido a partir de un EnsembleResult YA simulado.

    Extrae la parte de simulate_day que resume el ensemble (percentiles,
    histograma, prob. ventana/riesgo), de modo que el pipeline puede obtener el
    DayResult y la curva de Márkov del MISMO ensemble sin repetir el Monte
    Carlo (auditoría G8). Percentiles 5/50/95 sobre las horas óptimas de los
    escenarios con ventana; si ningún escenario tiene ventana, horas en NaN y
    histograma vacío.
    """
    n_iter = ens.n_iter
    if ens.hours.size == 0 or not ens.valid.any():
        prob_fase3 = float(ens.riesgo_duro[ens.valid].mean()) if ens.valid.any() else 0.0
        return DayResult(np.nan, np.nan, np.nan, 0.0, np.array([]), np.array([]),
                         prob_fase3, np.nan, np.nan, n_iter)

    optima = ens.optima[ens.valid]
    p5, p50, p95 = np.percentile(optima, [5, 50, 95])
    h0 = float(ens.hours[0])
    h1 = float(ens.hours[-1])
    bins = np.arange(h0, h1 + _BINSIZE_H, _BINSIZE_H)
    hist, _ = np.histogram(optima, bins=bins, density=True)
    centers = (bins[:-1] + bins[1:]) / 2.0
    return DayResult(
        median_hour=float(p50),
        ci_low=float(p5),
        ci_high=float(p95),
        prob_ventana=float(ens.valid.mean()),
        hist_hours=centers,
        hist_probs=hist,
        prob_fase3=float(ens.riesgo_duro[ens.valid].mean()),
        window_start_median=float(np.median(ens.apertura[ens.valid])),
        window_end_median=float(np.median(ens.cierre[ens.valid])),
        n_iter=n_iter,
    )


def simulate_day_referenciaEscalar(forecast_df: pd.DataFrame, cfg: ConfigProto,
                                   n_iter: int = 200, seed: int | None = None) -> DayResult:
    """Ruta escalar de referencia (usa physics.concentrations_over_day + alerts).

    Existe para los tests: valida que la versión vectorizada sea coherente con la
    implementación de referencia del modelo. No usar en la app (lenta).
    """
    seed = cfg.montecarlo.seed if seed is None else seed
    rng = np.random.default_rng(seed)
    h0, h1 = float(cfg.simulation.hora_inicio), float(cfg.simulation.hora_fin)
    base = (forecast_df[(forecast_df["hour"] >= h0) & (forecast_df["hour"] <= h1)]
            .sort_values("hour").reset_index(drop=True))
    m = cfg.montecarlo
    growth_h = cfg.simulation.minutos_crecimiento / 60.0
    optimas, aperturas, cierres, riesgos = [], [], [], []
    for _ in range(n_iter):
        muestra = base.copy()
        muestra["temp_c"] = np.clip(muestra["temp_c"] + rng.normal(0, m.sigma_temp_c, len(base)), -20, 60)
        muestra["rh_pct"] = np.clip(muestra["rh_pct"] + rng.normal(0, m.sigma_rh_pct, len(base)), 5, 99)
        muestra["wind_ms"] = np.clip(muestra["wind_ms"] + rng.normal(0, m.sigma_wind_ms, len(base)), 0, None)
        sim = physics.concentrations_over_day(muestra, cfg)
        nuc = sim["hora_nucleacion"].dropna()
        if nuc.empty:
            continue
        apertura = float(nuc.iloc[0]) + growth_h
        if apertura > h1:
            continue
        sub = sim[sim["hour"] >= apertura]
        f3 = sub[sub["fase"] == 3]
        if not f3.empty:
            h_c = float(f3["hour"].iloc[0])
            fila = sub[sub["hour"] == h_c].iloc[0]
            duro = (fila["wind_ms"] > cfg.limits.viento_peligro_ms
                    or fila["rh_pct"] > cfg.limits.hr_peligro_pct)
            riesgos.append(bool(duro))
        else:
            h_c = h1
            riesgos.append(False)
        dur = h_c - apertura
        if dur <= 0:
            riesgos.pop()
            continue
        optimas.append(apertura + 0.5 * dur)
        aperturas.append(apertura)
        cierres.append(h_c)
    if not optimas:
        return DayResult(np.nan, np.nan, np.nan, 0.0, np.array([]), np.array([]),
                         0.0, np.nan, np.nan, n_iter)
    arr = np.asarray(optimas)
    p5, p50, p95 = np.percentile(arr, [5, 50, 95])
    return DayResult(float(p50), float(p5), float(p95), len(optimas) / n_iter,
                     np.array([]), np.array([]), float(np.mean(riesgos)),
                     float(np.median(aperturas)), float(np.median(cierres)), n_iter)
