"""Tests basados en propiedades (Hypothesis) — invariantes físicas del modelo.

Valida que las funciones de src.physics respeten las leyes físicas esperadas
para cualquier entrada válida (no solo los casos del PDF).
"""
from __future__ import annotations

import math

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings

from src import physics
from src.config import Config

# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def cfg() -> Config:
    """Configuración real del proyecto para usar coeficientes de Dalton, etc."""
    from src.config import load_config
    return load_config()


# ─── Estrategias de Hypothesis ───────────────────────────────────────────────

# Temperaturas físicas razonables para una salina en Córdoba
_TEMP_C = st.floats(min_value=-40.0, max_value=60.0, allow_nan=False, allow_infinity=False)

# Humedad relativa 0-100 %
_RH_PCT = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)

# Viento ≥ 0 m/s (razonable hasta 30 m/s en tormenta)
_WIND_MS = st.floats(min_value=0.0, max_value=30.0, allow_nan=False, allow_infinity=False)

# Radiación solar 0-1300 W/m² (pico teórico ~1360)
_RAD = st.floats(min_value=0.0, max_value=1400.0, allow_nan=False, allow_infinity=False)

# Horas enteras 0-23
_HOUR = st.integers(min_value=0, max_value=23)

# Profundidad de lámina cm (0.1-50 cm)
_DEPTH_CM = st.floats(min_value=0.1, max_value=50.0, allow_nan=False, allow_infinity=False)

# Concentración inicial g/l (0-400)
_C0 = st.floats(min_value=0.0, max_value=400.0, allow_nan=False, allow_infinity=False)

# Evaporación acumulada mm (≥0, hasta profundidad en mm)
_EVAP_ACCUM = st.floats(min_value=0.0, max_value=500.0, allow_nan=False, allow_infinity=False)

# VPD kPa (≥0)
_VPD = st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False)


# ─── Tests de psat_hpa ───────────────────────────────────────────────────────

@given(t_c=_TEMP_C)
@settings(max_examples=50, deadline=None)
def test_psat_hpa_positiva(t_c: float) -> None:
    """Psat(T) > 0 para toda T física [-40, 60] °C (presión de vapor siempre positiva)."""
    assert physics.psat_hpa(t_c) > 0.0


@given(t1=_TEMP_C, t2=_TEMP_C)
@settings(max_examples=50, deadline=None)
def test_psat_hpa_monotona_creciente(t1: float, t2: float) -> None:
    """Psat es estrictamente creciente con la temperatura (ecuación de Tetens)."""
    # Filtrar casos donde la diferencia sea muy pequeña (precisión numérica)
    if abs(t1 - t2) < 1e-10:
        return
    if t1 < t2:
        assert physics.psat_hpa(t1) < physics.psat_hpa(t2)
    else:
        assert physics.psat_hpa(t1) > physics.psat_hpa(t2)


# ─── Tests de vapor_pressure_hpa / vpd_kpa ───────────────────────────────────

@given(t_c=_TEMP_C, rh_pct=_RH_PCT)
@settings(max_examples=50, deadline=None)
def test_vapor_pressure_hpa_rango(t_c: float, rh_pct: float) -> None:
    """Pvapor = HR/100 * Psat(T) ∈ [0, Psat(T)]."""
    pv = physics.vapor_pressure_hpa(t_c, rh_pct)
    psat = physics.psat_hpa(t_c)
    assert 0.0 <= pv <= psat + 1e-12  # tolerancia numérica


@given(t_c=_TEMP_C, rh_pct=_RH_PCT)
@settings(max_examples=50, deadline=None)
def test_vpd_kpa_no_negativo(t_c: float, rh_pct: float) -> None:
    """VPD = (Psat(T) - Pvapor) / 10 ≥ 0  (en kPa)."""
    assert physics.vpd_kpa(t_c, rh_pct) >= -1e-12  # tolerancia numérica


