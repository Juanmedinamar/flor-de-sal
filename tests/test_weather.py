"""Tests del cliente de previsión (src/weather.py) — con red simulada + integración real.

Cubre el contrato, los reintentos con backoff exponencial (auditoría G5) y las
excepciones tipadas (auditoría M7): WeatherNetworkError se reintenta,
WeatherDataError no.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
import requests

from src.config import load_config
from src.errors import WeatherDataError, WeatherNetworkError
from src.weather import API_URL, fetch_forecast

FECHA = "2026-07-15"
COLUMNAS_EXACTAS = ["hour", "temp_c", "rh_pct", "wind_ms", "wind_dir_deg", "radiation_w_m2"]


def _payload_horas() -> list[str]:
    """Marcas horarias locales de un día completo tal y como las devuelve Open-Meteo."""
    return [f"{FECHA}T{h:02d}:00" for h in range(24)]


def _payload_open_meteo() -> dict:
    """Payload de ejemplo con la forma real de la respuesta de Open-Meteo (24 h)."""
    return {
        "latitude": 37.9,
        "longitude": -4.75,
        "timezone": "Europe/Madrid",
        "hourly": {
            "time": _payload_horas(),
            "temperature_2m": [18.0 + h * 0.7 for h in range(24)],
            "relative_humidity_2m": [85.0 - h * 1.5 for h in range(24)],
            "wind_speed_10m": [0.5 + h * 0.1 for h in range(24)],
            "wind_direction_10m": [90.0] * 24,
            "shortwave_radiation": [max(0.0, 800.0 - abs(h - 13) * 120) for h in range(24)],
        },
    }


def _respuesta_mock(payload: dict) -> MagicMock:
    """Fake de requests.Response con .json() y .raise_for_status()."""
    resp = MagicMock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# Tests con red simulada (sin dependencia de red en CI)
# ---------------------------------------------------------------------------
@patch("src.weather.requests.get")
def test_parseo_columnas_exactas_tipos_y_24_filas(mock_get: MagicMock) -> None:
    """El parseo devuelve exactamente las columnas del contrato, 24 filas y tipos correctos."""
    mock_get.return_value = _respuesta_mock(_payload_open_meteo())

    df = fetch_forecast(37.8882, -4.7794, FECHA)

    assert list(df.columns) == COLUMNAS_EXACTAS
    assert len(df) == 24
    assert df["hour"].tolist() == list(range(24))
    assert pd.api.types.is_integer_dtype(df["hour"])
    for col in COLUMNAS_EXACTAS[1:]:
        assert pd.api.types.is_float_dtype(df[col]), f"{col} debe ser float"
    # valores de la hora 0 correctos
    assert df.loc[0, "temp_c"] == pytest.approx(18.0)
    assert df.loc[0, "rh_pct"] == pytest.approx(85.0)
    assert df.loc[0, "wind_ms"] == pytest.approx(0.5)


@patch("src.weather.requests.get")
def test_parametros_de_llamada_open_meteo(mock_get: MagicMock) -> None:
    """La llamada HTTP usa el endpoint y los parámetros exactos del contrato."""
    mock_get.return_value = _respuesta_mock(_payload_open_meteo())

    fetch_forecast(37.8882, -4.7794, FECHA, timezone="Europe/Madrid")

    mock_get.assert_called_once()
    url, kwargs = mock_get.call_args
    assert url[0] == API_URL
    params = kwargs["params"]
    assert params["latitude"] == 37.8882
    assert params["longitude"] == -4.7794
    assert params["wind_speed_unit"] == "ms"
    assert params["timezone"] == "Europe/Madrid"
    assert params["start_date"] == FECHA
    assert params["end_date"] == FECHA
    assert params["hourly"] == (
        "temperature_2m,relative_humidity_2m,wind_speed_10m,"
        "wind_direction_10m,shortwave_radiation"
    )


@patch("src.weather.requests.get")
def test_filtrado_de_la_fecha_pedida(mock_get: MagicMock) -> None:
    """Si Open-Meteo devolviese marcas de otro día, se quedan solo las de `date`."""
    payload = _payload_open_meteo()
    payload["hourly"]["time"] = [f"2026-07-16T{h:02d}:00" for h in range(3)] + _payload_horas()
    for nombre, valores in payload["hourly"].items():
        if nombre != "time":
            payload["hourly"][nombre] = [0.0] * 3 + list(valores)
    mock_get.return_value = _respuesta_mock(payload)

    df = fetch_forecast(37.8882, -4.7794, FECHA)

    assert len(df) == 24
    assert df["hour"].tolist() == list(range(24))


@patch("time.sleep")
@patch("src.weather.requests.get")
def test_error_http_lanza_weather_network_error(mock_get: MagicMock, mock_sleep: MagicMock) -> None:
    """Un error HTTP (p. ej. 429/500) → WeatherNetworkError (reintentable, M7/G5)."""
    resp = MagicMock()
    resp.raise_for_status.side_effect = requests.HTTPError("429 Too Many Requests")
    mock_get.return_value = resp

    with pytest.raises(WeatherNetworkError, match="Open-Meteo"):
        fetch_forecast(37.8882, -4.7794, FECHA, timeout_s=5, retries=2, backoff_base_s=0.0)
    assert mock_get.call_count == 2       # se reintenta hasta agotar intentos
    assert mock_sleep.call_count == 1


@patch("time.sleep")
@patch("src.weather.requests.get")
def test_error_de_red_lanza_weather_network_error(mock_get: MagicMock,
                                                  mock_sleep: MagicMock) -> None:
    """Un fallo de conexión → WeatherNetworkError, que sigue siendo RuntimeError (M7)."""
    mock_get.side_effect = requests.ConnectionError("sin conexión")

    with pytest.raises(WeatherNetworkError, match="Open-Meteo"):
        fetch_forecast(37.8882, -4.7794, FECHA, timeout_s=5, retries=3, backoff_base_s=0.0)
    assert mock_get.call_count == 3
    # compatibilidad: los llamantes antiguos que capturan RuntimeError siguen funcionando
    with pytest.raises(RuntimeError):
        fetch_forecast(37.8882, -4.7794, FECHA, timeout_s=5, retries=1, backoff_base_s=0.0)


@patch("time.sleep")
@patch("src.weather.requests.get")
def test_respuesta_sin_datos_del_dia_lanza_weather_data_error(mock_get: MagicMock,
                                                              mock_sleep: MagicMock) -> None:
    """Una respuesta sin series horarias → WeatherDataError SIN reintentos (M7/G5)."""
    mock_get.return_value = _respuesta_mock({"reason": "Invalid API request"})

    with pytest.raises(WeatherDataError, match="Open-Meteo"):
        fetch_forecast(37.8882, -4.7794, FECHA, timeout_s=5, retries=3, backoff_base_s=0.0)

    mock_get.assert_called_once()   # los datos malos NO se reintentan
    mock_sleep.assert_not_called()


@patch("time.sleep")
@patch("src.weather.requests.get")
def test_json_invalido_lanza_weather_data_error_sin_reintentos(mock_get: MagicMock,
                                                               mock_sleep: MagicMock) -> None:
    """Una respuesta que no es JSON (p. ej. HTML de un proxy) no se reintenta (M7/G5)."""
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.side_effect = requests.exceptions.JSONDecodeError("Expecting value", "", 0)
    mock_get.return_value = resp

    with pytest.raises(WeatherDataError, match="no-JSON"):
        fetch_forecast(37.8882, -4.7794, FECHA, timeout_s=5, retries=3, backoff_base_s=0.0)

    mock_get.assert_called_once()
    mock_sleep.assert_not_called()


@patch("time.sleep")
@patch("src.weather.requests.get")
def test_reintentos_con_backoff_exponencial_hasta_el_exito(mock_get: MagicMock,
                                                           mock_sleep: MagicMock) -> None:
    """Falla 2 veces por red y a la 3ª funciona: 3 llamadas y esperas base·2^0, base·2^1."""
    mock_get.side_effect = [
        requests.ConnectionError("caída 1"),
        requests.ConnectionError("caída 2"),
        _respuesta_mock(_payload_open_meteo()),
    ]

    df = fetch_forecast(37.8882, -4.7794, FECHA, timeout_s=5, retries=3, backoff_base_s=0.5)

    assert len(df) == 24   # la 3ª petición devuelve datos válidos
    assert mock_get.call_count == 3
    assert mock_sleep.call_count == 2
    esperas = [llamada.args[0] for llamada in mock_sleep.call_args_list]
    assert 0.5 <= esperas[0] <= 0.7    # base·2^0 + jitter U(0, 0.2)
    assert 1.0 <= esperas[1] <= 1.2    # base·2^1 + jitter U(0, 0.2)
    # el timeout usado es el pasado explícito (no el de config)
    assert mock_get.call_args_list[0].kwargs["timeout"] == 5


@patch("src.weather.requests.get")
def test_fetch_forecast_usa_los_parametros_de_cfg_network(mock_get: MagicMock) -> None:
    """Sin kwargs explícitos, timeout/retries/backoff salen de cfg.network (G5)."""
    cfg_local = load_config()
    cfg_local.network.timeout_s = 7.0
    cfg_local.network.retries = 4
    cfg_local.network.backoff_base_s = 0.0
    mock_get.side_effect = requests.ConnectionError("sin conexión")

    with patch("time.sleep") as mock_sleep, pytest.raises(WeatherNetworkError):
        fetch_forecast(37.8882, -4.7794, FECHA, cfg=cfg_local)

    assert mock_get.call_count == 4                    # retries del config
    assert mock_get.call_args_list[0].kwargs["timeout"] == 7.0
    assert mock_sleep.call_count == 3


def test_fecha_con_formato_invalido_lanza_value_error() -> None:
    """Una fecha mal formada se rechaza con ValueError antes de tocar la red."""
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        fetch_forecast(37.8882, -4.7794, "15/07/2026")


# ---------------------------------------------------------------------------
# Test de integración real (red). Se salta con: -m "not integration"
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_integracion_descarga_real_cordoba() -> None:
    """Descarga real del día de hoy para la salina de Córdoba y valida rangos físicos."""
    hoy = datetime.now(ZoneInfo("Europe/Madrid")).strftime("%Y-%m-%d")

    df = fetch_forecast(37.8882, -4.7794, hoy, timezone="Europe/Madrid")

    assert list(df.columns) == COLUMNAS_EXACTAS
    assert len(df) == 24
    assert df["hour"].tolist() == list(range(24))
    assert df["rh_pct"].between(0, 100).all(), "HR fuera de [0, 100] %"
    assert df["temp_c"].between(-20, 55).all(), "T fuera de [-20, 55] °C"
    assert (df["wind_ms"] >= 0).all(), "Viento negativo"
    assert (df["wind_dir_deg"] >= 0).all() and (df["wind_dir_deg"] <= 360).all()
    assert (df["radiation_w_m2"] >= 0).all()
    print(f"\n[integración] Córdoba {hoy}: T {df['temp_c'].min():.1f}..{df['temp_c'].max():.1f} °C, "
          f"HR mín {df['rh_pct'].min():.1f} %, V máx {df['wind_ms'].max():.2f} m/s")
