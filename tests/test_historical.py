"""Tests del cliente histórico (src/historical.py) — red simulada + integración real.

Cubre el contrato de la docstring: parseo con mock, tramos mensuales concatenados,
iter_days (contrato de un día), calidad_datos y un rango real de integración.

NOTA (auditoría G5): la petición HTTP vive en el helper compartido
src.weather.get_json_con_reintentos, por eso los mocks se parchean sobre
`src.weather.requests.get` (requests es un módulo único: el patch afecta a
cualquier cliente que lo use).
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests

from src.errors import WeatherDataError, WeatherNetworkError
from src.historical import API_URL, COLUMNAS, COLUMNAS_DIA, calidad_datos, fetch_archive, iter_days

INICIO = "2026-06-01"
FIN = "2026-06-07"
FECHA = "2026-07-15"


# ---------------------------------------------------------------------------
# Helpers de red simulada
# ---------------------------------------------------------------------------
def _payload_rango(start: str, end: str) -> dict:
    """Payload con la forma real de Open-Meteo Archive para [start, end] (24 h/día).

    Los valores dependen solo de la hora para poder asertarlos con precisión.
    """
    fechas: list[str] = []
    d = date.fromisoformat(start)
    fin = date.fromisoformat(end)
    while d <= fin:
        fechas.append(d.isoformat())
        d += timedelta(days=1)
    horas = list(range(24))
    return {
        "latitude": 37.9,
        "longitude": -4.75,
        "timezone": "Europe/Madrid",
        "hourly": {
            "time": [f"{f}T{h:02d}:00" for f in fechas for h in horas],
            "temperature_2m": [15.0 + h * 0.5 for h in horas] * len(fechas),
            "relative_humidity_2m": [90.0 - h * 2.0 for h in horas] * len(fechas),
            "wind_speed_10m": [0.5 + h * 0.1 for h in horas] * len(fechas),
            "wind_direction_10m": [180.0] * (24 * len(fechas)),
            "shortwave_radiation": [max(0.0, 800.0 - abs(h - 13) * 100.0)
                                    for h in horas] * len(fechas),
        },
    }


def _respuesta_mock(payload: dict) -> MagicMock:
    """Fake de requests.Response con .json() y .raise_for_status()."""
    resp = MagicMock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


def _df_dias(fechas: list[str], horas_por_dia: dict[str, list[int]] | None = None) -> pd.DataFrame:
    """DataFrame sintético con columnas del contrato para las fechas dadas."""
    filas: list[dict] = []
    for f in fechas:
        horas = (horas_por_dia or {}).get(f, list(range(24)))
        for h in horas:
            filas.append({
                "date": f, "hour": h, "temp_c": 20.0 + h * 0.5, "rh_pct": 80.0 - h,
                "wind_ms": 1.0, "wind_dir_deg": 135.0, "radiation_w_m2": 400.0,
            })
    return pd.DataFrame(filas, columns=COLUMNAS)


def _rango_fechas(start: str, end: str) -> list[str]:
    fechas, d, fin = [], date.fromisoformat(start), date.fromisoformat(end)
    while d <= fin:
        fechas.append(d.isoformat())
        d += timedelta(days=1)
    return fechas


# ---------------------------------------------------------------------------
# fetch_archive — parseo con requests.get simulado
# ---------------------------------------------------------------------------
@patch("src.weather.requests.get")
def test_parseo_columnas_exactas_tipos_y_multi_dia(mock_get: MagicMock) -> None:
    """El parseo devuelve exactamente las columnas del contrato, tipos correctos y `date`."""
    mock_get.return_value = _respuesta_mock(_payload_rango("2026-06-01", "2026-06-02"))

    df = fetch_archive("2026-06-01", "2026-06-02", 37.8882, -4.7794)

    assert list(df.columns) == COLUMNAS
    assert len(df) == 48  # 2 días × 24 h
    assert df["date"].dtype == object or pd.api.types.is_string_dtype(df["date"])
    assert df["date"].unique().tolist() == ["2026-06-01", "2026-06-02"]
    assert pd.api.types.is_integer_dtype(df["hour"])
    assert sorted(df[df["date"] == "2026-06-01"]["hour"].tolist()) == list(range(24))
    for col in COLUMNAS[2:]:
        assert pd.api.types.is_float_dtype(df[col]), f"{col} debe ser float"
    primera = df[df["date"] == "2026-06-01"].iloc[0]
    assert primera["hour"] == 0
    assert primera["temp_c"] == pytest.approx(15.0)
    assert primera["rh_pct"] == pytest.approx(90.0)
    assert primera["wind_ms"] == pytest.approx(0.5)
    assert primera["wind_dir_deg"] == pytest.approx(180.0)
    assert primera["radiation_w_m2"] == pytest.approx(0.0)
    # el orden cronológico global se respeta
    claves = list(zip(df["date"], df["hour"], strict=False))
    assert claves == sorted(claves)


@patch("src.weather.requests.get")
def test_parametros_de_llamada_open_meteo_archive(mock_get: MagicMock) -> None:
    """La llamada HTTP usa el endpoint y los parámetros exactos del contrato."""
    mock_get.return_value = _respuesta_mock(_payload_rango(FECHA, FECHA))

    fetch_archive(FECHA, FECHA, 37.8882, -4.7794, timezone="Europe/Madrid")

    mock_get.assert_called_once()
    args, kwargs = mock_get.call_args
    assert args[0] == API_URL
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
def test_rango_largo_se_descarga_en_tramos_mensuales(mock_get: MagicMock) -> None:
    """Un rango de varios meses hace UNA petición por mes, con los tramos exactos."""
    def responder(*_args, **kwargs):
        p = kwargs["params"]
        return _respuesta_mock(_payload_rango(p["start_date"], p["end_date"]))

    mock_get.side_effect = responder

    df = fetch_archive("2026-04-15", "2026-06-10", 37.8882, -4.7794)

    tramos = [(c[1]["params"]["start_date"], c[1]["params"]["end_date"])
              for c in mock_get.call_args_list]
    assert tramos == [
        ("2026-04-15", "2026-04-30"),
        ("2026-05-01", "2026-05-31"),
        ("2026-06-01", "2026-06-10"),
    ]
    assert len(df) == (16 + 31 + 10) * 24
    assert df["date"].iloc[0] == "2026-04-15"
    assert df["date"].iloc[-1] == "2026-06-10"


@patch("src.weather.requests.get")
def test_tramos_concatenados_sin_duplicados_ni_desorden(mock_get: MagicMock) -> None:
    """Aunque los tramos se solapen (payload repetido), el resultado no duplica ni desordena."""
    # Cada tramo devuelve SIEMPRE el mismo rango amplio → duplicados entre peticiones.
    mock_get.return_value = _respuesta_mock(_payload_rango("2026-04-01", "2026-05-31"))

    df = fetch_archive("2026-04-15", "2026-05-10", 37.8882, -4.7794)

    claves = list(zip(df["date"], df["hour"], strict=False))
    assert len(claves) == len(set(claves)), "hay filas duplicadas (date, hour)"
    assert claves == sorted(claves), "las filas no están ordenadas por (date, hour)"
    assert df["date"].min() >= "2026-04-15" and df["date"].max() <= "2026-05-10"
    assert len(df) == (16 + 10) * 24


@patch("src.weather.requests.get")
def test_filas_con_variables_todas_nulas_se_excluyen(mock_get: MagicMock) -> None:
    """Las filas con las 5 variables meteorológicas nulas se descartan (contrato)."""
    payload = _payload_rango(FECHA, FECHA)
    for nombre in ("temperature_2m", "relative_humidity_2m", "wind_speed_10m",
                   "wind_direction_10m", "shortwave_radiation"):
        payload["hourly"][nombre][13] = None  # hora 13 con todo nulo
    payload["hourly"]["temperature_2m"][14] = None  # hora 14 solo con T nula: se queda
    mock_get.return_value = _respuesta_mock(payload)

    df = fetch_archive(FECHA, FECHA, 37.8882, -4.7794)

    assert len(df) == 23
    assert 13 not in df["hour"].tolist()
    fila_14 = df[df["hour"] == 14].iloc[0]
    assert pd.isna(fila_14["temp_c"])
    assert fila_14["rh_pct"] == pytest.approx(90.0 - 14 * 2.0)


@patch("time.sleep")
@patch("src.weather.requests.get")
def test_error_http_lanza_weather_network_error(mock_get: MagicMock, mock_sleep: MagicMock) -> None:
    """Un error HTTP → WeatherNetworkError (reintentable), compatible con RuntimeError."""
    resp = MagicMock()
    resp.raise_for_status.side_effect = requests.HTTPError("500 Internal Server Error")
    mock_get.return_value = resp

    with pytest.raises(WeatherNetworkError, match="Open-Meteo"):
        fetch_archive(FECHA, FECHA, 37.8882, -4.7794, timeout_s=5, retries=2, backoff_base_s=0.0)
    assert mock_get.call_count == 2   # reintentos de red (G5)
    assert mock_sleep.call_count == 1


@patch("time.sleep")
@patch("src.weather.requests.get")
def test_error_de_red_lanza_weather_network_error(mock_get: MagicMock,
                                                  mock_sleep: MagicMock) -> None:
    """Un fallo de conexión → WeatherNetworkError tras agotar los reintentos (G5)."""
    mock_get.side_effect = requests.ConnectionError("sin conexión")

    with pytest.raises(WeatherNetworkError, match="Open-Meteo"):
        fetch_archive(FECHA, FECHA, 37.8882, -4.7794, timeout_s=5, retries=3, backoff_base_s=0.0)
    assert mock_get.call_count == 3
    assert mock_sleep.call_count == 2
    # compatibilidad M7: WeatherNetworkError sigue siendo RuntimeError
    with pytest.raises(RuntimeError, match="Open-Meteo"):
        fetch_archive(FECHA, FECHA, 37.8882, -4.7794, timeout_s=5, retries=1, backoff_base_s=0.0)


@patch("time.sleep")
@patch("src.weather.requests.get")
def test_reintentos_con_backoff_exponencial_hasta_el_exito(mock_get: MagicMock,
                                                           mock_sleep: MagicMock) -> None:
    """Falla 2 veces por red y a la 3ª funciona: 3 llamadas y esperas base·2^0, base·2^1."""
    def responder_ok(*_args, **_kwargs):
        return _respuesta_mock(_payload_rango(FECHA, FECHA))

    mock_get.side_effect = [
        requests.ConnectionError("caída 1"),
        requests.Timeout("caída 2"),
        responder_ok(),
    ]

    df = fetch_archive(FECHA, FECHA, 37.8882, -4.7794, timeout_s=5, retries=3, backoff_base_s=0.5)

    assert len(df) == 24
    assert mock_get.call_count == 3
    esperas = [llamada.args[0] for llamada in mock_sleep.call_args_list]
    assert len(esperas) == 2
    assert 0.5 <= esperas[0] <= 0.7    # base·2^0 + jitter U(0, 0.2)
    assert 1.0 <= esperas[1] <= 1.2    # base·2^1 + jitter U(0, 0.2)
    # el timeout de tramo es el del kwargs (no el de config)
    assert mock_get.call_args_list[0].kwargs["timeout"] == 5


@patch("time.sleep")
@patch("src.weather.requests.get")
def test_respuesta_sin_serie_horaria_lanza_weather_data_error(mock_get: MagicMock,
                                                              mock_sleep: MagicMock) -> None:
    """Una respuesta sin series horarias → WeatherDataError SIN reintentos (M7/G5)."""
    mock_get.return_value = _respuesta_mock({"reason": "Invalid API request"})

    with pytest.raises(WeatherDataError, match="Open-Meteo"):
        fetch_archive(FECHA, FECHA, 37.8882, -4.7794, timeout_s=5, retries=3, backoff_base_s=0.0)

    mock_get.assert_called_once()   # los datos malos NO se reintentan
    mock_sleep.assert_not_called()


def test_fecha_con_formato_invalido_lanza_value_error() -> None:
    """Una fecha mal formada se rechaza con ValueError antes de tocar la red."""
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        fetch_archive("15/06/2026", FECHA, 37.8882, -4.7794)


def test_rango_invertido_lanza_value_error() -> None:
    """Un rango con inicio posterior al fin se rechaza con ValueError."""
    with pytest.raises(ValueError, match="posterior"):
        fetch_archive("2026-06-10", "2026-06-01", 37.8882, -4.7794)


# ---------------------------------------------------------------------------
# iter_days
# ---------------------------------------------------------------------------
def _df_tres_dias() -> pd.DataFrame:
    """Tres días (uno incompleto y otro ausente) para probar el contrato de iter_days."""
    fechas = ["2026-06-02", "2026-06-01", "2026-06-04"]  # desordenadas a propósito
    df = _df_dias(fechas, {"2026-06-04": [9, 8, 7]})  # día incompleto desordenado
    # 2026-06-03 no tiene filas → debe omitirse
    return df.sample(frac=1.0, random_state=0).reset_index(drop=True)


def test_iter_days_contrato_de_un_dia() -> None:
    """Cada día tiene como máximo 24 filas, las columnas EXACTAS (sin `date`) y hour ordenado."""
    dias = list(iter_days(_df_tres_dias()))

    assert [f for f, _ in dias] == ["2026-06-01", "2026-06-02", "2026-06-04"]
    for _fecha, dia in dias:
        assert list(dia.columns) == COLUMNAS_DIA
        assert "date" not in dia.columns
        assert len(dia) <= 24
        assert dia["hour"].tolist() == sorted(dia["hour"].tolist())
        assert pd.api.types.is_integer_dtype(dia["hour"])
    assert len(dias[0][1]) == 24
    assert dias[2][0] == "2026-06-04"
    assert dias[2][1]["hour"].tolist() == [7, 8, 9]  # día incompleto reordenado


def test_iter_days_con_rango_de_fechas() -> None:
    """start_date/end_date recortan el rango (inclusivo) por ambos lados."""
    df = _df_tres_dias()

    dias = list(iter_days(df, "2026-06-02", "2026-06-03"))

    assert [f for f, _ in dias] == ["2026-06-02"]
    assert len(dias[0][1]) == 24


def test_iter_days_sin_filas_no_entra() -> None:
    """Un rango sin datos produce un iterador vacío (sin excepción)."""
    df = _df_tres_dias()

    assert list(iter_days(df, "2027-01-01", "2027-01-31")) == []
    assert list(iter_days(df[df["date"] > "2030-01-01"])) == []


# ---------------------------------------------------------------------------
# calidad_datos
# ---------------------------------------------------------------------------
def test_calidad_datos_rango_completo() -> None:
    """Si todos los días del rango tienen 24 horas → 'completo'."""
    df = _df_dias(_rango_fechas("2026-06-01", "2026-06-07"))

    assert calidad_datos(df, "2026-06-01", "2026-06-07") == "completo"


def test_calidad_datos_faltando_horas() -> None:
    """Falta una hora → 'parcial: 1 días incompletos' con la fecha como ejemplo."""
    fechas = _rango_fechas("2026-06-01", "2026-06-07")
    horas = {"2026-06-03": [h for h in range(24) if h != 13]}
    df = _df_dias(fechas, horas)

    txt = calidad_datos(df, "2026-06-01", "2026-06-07")

    assert txt.startswith("parcial: 1 días incompletos (ej: 2026-06-03")
    assert txt != "completo"


def test_calidad_datos_dia_ausente_cuenta_como_incompleto() -> None:
    """Un día sin filas en el rango también es incompleto."""
    fechas = [f for f in _rango_fechas("2026-06-01", "2026-06-07") if f != "2026-06-05"]
    df = _df_dias(fechas)

    txt = calidad_datos(df, "2026-06-01", "2026-06-07")

    assert txt == "parcial: 1 días incompletos (ej: 2026-06-05)"


def test_calidad_datos_max_tres_ejemplos() -> None:
    """Con más de 3 días incompletos se listan 3 ejemplos y se cierra con '...'."""
    fechas = _rango_fechas("2026-06-01", "2026-06-10")
    horas = {f: list(range(23)) for f in fechas}  # todos incompletos (23 h)
    df = _df_dias(fechas, horas)

    txt = calidad_datos(df, "2026-06-01", "2026-06-10")

    assert txt.startswith("parcial: 10 días incompletos (ej: ")
    assert txt.endswith(", ...)")
    assert "2026-06-01" in txt and "2026-06-03" in txt and "2026-06-04" not in txt


def test_calidad_datos_df_vacio() -> None:
    """Un df vacío en un rango de 7 días → parcial con 7 días incompletos."""
    df = _df_dias([])

    txt = calidad_datos(df, "2026-06-01", "2026-06-07")

    assert txt.startswith("parcial: 7 días incompletos")


# ---------------------------------------------------------------------------
# Integración real (red). Se salta con: -m "not integration"
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_integracion_semana_real_junio_2026() -> None:
    """Descarga real de una semana de junio de 2026 y valida rangos plausibles."""
    df = fetch_archive(INICIO, FIN, 37.8882, -4.7794, timezone="Europe/Madrid")

    assert list(df.columns) == COLUMNAS
    assert df["date"].unique().tolist() == _rango_fechas(INICIO, FIN)
    assert len(df) == 7 * 24, "ERA5 debe traer 24 horas por día"
    assert df["hour"].between(0, 23).all()
    assert df["rh_pct"].between(0, 100).all(), "HR fuera de [0, 100] %"
    assert df["temp_c"].between(-20, 55).all(), "T fuera de [-20, 55] °C"
    assert (df["wind_ms"] >= 0).all(), "Viento negativo"
    assert df["wind_dir_deg"].between(0, 360).all(), "Dirección fuera de [0, 360]°"
    assert (df["radiation_w_m2"] >= 0).all(), "Radiación negativa"
    assert calidad_datos(df, INICIO, FIN) == "completo"
    dias = list(iter_days(df, INICIO, FIN))
    assert len(dias) == 7
    assert all(list(d.columns) == COLUMNAS_DIA for _, d in dias)
    print(f"\n[integración] ERA5 {INICIO}..{FIN}: {len(df)} h · "
          f"T {df['temp_c'].min():.1f}..{df['temp_c'].max():.1f} °C · "
          f"HR mín {df['rh_pct'].min():.1f} % · V máx {df['wind_ms'].max():.2f} m/s")
