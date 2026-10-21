"""Datos meteorológicos históricos — Open-Meteo Archive (ERA5, observado/reanálisis).

CONTRATO — a implementar por el agente `temporada`. Firmas exactas:

    def fetch_archive(start_date: str, end_date: str, latitude: float, longitude: float,
                      timezone: str = "Europe/Madrid") -> pd.DataFrame
        # Descarga el rango [start_date, end_date] ("YYYY-MM-DD") de
        # https://archive-api.open-meteo.com/v1/archive
        #   hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,shortwave_radiation
        #   timezone, start_date, end_date
        # Para rangos largos, partir en tramos mensuales (una petición por mes) y concatenar.
        # Devuelve df con columnas EXACTAS:
        #   date (str "YYYY-MM-DD"), hour (int 0-23), temp_c, rh_pct, wind_ms,
        #   wind_dir_deg, radiation_w_m2
        # Excluye filas con todas las variables meteorológicas nulas.
        # Errores de red/HTTP → RuntimeError. (Verificado en Fase 0: el archivo tiene
        # datos desde al menos 2026-04-01 hasta 2026-10-21 para Córdoba.)

    def iter_days(df: pd.DataFrame, start_date: str | None = None,
                  end_date: str | None = None) -> Iterator[tuple[str, pd.DataFrame]]
        # Itera (date, df_dia) con el MISMO contrato de columnas que la previsión de un
        # día (hour, temp_c, rh_pct, wind_ms, wind_dir_deg, radiation_w_m2 — sin 'date'),
        # ordenado por hour, opcionalmente recortado al rango. Los días sin filas se omiten.

    def calidad_datos(df: pd.DataFrame, start_date: str, end_date: str) -> str
        # "completo" si todos los días del rango tienen 24 horas; si no,
        # "parcial: N días incompletos (ej: 2026-07-03, ...)" (máx 3 ejemplos).

Tests (tests/test_historical.py):
  - Parseo con requests.get simulado (mock): columnas exactas, tipos, multi-día con 'date'.
  - Tramos mensuales concatenados sin duplicados ni desorden.
  - iter_days devuelve el contrato de un día (24 filas máx, sin columna date).
  - calidad_datos: rango completo → "completo"; faltando horas → "parcial: ...".
  - Marca @pytest.mark.integration: rango real de 1 semana (p.ej. 2026-06-01..07)
    con datos reales y rangos plausibles (HR 0-100, T en [-20,55], V>=0, rad>=0).

Notas de implementación (temporada):
- Una petición por mes natural (tramo [inicio, fin] recortado a los límites del rango)
  para no agotar los límites de la API en rangos largos (la temporada son 7 tramos).
- `wind_speed_unit=ms` para que el archivo devuelva viento en m/s (igual que weather.py).
- Los tramos se concatenan, se eliminan duplicados (date, hour) — por si la API devuelve
  solapes — y se ordenan por (date, hour).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterator

import pandas as pd
import requests

API_URL = "https://archive-api.open-meteo.com/v1/archive"

# Variables horarias del contrato: (nombre Open-Meteo, columna interna).
_VARIABLES: list[tuple[str, str]] = [
    ("temperature_2m", "temp_c"),
    ("relative_humidity_2m", "rh_pct"),
    ("wind_speed_10m", "wind_ms"),
    ("wind_direction_10m", "wind_dir_deg"),
    ("shortwave_radiation", "radiation_w_m2"),
]

_METEO_COLS: list[str] = [col for _, col in _VARIABLES]

# Columnas EXACTAS de fetch_archive.
COLUMNAS: list[str] = ["date", "hour", *_METEO_COLS]

# Columnas EXACTAS de un día en iter_days (mismo contrato que la previsión).
COLUMNAS_DIA: list[str] = ["hour", *_METEO_COLS]


def _parse_fecha(valor: str, nombre: str) -> date:
    """Valida 'YYYY-MM-DD' y devuelve un date. ValueError si el formato es incorrecto."""
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"Fecha inválida {valor!r} ({nombre}): se espera formato YYYY-MM-DD.") from exc


def _tramos_mensuales(inicio: date, fin: date) -> Iterator[tuple[str, str]]:
    """Divide [inicio, fin] en tramos que terminan todos en fin de mes (ISO strings)."""
    actual = inicio
    while actual <= fin:
        primero_siguiente_mes = (date(actual.year + 1, 1, 1) if actual.month == 12
                                 else date(actual.year, actual.month + 1, 1))
        ultimo = min(primero_siguiente_mes - timedelta(days=1), fin)
        yield actual.isoformat(), ultimo.isoformat()
        actual = ultimo + timedelta(days=1)


def _vacio() -> pd.DataFrame:
    """DataFrame con las columnas del contrato y dtypes correctos, sin filas."""
    return pd.DataFrame({
        "date": pd.Series(dtype=str),
        "hour": pd.Series(dtype=int),
        **{col: pd.Series(dtype=float) for col in _METEO_COLS},
    })[COLUMNAS]


def _descargar_tramo(start_date: str, end_date: str, latitude: float, longitude: float,
                     timezone: str) -> list[dict]:
    """Descarga UN tramo [start_date, end_date] del archivo y devuelve filas (dict).

    Raises:
        RuntimeError: Error de red/HTTP o respuesta sin serie horaria utilizable.
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ",".join(nombre for nombre, _ in _VARIABLES),
        "wind_speed_unit": "ms",
        "timezone": timezone,
        "start_date": start_date,
        "end_date": end_date,
    }
    try:
        resp = requests.get(API_URL, params=params, timeout=60)
        resp.raise_for_status()
        datos = resp.json()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Error de red/HTTP descargando el archivo Open-Meteo (ERA5) "
            f"{start_date}..{end_date}: {exc}"
        ) from exc
    except ValueError as exc:  # respuesta no es JSON válido
        raise RuntimeError(
            f"Respuesta no-JSON de Open-Meteo Archive {start_date}..{end_date}: {exc}"
        ) from exc

    hourly = datos.get("hourly")
    if not isinstance(hourly, dict) or not hourly.get("time"):
        raise RuntimeError(
            f"Open-Meteo Archive no devolvió serie horaria para {start_date}..{end_date}."
        )

    horas_raw: list = hourly["time"]
    filas: list[dict] = []
    for i, marca in enumerate(horas_raw):
        if not isinstance(marca, str) or len(marca) < 13:
            continue
        fila: dict = {"date": marca[:10], "hour": int(marca[11:13])}
        for nombre, col in _VARIABLES:
            valores = hourly.get(nombre) or []
            valor = valores[i] if i < len(valores) else None
            # Valores nulos puntuales → NaN (la exclusión de filas todas nulas se
            # hace después, en fetch_archive, según el contrato).
            fila[col] = float(valor) if valor is not None else float("nan")
        filas.append(fila)
    return filas


