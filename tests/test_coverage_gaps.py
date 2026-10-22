"""Tests que cubren gaps de cobertura — líneas no ejercitadas por los tests actuales.

Objetivo: ≥85 % en src/ (actual ~93 %). Estos tests atacan ramas de error,
casos límite y caminos no cubiertos sin forzar 100 %.
"""
from __future__ import annotations

import math
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
import requests

from src.config import Config, load_config, validar_config
from src.db import Database, _sanitizar_json
from src.errors import ConfigError, WeatherDataError, WeatherNetworkError
from src.weather import fetch_forecast, get_json_con_reintentos, resuelve_red

# ─── config.py: validar_config — ramas de error ──────────────────────────────

def _config_base_valido() -> dict:
    """Devuelve un dict plano con config válida para tests."""
    return {
        "location": {"latitude": 37.9, "longitude": -4.75, "timezone": "Europe/Madrid"},
        "water": {"entrada_cristalizador_g_l": 295.0, "profundidad_lamina_cm": 7.0,
                  "umbral_sobresaturacion_g_l": 318.0, "umbral_temp_ref_c": 25.0,
                  "umbral_pendiente_g_l_c": 0.25},
        "physics": {"dalton_a": 0.17, "dalton_b": 0.87, "coef_solar_agua": 0.5,
                    "t_extra_manana_c": 3.0},
        "simulation": {"hora_inicio": 6, "hora_fin": 21, "minutos_crecimiento": 120},
        "montecarlo": {"iterations": 1000, "sigma_temp_c": 1.0, "sigma_rh_pct": 5.0,
                       "sigma_wind_ms": 0.5, "seed": 42},
        "limits": {"viento_peligro_ms": 5.5, "viento_seguro_max_ms": 3.0,
                   "hr_peligro_pct": 65, "hr_cierre_tarde_pct": 45, "hr_ideal_max_pct": 60,
                   "temp_activacion_c": 20},
        "assimilation": {"max_hours_back": 6},
        "network": {"timeout_s": 30.0, "archive_timeout_s": 60.0, "retries": 3, "backoff_base_s": 0.5},
        "season": {"start_date": "2026-04-01", "end_date": "2026-10-15", "iterations": 500,
                   "workers": 2},
        "markov": {"margen_critico_g_l": 2.0, "iterations": 500},
    }


def test_validar_config_falta_seccion_requerida() -> None:
    """Falta una sección requerida → ConfigError claro."""
    data = _config_base_valido()
    data.pop("water")
    with pytest.raises(ConfigError, match="faltan secciones requeridas"):
        validar_config(data)


def test_validar_config_clave_faltante() -> None:
    """Falta una clave dentro de una sección → ConfigError."""
    data = _config_base_valido()
    data["water"].pop("entrada_cristalizador_g_l")
    with pytest.raises(ConfigError, match=r"falta 'water.entrada_cristalizador_g_l'"):
        validar_config(data)


def test_validar_config_tipo_incorrecto() -> None:
    """Valor con tipo incorrecto (bool en vez de int/float) → ConfigError."""
    data = _config_base_valido()
    data["water"]["entrada_cristalizador_g_l"] = True  # bool no es int/float válido
    with pytest.raises(ConfigError, match="debe ser"):
        validar_config(data)


def test_validar_config_fuera_rango_min() -> None:
    """Valor por debajo del mínimo → ConfigError."""
    data = _config_base_valido()
    data["location"]["latitude"] = -100.0  # < -90
    with pytest.raises(ConfigError, match=r"fuera de rango.*mín"):
        validar_config(data)


def test_validar_config_fuera_rango_max() -> None:
    """Valor por encima del máximo → ConfigError."""
    data = _config_base_valido()
    data["location"]["latitude"] = 100.0  # > 90
    with pytest.raises(ConfigError, match=r"fuera de rango.*máx"):
        validar_config(data)


def test_validar_config_hora_inicio_ge_hora_fin() -> None:
    """hora_inicio >= hora_fin → ConfigError."""
    data = _config_base_valido()
    data["simulation"]["hora_inicio"] = 21
    data["simulation"]["hora_fin"] = 21
    with pytest.raises(ConfigError, match=r"hora_inicio.*debe ser <"):
        validar_config(data)


def test_validar_config_season_fechas_invertidas() -> None:
    """season.start_date > season.end_date → ConfigError."""
    data = _config_base_valido()
    data["season"]["start_date"] = "2026-10-15"
    data["season"]["end_date"] = "2026-04-01"
    with pytest.raises(ConfigError, match="posterior a"):
        validar_config(data)