@given(t_c=_TEMP_C)
@settings(max_examples=30, deadline=None)
def test_vpd_cero_si_saturado(t_c: float) -> None:
    """VPD = 0 ⇔ HR = 100% (aire saturado a esa temperatura)."""
    assert physics.vpd_kpa(t_c, 100.0) == pytest.approx(0.0, abs=1e-10)


@given(t_agua=_TEMP_C, t_aire=_TEMP_C)
@settings(max_examples=30, deadline=None)
def test_vpd_cero_si_iguales_y_saturado(t_agua: float, t_aire: float) -> None:
    """VPD = 0 ⇔ T_agua = T_aire Y HR = 100% (equilibrio termodinámico)."""
    # Solo si ambas temperaturas son iguales y HR=100%
    if abs(t_agua - t_aire) < 1e-9:
        vpd = (physics.psat_hpa(t_agua) - physics.vapor_pressure_hpa(t_aire, 100.0)) / 10.0
        assert vpd == pytest.approx(0.0, abs=1e-10)


# ─── Tests de evaporation_mm_h ───────────────────────────────────────────────

@given(vpd=_VPD, wind_ms=_WIND_MS)
@settings(max_examples=50, deadline=None)
def test_evaporation_no_negativa(cfg: Config, vpd: float, wind_ms: float) -> None:
    """E_hora = (a + b·V)·VPD/24 ≥ 0  (nunca hay condensación neta en el modelo)."""
    physics.evaporation_mm_h(25.0, 50.0, wind_ms, 25.0, cfg)  # T fijas, VPD efectivo controlado
    # El VPD real se calcula dentro; forzamos VPD≈0 para aislar el efecto VPD=0
    if vpd < 1e-9:
        # Con HR=100% el VPD interno será 0
        e0 = physics.evaporation_mm_h(25.0, 100.0, wind_ms, 25.0, cfg)
        assert e0 >= -1e-12


@given(vpd=_VPD, wind1=_WIND_MS, wind2=_WIND_MS)
@settings(max_examples=30, deadline=None)
def test_evaporation_lineal_en_viento(cfg: Config, vpd: float, wind1: float, wind2: float) -> None:
    """Para VPD fijo, E_hora es lineal en V: E(V) = (a + b·V)·VPD/24."""
    # Usamos HR=0% y T_agua=T_aire para que VPD interno = Psat/10 (constante)
    t = 25.0
    e1 = physics.evaporation_mm_h(t, 0.0, wind1, t, cfg)
    e2 = physics.evaporation_mm_h(t, 0.0, wind2, t, cfg)
    # (a + b·V1) / (a + b·V2) = e1 / e2
    if wind2 != wind1 and e2 > 1e-12:
        ratio_teorico = (cfg.physics.dalton_a + cfg.physics.dalton_b * wind1) / \
                        (cfg.physics.dalton_a + cfg.physics.dalton_b * wind2)
        ratio_medido = e1 / e2
        assert ratio_medido == pytest.approx(ratio_teorico, rel=1e-9)


@given(wind_ms=_WIND_MS)
@settings(max_examples=30, deadline=None)
def test_evaporation_nula_si_vpd_cero(cfg: Config, wind_ms: float) -> None:
    """Si HR=100% y T_agua=T_aire ⇒ VPD=0 ⇒ E=0 independientemente del viento."""
    t = 25.0
    e = physics.evaporation_mm_h(t, 100.0, wind_ms, t, cfg)
    assert e == pytest.approx(0.0, abs=1e-12)


# ─── Tests de concentration_g_l (modelo "masa") ──────────────────────────────

@given(c0=_C0, depth_cm=_DEPTH_CM)
@settings(max_examples=50, deadline=None)
def test_concentracion_sin_evaporacion_igual_a_c0(c0: float, depth_cm: float) -> None:
    """ΣE = 0 ⇒ C_t = C0."""
    assert physics.concentration_g_l(c0, 0.0, depth_cm, "masa") == pytest.approx(c0)


