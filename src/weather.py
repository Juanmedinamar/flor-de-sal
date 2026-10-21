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

    Nota de auditoría G5: desde la implementación la firma admite, además,
    kwargs opcionales sin romper el contrato (por defecto toman cfg.network):
        *, cfg=None, timeout_s=None, retries=None, backoff_base_s=None

Notas:
- Sin API key ni registro. Rate limit generoso; una llamada por día es nada.
- Errores tipados (auditoría M7): :class:`src.errors.WeatherNetworkError` para
  red/HTTP/timeout (reintentable) y :class:`src.errors.WeatherDataError` para
  respuestas sin datos o no-JSON (NO reintentable). Ambas heredan de RuntimeError.
- Reintentos con backoff exponencial + jitter (auditoría G5) según `cfg.network`.
- Aquí vive el helper compartido de peticiones con reintentos; src/historical.py
  lo reutiliza para el archivo ERA5 (mismo cliente Open-Meteo).
"""
from __future__ import annotations

import random
import time
from datetime import datetime
from typing import Any, NamedTuple

import pandas as pd
import requests

from src.config import Config, load_config
from src.errors import WeatherDataError, WeatherNetworkError

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

# Jitter (s) añadido a la espera de backoff para desincronizar reintentos.
_JITTER_S = 0.2


class RedCfg(NamedTuple):
    """Parámetros del cliente HTTP: timeout (s), intentos totales y base de backoff (s)."""
    timeout_s: float
    retries: int
    backoff_base_s: float


def resuelve_red(cfg: Config | None, timeout_attr: str, timeout_defecto: float,
                 timeout_s: float | None = None, retries: int | None = None,
                 backoff_base_s: float | None = None) -> RedCfg:
    """Resuelve los parámetros de red: kwargs explícitos > cfg.network > load_config().

    Args:
        cfg: Configuración del proyecto; si es None se carga con load_config()
            (solo si falta algún parámetro explícito).
        timeout_attr: Clave del timeout en cfg.network ("timeout_s" o "archive_timeout_s").
        timeout_defecto: Timeout a usar si no hay config ni kwargs.
        timeout_s: Timeout explícito (prioridad sobre config).
        retries: Intentos totales explícitos (prioridad sobre config).
        backoff_base_s: Base del backoff explícita (prioridad sobre config).

    Returns:
        RedCfg resuelto (retries mínimo 1: el primer intento siempre existe).

    Raises:
        ConfigError: si cfg es None y config.yaml no carga/valida.
    """
    if cfg is None and (timeout_s is None or retries is None or backoff_base_s is None):
        cfg = load_config()
    net = cfg.network if cfg is not None else None

    def _valor(override: Any, clave: str, defecto: Any) -> Any:
        if override is not None:
            return override
        return net.get(clave, defecto) if net is not None else defecto

    return RedCfg(
        timeout_s=float(_valor(timeout_s, timeout_attr, timeout_defecto)),
        retries=max(1, int(_valor(retries, "retries", 1))),
        backoff_base_s=float(_valor(backoff_base_s, "backoff_base_s", 0.5)),
    )


def get_json_con_reintentos(url: str, params: dict[str, Any], *, red: RedCfg,
                            contexto: str) -> Any:
    """GET que devuelve el JSON decodificado, reintentando SOLO fallos de red (G5).

    Backoff exponencial con jitter: espera = backoff_base_s·2^intento + U(0, 0.2) s.
    Se reintenta únicamente :class:`WeatherNetworkError` (red/HTTP/timeout);
    :class:`WeatherDataError` (JSON inválido, respuesta sin datos) sale al primer
    intento — repetir la petición no arregla un dato malo y solo satura la API.

    Args:
        url: Endpoint HTTP.
        params: Query string de la petición.
        red: Timeout, intentos y base de backoff (:func:`resuelve_red`).
        contexto: Texto del error ("la previsión de Open-Meteo para 2026-07-15").

    Returns:
        Respuesta JSON decodificada.

    Raises:
        WeatherNetworkError: tras agotar `red.retries` intentos de red/HTTP.
        WeatherDataError: respuesta no-JSON (sin reintentos).
    """
    intentos = max(1, int(red.retries))
    ultimo_exc: requests.RequestException | None = None
    ultimo_msg = ""
    for intento in range(intentos):
        if intento:  # backoff exponencial + jitter entre intentos
            espera = red.backoff_base_s * (2 ** (intento - 1)) + random.uniform(0.0, _JITTER_S)
            time.sleep(espera)
        try:
            resp = requests.get(url, params=params, timeout=red.timeout_s)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.JSONDecodeError as exc:
            # Hereda de RequestException, pero es problema de DATOS → sin reintentos.
            raise WeatherDataError(f"Respuesta no-JSON descargando {contexto}: {exc}") from exc
        except requests.RequestException as exc:
            ultimo_exc, ultimo_msg = exc, f"Error de red/HTTP descargando {contexto}: {exc}"
        except ValueError as exc:  # otro fallo de parseo → dato, no red
            raise WeatherDataError(f"Respuesta no-JSON descargando {contexto}: {exc}") from exc
    raise WeatherNetworkError(ultimo_msg) from ultimo_exc


def fetch_forecast(latitude: float, longitude: float, date: str,
                   timezone: str = "Europe/Madrid", *,
                   cfg: Config | None = None,
                   timeout_s: float | None = None,
                   retries: int | None = None,
                   backoff_base_s: float | None = None) -> pd.DataFrame:
    """Descarga la previsión horaria de Open-Meteo para el día `date` en las coordenadas dadas.

    Args:
        latitude: Latitud en grados decimales.
        longitude: Longitud en grados decimales.
        date: Día a descargar en formato "YYYY-MM-DD".
        timezone: Zona horaria IANA (por defecto "Europe/Madrid").
        cfg: Configuración (por defecto load_config()); de ahí salen los parámetros
            de red de cfg.network (auditoría G5).
        timeout_s: Timeout explícito (prioridad sobre cfg.network.timeout_s).
        retries: Intentos totales (prioridad sobre cfg.network.retries).
        backoff_base_s: Base del backoff (prioridad sobre cfg.network.backoff_base_s).

    Returns:
        DataFrame con 24 filas (0-23 h) y columnas EXACTAS:
        hour (int), temp_c, rh_pct, wind_ms, wind_dir_deg, radiation_w_m2 (float).

    Raises:
        ValueError: Si `date` no tiene formato "YYYY-MM-DD".
        ConfigError: Si cfg es None y config.yaml no es válido.
        WeatherNetworkError: Red/HTTP/timeout tras agotar los reintentos (M7/G5).
        WeatherDataError: La respuesta no contiene datos del día (sin reintentos).
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

    red = resuelve_red(cfg, "timeout_s", 30.0, timeout_s, retries, backoff_base_s)
    datos = get_json_con_reintentos(
        API_URL, params, red=red, contexto=f"la previsión de Open-Meteo para {date}")

    if not isinstance(datos, dict):
        raise WeatherDataError(f"Open-Meteo no devolvió un objeto JSON para {date}.")
    hourly = datos.get("hourly")
    if not isinstance(hourly, dict):
        raise WeatherDataError(f"Open-Meteo no devolvió serie horaria para {date}.")

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
                raise WeatherDataError(
                    f"Open-Meteo devolvió valores incompletos ({nombre}) para {date}."
                )
            fila[col] = float(valores[i])
        filas.append(fila)

    if not filas:
        raise WeatherDataError(f"Open-Meteo no devolvió datos horarios para el día {date}.")

    df = pd.DataFrame(filas, columns=_COLUMNAS)
    df["hour"] = df["hour"].astype(int)
    for _, col in _VARIABLES:
        df[col] = df[col].astype(float)
    return df.sort_values("hour").reset_index(drop=True)