def test_load_config_archivo_no_existe(tmp_path: Path) -> None:
    """load_config con ruta inexistente → ConfigError."""
    with pytest.raises(ConfigError, match="No existe el fichero"):
        load_config(tmp_path / "no_existe.yaml")


def test_load_config_contenido_no_mapa(tmp_path: Path) -> None:
    """YAML que no es un dict (lista, string...) → ConfigError."""
    f = tmp_path / "bad.yaml"
    f.write_text("- item1\n- item2")
    with pytest.raises(ConfigError, match="no es un mapa YAML"):
        load_config(f)


# ─── db.py: _sanitizar_json — ramas NaN/inf/numpy ────────────────────────────

def test_sanitizar_json_nan_inf() -> None:
    """NaN, +inf, -inf → None."""
    assert _sanitizar_json(float("nan")) is None
    assert _sanitizar_json(float("inf")) is None
    assert _sanitizar_json(float("-inf")) is None


def test_sanitizar_json_escalares_numpy() -> None:
    """np.float64, np.int64, np.bool_ → tipos Python nativos."""
    assert type(_sanitizar_json(np.float64(3.14))) is float
    assert type(_sanitizar_json(np.int64(42))) is int
    assert type(_sanitizar_json(np.bool_(True))) is bool
    assert _sanitizar_json(np.float64(3.14)) == 3.14
    assert _sanitizar_json(np.int64(42)) == 42
    assert _sanitizar_json(np.bool_(True)) is True


def test_sanitizar_json_dict_recursivo() -> None:
    """Dicts anidados se recorren recursivamente."""
    entrada = {"a": float("nan"), "b": {"c": np.float64(2.5), "d": [1, float("inf")]}}
    salida = _sanitizar_json(entrada)
    assert salida["a"] is None
    assert salida["b"]["c"] == 2.5
    assert salida["b"]["d"] == [1, None]


def test_sanitizar_json_list_tuple() -> None:
    """Listas y tuplas se recorren recursivamente."""
    assert _sanitizar_json([float("nan"), np.int64(7)]) == [None, 7]
    assert _sanitizar_json((float("inf"), 2)) == [None, 2]


# ─── db.py: save_forecast — validación de columnas ───────────────────────────

def test_save_forecast_columnas_faltantes(db: Database) -> None:
    """df sin columnas requeridas → ValueError claro."""
    df = pd.DataFrame({"hour": [0, 1], "temp_c": [20.0, 21.0]})  # faltan rh_pct, wind_ms...
    with pytest.raises(ValueError, match="sin columnas requeridas"):
        db.save_forecast("2026-07-15", df)


# ─── db.py: save_season_runs — validación y rollback (línea 220, 367) ────────

def test_save_season_runs_valida_fecha_vacia(db: Database) -> None:
    """date string vacío → ValueError."""
    fila = {"date": "  ", "window_start": "16:00"}
    with pytest.raises(ValueError, match="date"):
        db.save_season_runs("2026-06-01", "2026-06-02", [fila])


def test_save_season_runs_valida_no_dict(db: Database) -> None:
    """Elemento de rows que no es dict → ValueError con índice."""
    with pytest.raises(ValueError, match=r"rows\[0\]"):
        db.save_season_runs("2026-06-01", "2026-06-02", ["no-soy-dict"])


def test_save_season_runs_rollback_si_falla_serializacion(db: Database) -> None:
    """Error de serialización a mitad → rollback total (estado previo intacto)."""
    # Insertar filas válidas primero
    db.save_season_runs("2026-06-01", "2026-06-03", [
        {"date": "2026-06-01", "prob_ventana": 0.9},
        {"date": "2026-06-02", "prob_ventana": 0.8},
    ])
    # Ahora intento con una fila mala (set no serializable)
    filas_malas = [
        {"date": "2026-06-01", "prob_ventana": 0.9},
        {"date": "2026-06-02", "prob_ventana": 0.8},
        {"date": "2026-06-03", "prob_ventana": {1, 2}},  # set → falla JSON
    ]
    with pytest.raises(sqlite3.Error):
        db.save_season_runs("2026-06-01", "2026-06-03", filas_malas)
    # Estado previo intacto
    df = db.get_season_runs("2026-06-01", "2026-06-03")
    assert len(df) == 2
    assert df["date"].tolist() == ["2026-06-01", "2026-06-02"]


# ─── weather.py: get_json_con_reintentos / fetch_forecast — errores de red ───