def fetch_archive(start_date: str, end_date: str, latitude: float, longitude: float,
                  timezone: str = "Europe/Madrid") -> pd.DataFrame:
    """Descarga el rango [start_date, end_date] del archivo ERA5 de Open-Meteo.

    Parte el rango en tramos mensuales (una petición por mes) y los concatena
    sin duplicados y ordenados por (date, hour).

    Args:
        start_date: Inicio del rango "YYYY-MM-DD" (inclusivo).
        end_date: Fin del rango "YYYY-MM-DD" (inclusivo).
        latitude: Latitud en grados decimales.
        longitude: Longitud en grados decimales.
        timezone: Zona horaria IANA (por defecto "Europe/Madrid").

    Returns:
        DataFrame con columnas EXACTAS: date (str), hour (int 0-23), temp_c, rh_pct,
        wind_ms, wind_dir_deg, radiation_w_m2. Sin filas cuyas 5 variables
        meteorológicas sean todas nulas.

    Raises:
        ValueError: Fechas mal formadas o inicio posterior a fin.
        RuntimeError: Error de red/HTTP o respuesta sin serie horaria.
    """
    inicio = _parse_fecha(start_date, "start_date")
    fin = _parse_fecha(end_date, "end_date")
    if inicio > fin:
        raise ValueError(
            f"Rango inválido: start_date {start_date!r} es posterior a end_date {end_date!r}."
        )

    filas: list[dict] = []
    for tramo_inicio, tramo_fin in _tramos_mensuales(inicio, fin):
        filas.extend(_descargar_tramo(tramo_inicio, tramo_fin, latitude, longitude, timezone))

    if not filas:
        return _vacio()

    df = pd.DataFrame(filas, columns=COLUMNAS)
    # Excluir filas con TODAS las variables meteorológicas nulas (contrato),
    # luego duplicados de posibles solapes entre tramos, y ordenar.
    df = df.dropna(subset=_METEO_COLS, how="all")
    df = df.drop_duplicates(subset=["date", "hour"], keep="first")
    # Respetar el rango pedido aunque la API devuelva marcas fuera de él.
    df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
    df = df.sort_values(["date", "hour"], kind="stable").reset_index(drop=True)
    df["date"] = df["date"].astype(str)
    df["hour"] = df["hour"].astype(int)
    for col in _METEO_COLS:
        df[col] = df[col].astype(float)
    return df[COLUMNAS]


