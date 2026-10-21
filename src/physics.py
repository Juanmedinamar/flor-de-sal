"""Núcleo físico del modelo — ver AGENTS.md para el detalle de las ecuaciones.

Ecuaciones implementadas (fuente: AGENTS.md / "Modelo flor de sal.pdf"):
  - Tetens:            Psat(T) = 6.1078 · exp(17.27·T / (T + 237.3))  [hPa]
  - Vapor del aire:    Pvapor = HR/100 · Psat(T_ambiente)
  - VPD:               VPD[kPa] = (Psat(T_agua) − Pvapor_aire) / 10
  - Dalton mod.:       E_día[mm/día] = (a + b·V) · VPD[kPa];  E_hora = E_día / 24
  - T del agua:        T_agua = T_amb + coef_solar·(rad/1000) + extra_mañana(h)
  - Umbral:            umbral(T_agua) = 318 + 0.5·(T_agua − 25)  [g/l]
  - Concentración:     C_t = C0 / (1 − ΣE/h)   ("masa", h = profundidad_cm·10 mm)
                       C_t = C0 · (1 + ΣE/h)   ("lineal", aproximación del PDF)
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from src import alerts
from src.config import ConfigProto

# Mínimo físico de la temperatura de la lámina (no se enfría por debajo de esto).
_TEMP_AGUA_MIN_C = 15.0


def psat_hpa(t_c: float) -> float:
    """Presión de saturación del vapor de agua (Tetens).

    Psat(T) = 6.1078 · exp(17.27·T / (T + 237.3))  [hPa]
    """
    return 6.1078 * math.exp(17.27 * t_c / (t_c + 237.3))


def psat_hpa_arr(t_c: np.ndarray) -> np.ndarray:
    """Versión vectorizada de psat_hpa (misma fórmula) para el Monte Carlo."""
    return 6.1078 * np.exp(17.27 * t_c / (t_c + 237.3))


def vapor_pressure_hpa(t_c: float, rh_pct: float) -> float:
    """Presión parcial de vapor del aire: Pvapor = HR/100 · Psat(T_ambiente) [hPa]."""
    return rh_pct / 100.0 * psat_hpa(t_c)


def vpd_kpa(t_c: float, rh_pct: float) -> float:
    """Déficit de presión de vapor del aire: VPD = (Psat(T) − Pvapor) / 10 [kPa]."""
    return (psat_hpa(t_c) - vapor_pressure_hpa(t_c, rh_pct)) / 10.0


def water_temperature_c(t_air_c: float, radiation_w_m2: float, hour: int,
                        cfg: ConfigProto) -> float:
    """Temperatura de la lámina de agua.

    T_agua = T_amb + cfg.physics.coef_solar_agua·(rad/1000) + extra_mañana(h)
    donde extra_mañana decae linealmente de cfg.physics.t_extra_manana_c (en
    cfg.simulation.hora_inicio) a 0 a las 12:00. Mínimo físico: 15 °C.
    """
    h0 = float(cfg.simulation.hora_inicio)
    dur = 12.0 - h0
    if dur > 0 and hour < 12.0:
        factor = min(1.0, max(0.0, (12.0 - hour) / dur))
        extra = cfg.physics.t_extra_manana_c * factor
    else:
        extra = 0.0
    t_agua = (t_air_c
              + cfg.physics.coef_solar_agua * radiation_w_m2 / 1000.0
              + extra)
    return max(t_agua, _TEMP_AGUA_MIN_C)


def evaporation_mm_h(t_air_c: float, rh_pct: float, wind_ms: float,
                     t_water_c: float, cfg: ConfigProto) -> float:
    """Evaporación horaria — ley de Dalton modificada.

    E_hora[mm/h] = (a + b·V) · VPD_kPa / 24, con
    VPD = (Psat(T_agua) − Pvapor_aire(T_ambiente, HR)) / 10  [kPa]
    (a = cfg.physics.dalton_a, b = cfg.physics.dalton_b). Mínimo 0 (no se
    condensa: si el aire está saturado por encima del agua, E = 0).
    """
    vpd = (psat_hpa(t_water_c) - vapor_pressure_hpa(t_air_c, rh_pct)) / 10.0
    vpd = max(vpd, 0.0)
    e_dia = (cfg.physics.dalton_a + cfg.physics.dalton_b * wind_ms) * vpd
    return max(e_dia / 24.0, 0.0)


def solubility_threshold_g_l(t_water_c: float, cfg: ConfigProto) -> float:
    """Umbral de sobresaturación (nucleación).

    umbral(T_agua) = cfg.water.umbral_sobresaturacion_g_l
                     + cfg.water.umbral_pendiente_g_l_c·(T_agua − umbral_temp_ref_c)
    por defecto: 318 + 0.5·(T_agua − 25) [g/l].
    """
    w = cfg.water
    return (w.umbral_sobresaturacion_g_l
            + w.umbral_pendiente_g_l_c * (t_water_c - w.umbral_temp_ref_c))


def concentration_g_l(c0_g_l: float, evap_accum_mm: float, depth_cm: float,
                      model: str = "masa") -> float:
    """Concentración superficial de salmuera con masa de sal constante.

    h = depth_cm · 10 [mm]; ΣE = evaporación acumulada [mm = L/m²].
      "masa":   C_t = C0 / (1 − ΣE/h)   (default, físicamente correcto)
      "lineal": C_t = C0 · (1 + ΣE/h)   (aproximación lineal del PDF)
    Si ΣE >= h (imposible físico: se evaporó toda la lámina) devuelve inf.
    """
    if model not in ("masa", "lineal"):
        raise ValueError(f"Modelo de concentración desconocido: {model!r} "
                         "(usa 'masa' o 'lineal').")
    h_mm = depth_cm * 10.0
    frac = evap_accum_mm / h_mm
    if frac >= 1.0:  # ΣE >= h → imposible físico
        return math.inf
    if model == "masa":
        return c0_g_l / (1.0 - frac)
    return c0_g_l * (1.0 + frac)


def simulate_hourly(row: pd.Series | dict, cfg: ConfigProto,
                    c0_g_l: float | None = None) -> pd.Series:
    """Física de una fila horaria, con la concentración acumulada hasta esa hora.

    `c0_g_l` es la concentración EFECTIVA acumulada hasta la hora anterior (la
    gestiona el llamante, p.ej. Monte Carlo, que va pasando el resultado de
    concentration_g_l); por defecto se parte de cfg.water.entrada_cristalizador_g_l.

    Devuelve una Series con añadidos: t_water_c, evap_mm_h, vpd_kpa, umbral_g_l,
    c_sup_g_l (resultado de aplicar la evaporación de ESTA hora a la
    concentración acumulada previa).
    """
    out = pd.Series(row) if not isinstance(row, pd.Series) else row.copy()
    c_prev = (float(c0_g_l) if c0_g_l is not None
              else float(cfg.water.entrada_cristalizador_g_l))
    t_water = water_temperature_c(float(out["temp_c"]), float(out["radiation_w_m2"]),
                                  int(out["hour"]), cfg)
    e_h = evaporation_mm_h(float(out["temp_c"]), float(out["rh_pct"]),
                           float(out["wind_ms"]), t_water, cfg)
    out["t_water_c"] = t_water
    out["evap_mm_h"] = e_h
    out["vpd_kpa"] = (psat_hpa(t_water) - vapor_pressure_hpa(float(out["temp_c"]),
                                                             float(out["rh_pct"]))) / 10.0
    out["umbral_g_l"] = solubility_threshold_g_l(t_water, cfg)
    out["c_sup_g_l"] = concentration_g_l(c_prev, e_h,
                                         cfg.water.profundidad_lamina_cm)
    return out


def concentrations_over_day(df: pd.DataFrame, cfg: ConfigProto,
                            c0_g_l: float | None = None) -> pd.DataFrame:
    """Concentración y fase hora a hora a lo largo del día.

    Acumula ΣE hora a hora desde cfg.simulation.hora_inicio y, para cada hora,
    calcula t_water_c, evap_mm_h, vpd_kpa, umbral_g_l y c_g_l
    (C_t = C0 / (1 − ΣE/h), h = profundidad_lamina_cm·10 mm). La fase (0/1/2/3)
    se asigna con alerts.evaluar_fase, que implementa las reglas del PDF
    (nucleación = C >= umbral; ventana = nucleación + minutos_crecimiento;
    cierre = viento/HR/rehidratación). Se añaden las columnas de seguimiento
    `hora_nucleacion` (NaN hasta que C cruza el umbral) y `hr_min_pct` (mínimo
    de HR del día hasta esa hora, para la regla de repunte de HR).
    """
    out = df.copy()
    c0 = (float(c0_g_l) if c0_g_l is not None
          else float(cfg.water.entrada_cristalizador_g_l))
    depth_cm = float(cfg.water.profundidad_lamina_cm)

    sigma_e = 0.0          # ΣE acumulado [mm]
    hora_nucleacion: float | None = None
    hr_min = math.inf
    t_water_l: list[float] = []
    evap_l: list[float] = []
    vpd_l: list[float] = []
    umbral_l: list[float] = []
    c_l: list[float] = []
    fase_l: list[int] = []
    hn_l: list[float] = []
    hrmin_l: list[float] = []

    for _, fila in out.iterrows():
        hour = int(fila["hour"])
        t_water = water_temperature_c(float(fila["temp_c"]),
                                      float(fila["radiation_w_m2"]), hour, cfg)
        e_h = evaporation_mm_h(float(fila["temp_c"]), float(fila["rh_pct"]),
                               float(fila["wind_ms"]), t_water, cfg)
        vpd = ((psat_hpa(t_water) - vapor_pressure_hpa(float(fila["temp_c"]),
                                                       float(fila["rh_pct"])))
               / 10.0)
        umbral = solubility_threshold_g_l(t_water, cfg)
        sigma_e += e_h
        c_sup = concentration_g_l(c0, sigma_e, depth_cm)
        if hora_nucleacion is None and c_sup >= umbral:
            hora_nucleacion = float(hour)
        hr_min = min(hr_min, float(fila["rh_pct"]))
        fase = alerts.evaluar_fase(c_sup, umbral, float(hour), hora_nucleacion,
                                   float(fila["wind_ms"]), float(fila["rh_pct"]),
                                   hr_min, cfg)
        t_water_l.append(t_water)
        evap_l.append(e_h)
        vpd_l.append(vpd)
        umbral_l.append(umbral)
        c_l.append(c_sup)
        fase_l.append(fase)
        hn_l.append(hora_nucleacion if hora_nucleacion is not None else math.nan)
        hrmin_l.append(hr_min)

    out["t_water_c"] = t_water_l
    out["evap_mm_h"] = evap_l
    out["vpd_kpa"] = vpd_l
    out["umbral_g_l"] = umbral_l
    out["c_g_l"] = c_l
    out["fase"] = fase_l
    out["hora_nucleacion"] = hn_l
    out["hr_min_pct"] = hrmin_l
    return out
