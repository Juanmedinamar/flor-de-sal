"""Tests de la asimilación de datos (corrección por sesgo)."""
from __future__ import annotations

import pandas as pd
import pytest

from src import assimilation


@pytest.fixture
def forecast():
    return pd.DataFrame({
        "hour": [10, 11, 12, 13],
        "temp_c": [26.0, 28.0, 30.0, 31.0],
        "rh_pct": [55.0, 50.0, 45.0, 42.0],
        "wind_ms": [1.5, 1.8, 2.0, 2.2],
        "wind_dir_deg": [90.0] * 4,
        "radiation_w_m2": [600.0, 700.0, 800.0, 850.0],
    })


@pytest.fixture
def readings():
    return pd.DataFrame({
        "reading_time": ["10:30", "11:30", "12:30"],
        "t_ambiente_c": [28.0, 30.0, 33.0],   # +2, +2, +3 sobre la previsión
        "rh_pct": [48.0, 44.0, 40.0],          # −7, −6, −5
        "wind_ms": [2.0, 2.5, 3.0],            # +0.5, +0.7, +1.0
    })


def test_compute_bias(forecast, readings):
    bias = assimilation.compute_bias(forecast, readings)
    assert bias["temp_c"] == pytest.approx((2 + 2 + 3) / 3)
    assert bias["rh_pct"] == pytest.approx((-7 - 6 - 5) / 3)
    assert bias["wind_ms"] == pytest.approx((0.5 + 0.7 + 1.0) / 3)


def test_compute_bias_limita_horas(forecast, readings):
    bias = assimilation.compute_bias(forecast, readings, max_hours_back=1)
    # Solo la última lectura (12:30 → 33−30 = +3)
    assert bias["temp_c"] == pytest.approx(3.0)


def test_compute_bias_sin_lecturas(forecast):
    assert assimilation.compute_bias(forecast, pd.DataFrame()) == {}
    assert assimilation.compute_bias(forecast, None) == {}


def test_compute_bias_ignora_nan(forecast, readings):
    readings.loc[1, "t_ambiente_c"] = None
    bias = assimilation.compute_bias(forecast, readings)
    assert bias["temp_c"] == pytest.approx((2 + 3) / 2)


def test_apply_bias_no_muta_y_trunca(forecast):
    original = forecast.copy()
    out = assimilation.apply_bias(forecast, {"temp_c": 2.0, "rh_pct": -100.0,
                                             "wind_ms": -5.0})
    pd.testing.assert_frame_equal(forecast, original)       # no muta
    assert out["temp_c"].iloc[0] == pytest.approx(28.0)     # +2
    assert (out["rh_pct"] == 0.0).all()                     # truncado abajo
    assert (out["wind_ms"] == 0.0).all()                    # sin viento negativo
    out2 = assimilation.apply_bias(forecast, {"rh_pct": 100.0})
    assert (out2["rh_pct"] == 100.0).all()                  # truncado arriba


def test_apply_bias_vacio_devuelve_copia(forecast):
    out = assimilation.apply_bias(forecast, {})
    pd.testing.assert_frame_equal(out, forecast)