@patch("time.sleep")
@patch("src.weather.requests.get")
def test_get_json_con_reintentos_json_decode_error_no_reintenta(
    mock_get: MagicMock, mock_sleep: MagicMock
) -> None:
    """JSONDecodeError → WeatherDataError SIN reintentos."""
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.side_effect = requests.exceptions.JSONDecodeError("Expecting value", "", 0)
    mock_get.return_value = resp

    from src.weather import RedCfg
    red = RedCfg(timeout_s=5.0, retries=3, backoff_base_s=0.0)

    with pytest.raises(WeatherDataError, match="no-JSON"):
        get_json_con_reintentos("http://test", {}, red=red, contexto="test")

    mock_get.assert_called_once()
    mock_sleep.assert_not_called()


@patch("time.sleep")
@patch("src.weather.requests.get")
def test_get_json_con_reintentos_value_error_no_reintenta(
    mock_get: MagicMock, mock_sleep: MagicMock
) -> None:
    """ValueError en parseo → WeatherDataError SIN reintentos."""
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.side_effect = ValueError("dato inválido")
    mock_get.return_value = resp

    from src.weather import RedCfg
    red = RedCfg(timeout_s=5.0, retries=3, backoff_base_s=0.0)

    with pytest.raises(WeatherDataError, match="no-JSON"):
        get_json_con_reintentos("http://test", {}, red=red, contexto="test")

    mock_get.assert_called_once()
    mock_sleep.assert_not_called()


@patch("time.sleep")
@patch("src.weather.requests.get")
def test_fetch_forecast_timeout_lanza_network_error(
    mock_get: MagicMock, mock_sleep: MagicMock
) -> None:
    """Timeout → WeatherNetworkError (reintentable)."""
    mock_get.side_effect = requests.Timeout("timeout")

    with pytest.raises(WeatherNetworkError, match="Open-Meteo"):
        fetch_forecast(37.9, -4.75, "2026-07-15", timeout_s=1, retries=2, backoff_base_s=0.0)

    assert mock_get.call_count == 2


@patch("time.sleep")
@patch("src.weather.requests.get")
def test_fetch_forecast_too_many_redirects(
    mock_get: MagicMock, mock_sleep: MagicMock
) -> None:
    """TooManyRedirects → WeatherNetworkError."""
    mock_get.side_effect = requests.exceptions.TooManyRedirects("redirect loop")

    with pytest.raises(WeatherNetworkError):
        fetch_forecast(37.9, -4.75, "2026-07-15", timeout_s=5, retries=2, backoff_base_s=0.0)


# ─── weather.py: resuelve_red — kwargs explícitos > cfg > defecto ────────────

def test_resuelve_red_kwargs_explicitos_ganan() -> None:
    """kwargs explícitos tienen prioridad sobre cfg.network."""
    cfg = load_config()
    red = resuelve_red(cfg, "timeout_s", 10.0, timeout_s=7.5, retries=4, backoff_base_s=0.1)
    assert red.timeout_s == 7.5
    assert red.retries == 4
    assert red.backoff_base_s == 0.1


def test_resuelve_red_cfg_gana_sobre_defecto() -> None:
    """cfg.network gana sobre defecto si no hay kwargs."""
    cfg = load_config()
    # Asegurar que cfg tiene valores distintos del defecto
    cfg.network.timeout_s = 9.0
    cfg.network.retries = 5
    cfg.network.backoff_base_s = 0.2
    red = resuelve_red(cfg, "timeout_s", 10.0)
    assert red.timeout_s == 9.0
    assert red.retries == 5
    assert red.backoff_base_s == 0.2


def test_resuelve_red_defecto_si_todo_none(tmp_path: Path) -> None:
    """Si cfg=None y sin kwargs → usa valores de config.yaml (no los defectos de la firma)."""
    # Cuando cfg=None, resuelve_red carga load_config() y usa cfg.network
    red = resuelve_red(None, "timeout_s", 12.0, timeout_s=None, retries=None, backoff_base_s=None)
    # Valores por defecto de config.yaml
    assert red.timeout_s == 30.0
    assert red.retries == 3
    assert red.backoff_base_s == 0.5


# ─── historical.py: _vacio, _descargar_tramo (líneas 104, 142, 155, 216, 277) ─
# Nota: historical.py usa red real; estos tests mockean la capa baja

@patch("src.historical.get_json_con_reintentos")
def test_fetch_archive_tramo_sin_serie_horaria_lanza_data_error(
    mock_get_json: MagicMock
) -> None:
    """Tramo sin 'hourly' → WeatherDataError."""
    mock_get_json.return_value = {"otra_clave": "valor"}
    from src.historical import _descargar_tramo
    with pytest.raises(WeatherDataError, match="no devolvió serie horaria"):
        _descargar_tramo("2026-06-01", "2026-06-01", 37.9, -4.75, "Europe/Madrid")