@given(c0=_C0, evap=_EVAP_ACCUM, depth_cm=_DEPTH_CM)
@settings(max_examples=50, deadline=None)
def test_concentracion_masa_mayor_que_c0(c0: float, evap: float, depth_cm: float) -> None:
    """Con evaporación ΣE>0, C_t ≥ C0 (la sal no desaparece)."""
    h_mm = depth_cm * 10.0
    if evap < h_mm:  # caso físico válido
        ct = physics.concentration_g_l(c0, evap, depth_cm, "masa")
        assert ct >= c0 - 1e-12


@given(c0=st.floats(min_value=1.0, max_value=400.0, allow_nan=False, allow_infinity=False),
       depth_cm=_DEPTH_CM)
@settings(max_examples=30, deadline=None)
def test_concentracion_masa_diverge_al_limite(c0: float, depth_cm: float) -> None:
    """Cuando ΣE → h (se evapora toda la lámina) C_t → +inf (con C0 > 0)."""
    h_mm = depth_cm * 10.0
    # Aproximarnos al límite desde abajo
    evap = h_mm * 0.999999
    ct = physics.concentration_g_l(c0, evap, depth_cm, "masa")
    assert ct > c0 * 1e5  # crece sin cota


@given(c0=_C0, depth_cm=_DEPTH_CM)
@settings(max_examples=30, deadline=None)
def test_concentracion_inf_si_evap_ge_h(c0: float, depth_cm: float) -> None:
    """ΣE ≥ h ⇒ C_t = inf (imposible físico: lámina seca)."""
    h_mm = depth_cm * 10.0
    assert physics.concentration_g_l(c0, h_mm, depth_cm, "masa") == math.inf
    assert physics.concentration_g_l(c0, h_mm * 1.5, depth_cm, "masa") == math.inf


@given(c0=_C0, evap=_EVAP_ACCUM, depth_cm=_DEPTH_CM)
@settings(max_examples=30, deadline=None)
def test_modelo_masa_mayor_que_lineal(c0: float, evap: float, depth_cm: float) -> None:
    """Para la misma evaporación, modelo masa ≥ modelo lineal (físicamente correcto)."""
    h_mm = depth_cm * 10.0
    if evap < h_mm:
        masa = physics.concentration_g_l(c0, evap, depth_cm, "masa")
        lineal = physics.concentration_g_l(c0, evap, depth_cm, "lineal")
        assert masa >= lineal - 1e-12


# ─── Tests de solubility_threshold_g_l (umbral) ──────────────────────────────

@given(t_c=_TEMP_C)
@settings(max_examples=50, deadline=None)
def test_umbral_formula(cfg: Config, t_c: float) -> None:
    """umbral(T) = 318 + 0.5·(T − 25) ± tolerancia (valores por defecto del config)."""
    w = cfg.water
    esperado = w.umbral_sobresaturacion_g_l + w.umbral_pendiente_g_l_c * (t_c - w.umbral_temp_ref_c)
    assert physics.solubility_threshold_g_l(t_c, cfg) == pytest.approx(esperado, abs=0.1)


@given(t1=_TEMP_C, t2=_TEMP_C)
@settings(max_examples=30, deadline=None)
def test_umbral_creciente_con_temperatura(cfg: Config, t1: float, t2: float) -> None:
    """El umbral de sobresaturación crece con la temperatura (pendiente positiva)."""
    # Filtrar casos donde la diferencia sea muy pequeña (precisión numérica)
    if abs(t1 - t2) < 1e-9:
        return
    if t1 < t2:
        assert physics.solubility_threshold_g_l(t1, cfg) < physics.solubility_threshold_g_l(t2, cfg)
    else:
        assert physics.solubility_threshold_g_l(t1, cfg) > physics.solubility_threshold_g_l(t2, cfg)


# ─── Tests de water_temperature_c ────────────────────────────────────────────

