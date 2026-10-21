"""Cliente de previsión meteorológica — Open-Meteo (sin API key).

CONTRATO — a implementar por data-ingest. Firmas exactas:

    def fetch_forecast(latitude: float, longitude: float, date: str,
                       timezone: str = "Europe/Madrid") -> pd.DataFrame
        # Descarga la serie horaria del día `date` ("YYYY-MM-DD") para las coordenadas.
        # Endpoint: https://api.open-meteo.com/v1/forecast
        #   hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,shortwave_radiation
        #   wind_speed_unit=ms, timezone, start_date, end_date=date
        # Devuelve df con columnas EXACTAS:
        #   hour (int 0-23), temp_c (float), rh_pct (float), wind_ms (float),
        #   wind_dir_deg (float), radiation_w_m2 (float)
        # Solo las filas de `date` (Open-Meteo devuelve horas en la tz pedida).

Notas:
- Sin API key ni registro. Rate limit generoso; una llamada por día es nada.
- Manejar errores de red con excepción clara (RuntimeError con el mensaje).
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import requests

API_URL = "https://api.open-meteo.com/v1/forecast"

# Variables horarias en el orden en que Open-Meteo las devuelve y
# el nombre de columna interno que les asignamos (columnas EXACTAS del contrato).
_VARIABLES: list[tuple[str, str]] = [
    ("temperature_2m", "temp_c"),
    ("relative_humidity_2m", "rh_pct"),
    ("wind_speed_10m", "wind_ms"),
    ("wind_direction_10m", "wind_dir_deg"),
    ("shortwave_radiation", "radiation_w_m2"),
]

_COLUMNAS: list[str] = ["hour", *[col for _, col in _VARIABLES]]


def fetch_forecast(latitude: float, longitude: float, date: str,
                   timezone: str = "Europe/Madrid") -> pd.DataFrame:
    """Descarga la previsión horaria de Open-Meteo para el día `date` en las coordenadas dadas.

    Args:
        latitude: Latitud en grados decimales.
        longitude: Longitud en grados decimales.
        date: Día a descargar en formato "YYYY-MM-DD".
        timezone: Zona horaria IANA (por defecto "Europe/Madrid").

    Returns:
        DataFrame con 24 filas (0-23 h) y columnas EXACTAS:
        hour (int), temp_c, rh_pct, wind_ms, wind_dir_deg, radiation_w_m2 (float).

    Raises:
        ValueError: Si `date` no tiene formato "YYYY-MM-DD".
        RuntimeError: Si falla la red, el HTTP o la respuesta no contiene datos del día.
    """
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"Fecha inválida {date!r}: se espera formato YYYY-MM-DD.") from exc

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ",".join(nombre for nombre, _ in _VARIABLES),
        "wind_speed_unit": "ms",
        "timezone": timezone,
        "start_date": date,
        "end_date": date,
    }

    try:
        resp = requests.get(API_URL, params=params, timeout=30)
        resp.raise_for_status()
        datos = resp.json()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Error de red/HTTP descargando previsión de Open-Meteo para {date}: {exc}"
        ) from exc
    except ValueError as exc:  # respuesta no es JSON válido
        raise RuntimeError(
            f"Respuesta no-JSON de Open-Meteo para {date}: {exc}"
        ) from exc

    hourly = datos.get("hourly")
    if not isinstance(hourly, dict):
        raise RuntimeError(f"Open-Meteo no devolvió serie horaria para {date}.")

    horas_raw: list = hourly.get("time") or []
    filas: list[dict] = []
    for i, marca in enumerate(horas_raw):
        # Open-Meteo responde marcas locales "YYYY-MM-DDTHH:MM"; nos quedamos con `date`.
        if not isinstance(marca, str) or not marca.startswith(date):
            continue
        fila: dict = {"hour": int(marca[11:13])}
        for nombre, col in _VARIABLES:
            valores = hourly.get(nombre) or []
            if i >= len(valores) or valores[i] is None:
                raise RuntimeError(
                    f"Open-Meteo devolvió valores incompletos ({nombre}) para {date}."
                )
            fila[col] = float(valores[i])
        filas.append(fila)

    if not filas:
        raise RuntimeError(f"Open-Meteo no devolvió datos horarios para el día {date}.")

    df = pd.DataFrame(filas, columns=_COLUMNAS)
    df["hour"] = df["hour"].astype(int)
    for _, col in _VARIABLES:
        df[col] = df[col].astype(float)
    return df.sort_values("hour").reset_index(drop=True)