def iter_days(df: pd.DataFrame, start_date: str | None = None,
              end_date: str | None = None) -> Iterator[tuple[str, pd.DataFrame]]:
    """Itera (date, df_dia) con el mismo contrato de columnas que la previsión de un día.

    Args:
        df: Salida de fetch_archive (columna `date` incluida).
        start_date: Si se indica, incluye solo días >= esta fecha ("YYYY-MM-DD").
        end_date: Si se indica, incluye solo días <= esta fecha ("YYYY-MM-DD").

    Yields:
        (fecha "YYYY-MM-DD", DataFrame con COLUMNAS_DIA — sin `date` — ordenado por
        hour y sin duplicados). Los días sin filas se omiten.
    """
    trabajado = df
    if start_date is not None:
        trabajado = trabajado[trabajado["date"] >= start_date]
    if end_date is not None:
        trabajado = trabajado[trabajado["date"] <= end_date]
    if trabajado.empty:
        return
    for fecha, grupo in trabajado.sort_values(["date", "hour"]).groupby("date", sort=True):
        dia = (grupo[COLUMNAS_DIA]
               .drop_duplicates(subset=["hour"], keep="first")
               .sort_values("hour")
               .reset_index(drop=True))
        dia["hour"] = dia["hour"].astype(int)
        yield str(fecha), dia


def calidad_datos(df: pd.DataFrame, start_date: str, end_date: str) -> str:
    """Calidad del rango: "completo" si todos los días tienen 24 horas; si no, "parcial".

    Args:
        df: Salida de fetch_archive.
        start_date: Inicio del rango "YYYY-MM-DD".
        end_date: Fin del rango "YYYY-MM-DD".

    Returns:
        "completo" o "parcial: N días incompletos (ej: 2026-07-03, ...)" con
        como mucho 3 ejemplos (y "..." si hay más).
    """
    inicio = _parse_fecha(start_date, "start_date")
    fin = _parse_fecha(end_date, "end_date")
    if inicio > fin:
        raise ValueError(
            f"Rango inválido: start_date {start_date!r} es posterior a end_date {end_date!r}."
        )

    conteo = (df.groupby("date").size() if df is not None and not df.empty
              else pd.Series(dtype=int))

    incompletos: list[str] = []
    actual = inicio
    while actual <= fin:
        clave = actual.isoformat()
        if int(conteo.get(clave, 0)) != 24:
            incompletos.append(clave)
        actual += timedelta(days=1)

    if not incompletos:
        return "completo"

    ejemplos = incompletos[:3]
    if len(incompletos) > 3:
        ejemplos = [*ejemplos, "..."]
    return f"parcial: {len(incompletos)} días incompletos (ej: {', '.join(ejemplos)})"
