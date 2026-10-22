"""Tests del motor de Monte Carlo — validan la ventana del día típico del PDF
(nucleación ~14h, cosecha 16-19h) y el comportamiento estocástico."""
from __future__ import annotations

import numpy as np
import pytest

from src import montecarlo


def test_dia_verano_cordoba(cfg, dia_verano_cordoba):
    """Escenario de validación del PDF: ventana por la tarde, cosecha 16-19h."""
    r = montecarlo.simulate_day(dia_verano_cordoba, cfg, n_iter=1000, seed=42)
    assert r.prob_ventana > 0.8, "un día de verano claro debe abrir ventana casi seguro"
    assert 15.0 <= r.median_hour <= 19.5, f"óptima mediana {r.median_hour} fuera de rango"
    assert r.ci_low <= r.median_hour <= r.ci_high
    assert r.window_start_median < r.median_hour < r.window_end_median
    # Ventana coherente: abre por la tarde y dura al menos 1 h
    assert 14.0 <= r.window_start_median <= 18.5
    assert r.window_end_median - r.window_start_median >= 1.0
    # Campana normalizada (área 1)
    assert r.hist_hours.shape == r.hist_probs.shape
    assert r.hist_probs.sum() * 0.25 == pytest.approx(1.0, abs=0.05)


def test_dia_nublado_humedo(cfg, dia_nublado_humedo):
    r = montecarlo.simulate_day(dia_nublado_humedo, cfg, n_iter=1000, seed=42)
    assert r.prob_ventana < 0.2, "un día nublado no debe abrir ventana"
    assert np.isnan(r.median_hour)


def test_determinismo_y_seed(cfg, dia_verano_cordoba):
    a = montecarlo.simulate_day(dia_verano_cordoba, cfg, n_iter=300, seed=7)
    b = montecarlo.simulate_day(dia_verano_cordoba, cfg, n_iter=300, seed=7)
    c = montecarlo.simulate_day(dia_verano_cordoba, cfg, n_iter=300, seed=99)
    assert a.median_hour == b.median_hour and a.prob_ventana == b.prob_ventana
    assert np.array_equal(a.hist_probs, b.hist_probs)
    assert not np.array_equal(a.hist_probs, c.hist_probs)


def test_bias_seco_adelanta_apertura(cfg, dia_verano_cordoba):
    """Si el aire está más seco de lo previsto (HR −8), la ventana abre antes."""
    base = montecarlo.simulate_day(dia_verano_cordoba, cfg, n_iter=500, seed=5)
    seco = montecarlo.simulate_day(dia_verano_cordoba, cfg, bias={"rh_pct": -8.0},
                                   n_iter=500, seed=5)
    assert seco.window_start_median <= base.window_start_median
    assert seco.prob_ventana >= base.prob_ventana


def test_viento_alto_aumenta_prob_fase3(cfg, dia_verano_cordoba):
    """Viento por encima del límite → los escenarios cierran por riesgo (Fase 3)."""
    df = dia_verano_cordoba.copy()
    df["wind_ms"] = 6.0
    r = montecarlo.simulate_day(df, cfg, n_iter=500, seed=11)
    assert r.prob_fase3 > 0.9


def test_dayresult_tipos(cfg, dia_verano_cordoba):
    r = montecarlo.simulate_day(dia_verano_cordoba, cfg, n_iter=200, seed=1)
    assert r.n_iter == 200
    assert isinstance(r.prob_ventana, float) and 0.0 <= r.prob_ventana <= 1.0
    assert isinstance(r.prob_fase3, float) and 0.0 <= r.prob_fase3 <= 1.0


def test_vectorizada_coincide_con_referencia_escalar(cfg, dia_verano_cordoba):
    """La versión vectorizada debe ser coherente con la ruta de referencia (alerts)."""
    vec = montecarlo.simulate_day(dia_verano_cordoba, cfg, n_iter=400, seed=3)
    esc = montecarlo.simulate_day_referenciaEscalar(dia_verano_cordoba, cfg,
                                                    n_iter=400, seed=3)
    assert vec.prob_ventana == pytest.approx(esc.prob_ventana, abs=0.1)
    assert abs(vec.median_hour - esc.median_hour) <= 1.0
    assert vec.prob_fase3 == pytest.approx(esc.prob_fase3, abs=0.1)


def test_cierre_nocturno_normal_no_es_riesgo(cfg, dia_verano_cordoba):
    """El repunte normal de HR al anochecer cierra la ventana pero NO es riesgo."""
    r = montecarlo.simulate_day(dia_verano_cordoba, cfg, n_iter=1000, seed=42)
    assert r.prob_fase3 < 0.3, "un día calmado no debe marcar riesgo de hundimiento"


def test_rendimiento(cfg, dia_verano_cordoba):
    """1000 escenarios deben simularse en pocos segundos (UI interactiva)."""
    import time
    t0 = time.time()
    montecarlo.simulate_day(dia_verano_cordoba, cfg, n_iter=1000, seed=42)
    assert time.time() - t0 < 5.0, "Monte Carlo demasiado lento para la UI"