@patch("src.historical.get_json_con_reintentos")
def test_fetch_archive_tramo_horas_invalidas_se_saltan(
    mock_get_json: MagicMock
) -> None:
    """Marcas de tiempo mal formadas se ignoran (línea 155)."""
    mock_get_json.return_value = {
        "hourly": {
            "time": ["2026-06-01T00:00", "malformado", "2026-06-01T02:00"],
            "temperature_2m": [20.0, 21.0, 22.0],
            "relative_humidity_2m": [50.0, 51.0, 52.0],
            "wind_speed_10m": [1.0, 1.1, 1.2],
            "wind_direction_10m": [90.0, 90.0, 90.0],
            "shortwave_radiation": [100.0, 101.0, 102.0],
        }
    }
    from src.historical import _descargar_tramo
    filas = _descargar_tramo("2026-06-01", "2026-06-01", 37.9, -4.75, "Europe/Madrid")
    # Solo 2 filas válidas (la malformada se salta)
    assert len(filas) == 2


@patch("src.historical.get_json_con_reintentos")
def test_fetch_archive_valores_none_se_convierten_nan(
    mock_get_json: MagicMock
) -> None:
    """Valores None en la API → NaN (línea 162)."""
    mock_get_json.return_value = {
        "hourly": {
            "time": ["2026-06-01T00:00", "2026-06-01T01:00"],
            "temperature_2m": [20.0, None],
            "relative_humidity_2m": [50.0, 51.0],
            "wind_speed_10m": [1.0, 1.1],
            "wind_direction_10m": [90.0, 90.0],
            "shortwave_radiation": [100.0, 101.0],
        }
    }
    from src.historical import _descargar_tramo
    filas = _descargar_tramo("2026-06-01", "2026-06-01", 37.9, -4.75, "Europe/Madrid")
    assert math.isnan(filas[1]["temp_c"])


def test_iter_days_rango_vacio() -> None:
    """iter_days con DataFrame vacío → no itera nada."""
    from src.historical import iter_days
    df = pd.DataFrame(columns=["date", "hour", "temp_c", "rh_pct", "wind_ms",
                                "wind_dir_deg", "radiation_w_m2"])
    resultados = list(iter_days(df))
    assert resultados == []


def test_calidad_datos_rango_invalido() -> None:
    """calidad_datos con start > end → ValueError."""
    from src.historical import calidad_datos
    df = pd.DataFrame()
    with pytest.raises(ValueError, match="posterior a"):
        calidad_datos(df, "2026-06-10", "2026-06-01")


# ─── pipeline.py: _ensure_forecast — descarga si no existe (líneas 30-32) ─────

@patch("src.pipeline.weather.fetch_forecast")
def test_ensure_forecast_descarga_si_no_existe(mock_fetch: MagicMock, db: Database, cfg: Config) -> None:
    """Si no hay previsión en DB, la descarga y guarda."""
    from src.pipeline import _ensure_forecast
    mock_fetch.return_value = pd.DataFrame({
        "hour": list(range(24)),
        "temp_c": [20.0] * 24,
        "rh_pct": [50.0] * 24,
        "wind_ms": [1.0] * 24,
        "wind_dir_deg": [90.0] * 24,
        "radiation_w_m2": [100.0] * 24,
    })
    df = _ensure_forecast(db, "2026-07-20", cfg)
    assert df is not None
    assert len(df) == 24
    mock_fetch.assert_called_once()


# ─── pipeline.py: _fase_actual — hora_veredicto fuera de rango (línea 126) ───

def test_fase_actual_hora_veredicto_despues_de_fin_sim(cfg: Config, dia_verano_cordoba: pd.DataFrame) -> None:
    """hora_veredicto > última hora simulada → usa la última fila (línea 152)."""
    # Simular día completo
    from src import physics
    from src.pipeline import _fase_actual
    physics.concentrations_over_day(dia_verano_cordoba, cfg)
    # Hora 22 está fuera del rango simulado (6-21)
    fase, _desc = _fase_actual(dia_verano_cordoba, cfg, None, 22)
    # Debe usar la última hora simulada (21)
    assert isinstance(fase, int)
    assert 0 <= fase <= 3


# ─── assimilation.py: compute_bias / apply_bias (líneas 35, 38) ──────────────

def test_compute_bias_sin_lecturas_devuelve_vacio() -> None:
    """readings_df vacío o None → bias vacío."""
    from src.assimilation import compute_bias
    forecast = pd.DataFrame({"hour": [6, 12, 18], "temp_c": [20, 30, 25],
                             "rh_pct": [60, 40, 50], "wind_ms": [1, 2, 1]})
    assert compute_bias(forecast, pd.DataFrame()) == {}
    assert compute_bias(forecast, None) == {}