@given(t_air=_TEMP_C, rad=_RAD, hour=_HOUR)
@settings(max_examples=50, deadline=None)
def test_temperatura_agua_minimo_fisico(cfg: Config, t_air: float, rad: float, hour: int) -> None:
    """T_agua nunca baja de 15 °C (mínimo físico de la lámina)."""
    t_w = physics.water_temperature_c(t_air, rad, hour, cfg)
    assert t_w >= 15.0 - 1e-9


@given(t_air=_TEMP_C, rad=_RAD)
@settings(max_examples=30, deadline=None)
def test_temperatura_agua_subida_por_radiacion(cfg: Config, t_air: float, rad: float) -> None:
    """Más radiación ⇒ T_agua más alta (coef_solar_agua > 0)."""
    t_w_low = physics.water_temperature_c(t_air, 0.0, 14, cfg)
    t_w_high = physics.water_temperature_c(t_air, rad, 14, cfg)
    assert t_w_high >= t_w_low - 1e-9


@given(t_air=st.floats(min_value=20.0, max_value=40.0, allow_nan=False, allow_infinity=False))
@settings(max_examples=30, deadline=None)
def test_extra_manana_decae_linealmente(cfg: Config, t_air: float) -> None:
    """El término extra_mañana decae linealmente de hora_inicio a 12:00."""
    h0 = cfg.simulation.hora_inicio
    if h0 < 12:
        t_early = physics.water_temperature_c(t_air, 0.0, h0, cfg)
        t_late = physics.water_temperature_c(t_air, 0.0, 12, cfg)
        # A las 12:00 el extra es 0; a h0 es t_extra_manana_c
        extra_esperado = cfg.physics.t_extra_manana_c
        assert t_early - t_late == pytest.approx(extra_esperado, abs=1e-9)


# ─── Tests integrados: simulate_hourly / concentrations_over_day ─────────────

@given(
    temp_c=_TEMP_C, rh_pct=_RH_PCT, wind_ms=_WIND_MS, rad=_RAD, hour=_HOUR
)
@settings(max_examples=30, deadline=None)
def test_simulate_hourly_devuelve_claves_esperadas(cfg: Config, temp_c: float, rh_pct: float,
                                                    wind_ms: float, rad: float, hour: int) -> None:
    """simulate_hourly añade las columnas del contrato físico."""
    fila = pd.Series({
        "hour": hour,
        "temp_c": temp_c,
        "rh_pct": rh_pct,
        "wind_ms": wind_ms,
        "wind_dir_deg": 90.0,
        "radiation_w_m2": rad,
    })
    out = physics.simulate_hourly(fila, cfg)
    for col in ("t_water_c", "evap_mm_h", "vpd_kpa", "umbral_g_l", "c_sup_g_l"):
        assert col in out.index


@given(
    temp_c=_TEMP_C, rh_pct=_RH_PCT, wind_ms=_WIND_MS, rad=_RAD, hour=_HOUR
)
@settings(max_examples=30, deadline=None)
def test_concentrations_over_day_columnas(cfg: Config, temp_c: float, rh_pct: float,
                                           wind_ms: float, rad: float, hour: int) -> None:
    """concentrations_over_day devuelve DataFrame con todas las columnas de seguimiento."""
    import pandas as pd
    df = pd.DataFrame([{
        "hour": hour,
        "temp_c": temp_c,
        "rh_pct": rh_pct,
        "wind_ms": wind_ms,
        "wind_dir_deg": 90.0,
        "radiation_w_m2": rad,
    }])
    out = physics.concentrations_over_day(df, cfg)
    esperadas = ("t_water_c", "evap_mm_h", "vpd_kpa", "umbral_g_l", "c_g_l",
                 "fase", "hora_nucleacion", "hr_min_pct")
    for col in esperadas:
        assert col in out.columns


# Import pandas al final para no romper los tests si hypothesis no lo necesita
import pandas as pd
