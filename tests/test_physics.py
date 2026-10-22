"""Tests del núcleo físico — validan las ecuaciones del PDF contra el escenario
de día típico de verano en Córdoba (fixtures de conftest.py)."""
from __future__ import annotations

import math

import pytest

from src import alerts, physics


def test_psat_sane_y_creciente(cfg):
    # Tetens a 25 °C ≈ 31.7 hPa
    assert physics.psat_hpa(25.0) == pytest.approx(31.7, abs=0.3)
    assert physics.psat_hpa(35.0) > physics.psat_hpa(25.0) > physics.psat_hpa(15.0)
    assert physics.psat_hpa(-5.0) > 0


def test_vapor_y_vpd(cfg):
    # HR 100% → el aire está saturado → VPD = 0
    assert physics.vapor_pressure_hpa(25.0, 100.0) == pytest.approx(physics.psat_hpa(25.0))
    assert physics.vpd_kpa(25.0, 100.0) == pytest.approx(0.0)
    # Mediodía de Córdoba: VPD claramente alto (> 1.5 kPa)
    assert physics.vpd_kpa(31.0, 40.0) > 1.5
    # Aire más húmedo → menos VPD
    assert physics.vpd_kpa(30.0, 30.0) > physics.vpd_kpa(30.0, 80.0)


def test_temperatura_agua(cfg):
    # La radiación calienta la lámina por encima del aire
    assert physics.water_temperature_c(30.0, 800.0, 14, cfg) > 30.0
    # Por la mañana hay sobrecalentamiento por la entrada del concentrador...
    t_manana = physics.water_temperature_c(22.0, 300.0, 8, cfg)
    # ...que desaparece a mediodía (solo queda el factor solar)
    t_mediodia_solo_solar = 22.0 + cfg.physics.coef_solar_agua * 0.3
    assert t_mediodia_solo_solar < t_manana
    # Mínimo físico de15 °C
    assert physics.water_temperature_c(5.0, 0.0, 21, cfg) >= 15.0


def test_evaporacion(cfg):
    t_w = 35.0
    e_mediodia = physics.evaporation_mm_h(31.0, 40.0, 2.5, t_w, cfg)
    e_mañana = physics.evaporation_mm_h(18.0, 85.0, 0.5, 22.0, cfg)
    assert e_mediodia > e_mañana * 5  # el mediodía evapora muchísimo más
    # HR muy alta → evaporación casi nula
    assert physics.evaporation_mm_h(20.0, 95.0, 1.0, 20.0, cfg) < 0.02
    # Más viento → más evaporación
    assert (physics.evaporation_mm_h(30.0, 40.0, 5.0, 34.0, cfg)
            > physics.evaporation_mm_h(30.0, 40.0, 1.0, 34.0, cfg))
    # Nunca negativa (no condensa)
    assert physics.evaporation_mm_h(15.0, 100.0, 0.0, 10.0, cfg) >= 0.0


def test_umbral_sobresaturacion(cfg):
    u25 = physics.solubility_threshold_g_l(25.0, cfg)
    u35 = physics.solubility_threshold_g_l(35.0, cfg)
    assert 315.0 <= u25 <= 320.0  # rango del PDF
    assert u35 > u25              # sube con la temperatura


def test_concentracion(cfg):
    # ΣE = 0 → sin cambio
    assert physics.concentration_g_l(300.0, 0.0, 7.0) == 300.0
    # masa > lineal para la misma pérdida de agua
    masa = physics.concentration_g_l(300.0, 4.0, 7.0, "masa")
    lineal = physics.concentration_g_l(300.0, 4.0, 7.0, "lineal")
    assert masa > lineal > 300.0
    # C0/(1−ΣE/h) con h=70 mm: 300/(1−4/70) ≈ 317.9
    assert masa == pytest.approx(300.0 / (1 - 4 / 70))
    # Se evaporó toda la lámina → imposible físico
    assert physics.concentration_g_l(300.0, 70.0, 7.0) == math.inf
    with pytest.raises(ValueError):
        physics.concentration_g_l(300.0, 1.0, 7.0, "raro")


def test_dia_verano_nuclea_y_abre_ventana(cfg, dia_verano_cordoba):
    sim = physics.concentrations_over_day(dia_verano_cordoba, cfg)
    # Columnas del contrato
    for col in ("t_water_c", "evap_mm_h", "vpd_kpa", "umbral_g_l", "c_g_l",
                "fase", "hora_nucleacion", "hr_min_pct"):
        assert col in sim.columns
    nucleacion = sim["hora_nucleacion"].dropna()
    assert not nucleacion.empty, "el día de verano en Córdoba debe nucleear"
    h = float(nucleacion.iloc[0])
    assert 11.0 <= h <= 16.5, f"nucleación a las {h}h, esperada entre 11 y 16:30"
    # Tras nuclear + crecimiento debe llegar la Fase 2 (ventana)
    assert (sim["fase"] == 2).any()
    # La concentración crece a lo largo del día
    assert sim["c_g_l"].iloc[-1] > sim["c_g_l"].iloc[0]


def test_dia_nublado_no_nuclea(cfg, dia_nublado_humedo):
    sim = physics.concentrations_over_day(dia_nublado_humedo, cfg)
    assert sim["hora_nucleacion"].dropna().empty, "un día nublado/húmedo no debe nucleear"
    assert (sim["fase"] == 2).sum() == 0
    assert (sim["c_g_l"] < sim["umbral_g_l"]).all()


def test_fase3_por_viento(cfg, dia_verano_cordoba):
    df = dia_verano_cordoba.copy()
    df.loc[df["hour"] == 15, "wind_ms"] = 7.0  # ráfaga por encima del peligro
    sim = physics.concentrations_over_day(df, cfg)
    assert alerts.evaluar_fase(320.0, 318.0, 15.0, 13.0, 7.0, 30.0, 28.0, cfg) == 3
    assert 3 in set(sim["fase"])