def test_compute_bias_variable_sin_columna_en_lecturas() -> None:
    """Si la lectura no tiene la columna correspondiente, se ignora esa variable."""
    from src.assimilation import compute_bias
    forecast = pd.DataFrame({"hour": [12], "temp_c": [30.0], "rh_pct": [40.0], "wind_ms": [2.0]})
    readings = pd.DataFrame({"reading_time": ["12:00"], "t_ambiente_c": [32.0]})  # sin rh_pct, wind_ms
    bias = compute_bias(forecast, readings, max_hours_back=6)
    assert "temp_c" in bias
    assert "rh_pct" not in bias
    assert "wind_ms" not in bias


def test_apply_bias_hr_clip_0_100() -> None:
    """apply_bias recorta HR a [0, 100]."""
    from src.assimilation import apply_bias
    forecast = pd.DataFrame({"hour": [12], "rh_pct": [95.0]})
    bias = {"rh_pct": 10.0}  # 95+10=105 → clip a 100
    out = apply_bias(forecast, bias)
    assert out.loc[0, "rh_pct"] == 100.0


def test_apply_bias_wind_clip_ge_0() -> None:
    """apply_bias recorta viento a ≥0."""
    from src.assimilation import apply_bias
    forecast = pd.DataFrame({"hour": [12], "wind_ms": [1.0]})
    bias = {"wind_ms": -5.0}  # 1-5=-4 → clip a 0
    out = apply_bias(forecast, bias)
    assert out.loc[0, "wind_ms"] == 0.0


# ─── markov.py: propagar — n_horas > matrices + 1 (línea 183) ────────────────

def test_propagar_arrastra_ultima_si_faltan_matrices() -> None:
    """Si n_horas > len(matrices)+1, arrastra la última distribución."""
    import numpy as np

    from src.markov import propagar
    # 2 matrices para 3 horas; pedimos 5 horas
    matrices = np.array([
        [[0.5, 0.5, 0, 0, 0], [0, 1, 0, 0, 0], [0, 0, 1, 0, 0], [0, 0, 0, 1, 0], [0, 0, 0, 0, 1]],
        [[0.2, 0.8, 0, 0, 0], [0, 0.5, 0.5, 0, 0], [0, 0, 0.5, 0.5, 0], [0, 0, 0, 0.5, 0.5], [0, 0, 0, 0, 1]],
    ])
    pi = propagar(matrices, n_horas=5, estado_inicial=0)
    assert pi.shape == (5, 5)
    # horas 3 y 4 deben ser iguales a hora 2 (última matriz aplicada)
    np.testing.assert_array_almost_equal(pi[3], pi[2])
    np.testing.assert_array_almost_equal(pi[4], pi[2])


# ─── montecarlo.py: simulate_ensemble — base vacía (líneas 239-240) ──────────

def test_simulate_ensemble_base_vacia_devuelve_vacio(cfg: Config) -> None:
    """Si el forecast filtrado queda vacío, devuelve EnsembleResult vacío."""
    from src.montecarlo import simulate_ensemble
    df_vacio = pd.DataFrame(columns=["hour", "temp_c", "rh_pct", "wind_ms",
                                      "wind_dir_deg", "radiation_w_m2"])
    ens = simulate_ensemble(df_vacio, cfg, n_iter=100)
    assert ens.hours.size == 0
    assert ens.c_g_l.shape == (100, 0)
    assert ens.valid.sum() == 0


# ─── montecarlo.py: simulate_day_desde_ensemble — sin ventana (líneas 321, 324, 344) ──

def test_simulate_day_desde_ensemble_sin_ventana(cfg: Config, dia_nublado_humedo: pd.DataFrame) -> None:
    """Día sin ventana → DayResult con NaN y prob_ventana=0."""
    from src.montecarlo import simulate_day_desde_ensemble, simulate_ensemble
    ens = simulate_ensemble(dia_nublado_humedo, cfg, n_iter=200)
    r = simulate_day_desde_ensemble(ens)
    assert math.isnan(r.median_hour)
    assert math.isnan(r.ci_low)
    assert math.isnan(r.ci_high)
    assert r.prob_ventana == 0.0
    assert r.hist_hours.size == 0
    assert math.isnan(r.window_start_median)
    assert math.isnan(r.window_end_median)


# ─── Fixture db reutilizada ───────────────────────────────────────────────────

@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "test_cov.db")
    database.init_schema()
    return database
