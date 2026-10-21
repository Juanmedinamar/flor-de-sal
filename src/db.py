"""Capa de datos — SQLite local (data/flor_desal.db).

CONTRATO — a implementar por data-ingest. Firmas exactas:

    class Database:
        def __init__(self, path: str | Path | None = None) -> None
            # None -> DB_PATH de src.config

        def init_schema(self) -> None
            # Crea las tablas si no existen (idempotente).

        # --- Previsión meteorológica ---
        def save_forecast(self, date: str, df: pd.DataFrame, source: str = "open-meteo") -> int
            # df columnas: hour (int 0-23), temp_c, rh_pct, wind_ms, wind_dir_deg, radiation_w_m2.
            # date: "YYYY-MM-DD". Borra la previsión previa de ese día (reemplazo).
            # Devuelve nº de filas guardadas.

        def get_forecast(self, date: str) -> pd.DataFrame | None
            # Misma forma que el df guardado, ordenado por hour. None si no hay.

        # --- Lecturas reales de campo ---
        def save_reading(self, date: str, reading_time: str,
                         t_calentador_c: float | None, t_cristalizador_c: float | None,
                         concentration_g_l: float | None, t_ambiente_c: float | None,
                         rh_pct: float | None, wind_ms: float | None,
                         notes: str = "") -> int
            # reading_time: "HH:MM". Devuelve id.

        def get_readings(self, date: str) -> pd.DataFrame
            # Columnas: reading_time, t_calentador_c, t_cristalizador_c, concentration_g_l,
            #           t_ambiente_c, rh_pct, wind_ms, notes — ordenado por reading_time.

        # --- Predicciones / veredictos ---
        def save_prediction(self, date: str, computed_at: str, payload: dict) -> int
            # payload: dict serializable (ver pipeline.run_daily). Devuelve id.

        def get_predictions(self, date: str) -> pd.DataFrame
            # Una fila por predicción, con payload decodificado en columna "payload".

Esquema sugerido (libre de implementarlo como quieras si respeta las firmas):

    forecast(id, date, hour, temp_c, rh_pct, wind_ms, wind_dir_deg, radiation_w_m2,
             source, fetched_at)
    readings(id, date, reading_time, t_calentador_c, t_cristalizador_c, concentration_g_l,
             t_ambiente_c, rh_pct, wind_ms, notes, created_at)
    predictions(id, date, computed_at, payload_json)

Notas de implementación (data-ingest):
- sqlite3 puro, sin ORM. Conexión por operación (cierre garantizado, thread-safe).
- Fechas en formato "YYYY-MM-DD", horas de lectura "HH:MM" (orden lexicográfico = cronológico).
- save_forecast reemplaza la previsión previa del día (DELETE + INSERT en transacción).
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

import pandas as pd

from src.config import DB_PATH

# Columnas exactas del df de previsión (contrato de src.weather.fetch_forecast)
FORECAST_COLS: list[str] = [
    "hour", "temp_c", "rh_pct", "wind_ms", "wind_dir_deg", "radiation_w_m2",
]

# Columnas exactas que devuelve get_readings (contrato)
READINGS_COLS: list[str] = [
    "reading_time", "t_calentador_c", "t_cristalizador_c", "concentration_g_l",
    "t_ambiente_c", "rh_pct", "wind_ms", "notes",
]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS forecast (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    hour INTEGER NOT NULL,
    temp_c REAL,
    rh_pct REAL,
    wind_ms REAL,
    wind_dir_deg REAL,
    radiation_w_m2 REAL,
    source TEXT,
    fetched_at TEXT,
    UNIQUE (date, hour)
);
CREATE TABLE IF NOT EXISTS readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    reading_time TEXT NOT NULL,
    t_calentador_c REAL,
    t_cristalizador_c REAL,
    concentration_g_l REAL,
    t_ambiente_c REAL,
    rh_pct REAL,
    wind_ms REAL,
    notes TEXT DEFAULT '',
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS season_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    date TEXT NOT NULL,
    window_start TEXT,
    window_end TEXT,
    hora_optima TEXT,
    ci_low TEXT,
    ci_high TEXT,
    prob_ventana REAL,
    prob_riesgo REAL,
    calidad TEXT,
    n_iter INTEGER,
    computed_at TEXT,
    UNIQUE (start_date, end_date, date)
);
CREATE INDEX IF NOT EXISTS idx_forecast_date ON forecast (date);
CREATE INDEX IF NOT EXISTS idx_readings_date ON readings (date);
CREATE INDEX IF NOT EXISTS idx_predictions_date ON predictions (date);
CREATE INDEX IF NOT EXISTS idx_season_rango ON season_runs (start_date, end_date, date);
"""


def _ahora() -> str:
    """Marca de tiempo local "YYYY-MM-DD HH:MM:SS" para columnas de auditoría."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Database:
    """Acceso a la base de datos local SQLite de la salina (una conexión por operación)."""

    def __init__(self, path: str | Path | None = None) -> None:
        """Constructor. `path=None` usa DB_PATH de src.config (data/flor_desal.db)."""
        self.path: Path = Path(path) if path else DB_PATH

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Context manager: conexión, commit automático y cierre garantizado."""
        conn = sqlite3.connect(self.path)
        try:
            with conn:  # hace commit si todo va bien, rollback si hay excepción
                yield conn
        finally:
            conn.close()

    def init_schema(self) -> None:
        """Crea las tablas forecast/readings/predictions/season_runs si no existen (idempotente)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    # ------------------------------------------------------------------
    # Previsión meteorológica
    # ------------------------------------------------------------------
    def save_forecast(self, date: str, df: pd.DataFrame, source: str = "open-meteo") -> int:
        """Guarda la previsión horaria de `date` ("YYYY-MM-DD"), reemplazando la anterior.

        Args:
            date: Día de la previsión en formato "YYYY-MM-DD".
            df: DataFrame con las columnas exactas de fetch_forecast (FORECAST_COLS).
            source: Origen de los datos (por defecto "open-meteo").

        Returns:
            Número de filas guardadas.
        """
        faltantes = [c for c in FORECAST_COLS if c not in df.columns]
        if faltantes:
            raise ValueError(f"df de previsión sin columnas requeridas: {faltantes}")

        registros = [
            (
                date,
                int(row.hour),
                float(row.temp_c),
                float(row.rh_pct),
                float(row.wind_ms),
                float(row.wind_dir_deg),
                float(row.radiation_w_m2),
                source,
                _ahora(),
            )
            for row in df[FORECAST_COLS].itertuples(index=False)
        ]
        with self._connect() as conn:
            conn.execute("DELETE FROM forecast WHERE date = ?", (date,))
            conn.executemany(
                "INSERT INTO forecast (date, hour, temp_c, rh_pct, wind_ms, wind_dir_deg,"
                " radiation_w_m2, source, fetched_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                registros,
            )
        return len(registros)

    def get_forecast(self, date: str) -> pd.DataFrame | None:
        """Devuelve la previsión de `date` ordenada por hora, o None si no hay.

        Returns:
            DataFrame con las columnas FORECAST_COLS (hour de tipo int) o None.
        """
        with self._connect() as conn:
            filas = conn.execute(
                "SELECT hour, temp_c, rh_pct, wind_ms, wind_dir_deg, radiation_w_m2"
                " FROM forecast WHERE date = ? ORDER BY hour",
                (date,),
            ).fetchall()
        if not filas:
            return None
        df = pd.DataFrame(filas, columns=FORECAST_COLS)
        df["hour"] = df["hour"].astype(int)
        return df

    # ------------------------------------------------------------------
    # Lecturas reales de campo
    # ------------------------------------------------------------------
    def save_reading(self, date: str, reading_time: str,
                     t_calentador_c: float | None, t_cristalizador_c: float | None,
                     concentration_g_l: float | None, t_ambiente_c: float | None,
                     rh_pct: float | None, wind_ms: float | None, notes: str = "") -> int:
        """Registra una lectura real de campo en `date` a las `reading_time` ("HH:MM").

        Returns:
            id de la fila insertada.
        """
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO readings (date, reading_time, t_calentador_c, t_cristalizador_c,"
                " concentration_g_l, t_ambiente_c, rh_pct, wind_ms, notes, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (date, reading_time, t_calentador_c, t_cristalizador_c,
                 concentration_g_l, t_ambiente_c, rh_pct, wind_ms, notes, _ahora()),
            )
            return int(cur.lastrowid)

    def get_readings(self, date: str) -> pd.DataFrame:
        """Devuelve las lecturas reales de `date` ordenadas por reading_time.

        Returns:
            DataFrame con columnas READINGS_COLS (vacío si no hay lecturas).
        """
        with self._connect() as conn:
            filas = conn.execute(
                "SELECT reading_time, t_calentador_c, t_cristalizador_c, concentration_g_l,"
                " t_ambiente_c, rh_pct, wind_ms, notes"
                " FROM readings WHERE date = ? ORDER BY reading_time",
                (date,),
            ).fetchall()
        return pd.DataFrame(filas, columns=READINGS_COLS)

    # ------------------------------------------------------------------
    # Predicciones / veredictos
    # ------------------------------------------------------------------
    def save_prediction(self, date: str, computed_at: str, payload: dict) -> int:
        """Guarda el veredicto del día serializando `payload` a JSON.

        Args:
            date: Día de la predicción "YYYY-MM-DD".
            computed_at: Marca de cálculo (la entrega el pipeline).
            payload: Dict serializable con el veredicto.

        Returns:
            id de la fila insertada.
        """
        payload_json = json.dumps(payload, ensure_ascii=False, default=str)
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO predictions (date, computed_at, payload_json) VALUES (?, ?, ?)",
                (date, computed_at, payload_json),
            )
            return int(cur.lastrowid)

    def get_predictions(self, date: str) -> pd.DataFrame:
        """Devuelve las predicciones de `date` con el payload ya decodificado.

        Returns:
            DataFrame con columnas id, date, computed_at, payload (dict); vacío si no hay.
        """
        with self._connect() as conn:
            filas = conn.execute(
                "SELECT id, date, computed_at, payload_json"
                " FROM predictions WHERE date = ? ORDER BY id",
                (date,),
            ).fetchall()
        df = pd.DataFrame(filas, columns=["id", "date", "computed_at", "payload_json"])
        if df.empty:
            return pd.DataFrame(columns=["id", "date", "computed_at", "payload"])
        df["payload"] = df["payload_json"].map(json.loads)
        return df.drop(columns=["payload_json"])

    # ------------------------------------------------ Simulación de temporada

    def save_season_runs(self, start_date: str, end_date: str,
                         rows: list[dict]) -> int:
        """Guarda los veredictos diarios de una simulación de temporada.

        Reemplaza los resultados previos MISMO rango (idempotente: re-ejecutar
        la simulación no duplica filas). Cada fila de `rows`:
        {'date', 'window_start', 'window_end', 'hora_optima', 'ci_low', 'ci_high',
         'prob_ventana', 'prob_riesgo', 'calidad', 'n_iter'}.

        Returns: nº de filas guardadas.
        """
        if not rows:
            return 0
        ahora = _ahora()
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM season_runs WHERE start_date = ? AND end_date = ?",
                (start_date, end_date),
            )
            conn.executemany(
                "INSERT INTO season_runs (start_date, end_date, date, window_start,"
                " window_end, hora_optima, ci_low, ci_high, prob_ventana, prob_riesgo,"
                " calidad, n_iter, computed_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(start_date, end_date, r["date"], r.get("window_start"),
                  r.get("window_end"), r.get("hora_optima"), r.get("ci_low"),
                  r.get("ci_high"), r.get("prob_ventana"), r.get("prob_riesgo"),
                  r.get("calidad"), r.get("n_iter"), ahora) for r in rows],
            )
        return len(rows)

    def get_season_runs(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Resultados de la temporada [start_date, end_date] ordenados por fecha.

        Returns: DataFrame (vacío si no hay nada) con las columnas guardadas.
        """
        cols = ["date", "window_start", "window_end", "hora_optima", "ci_low",
                "ci_high", "prob_ventana", "prob_riesgo", "calidad", "n_iter",
                "computed_at"]
        with self._connect() as conn:
            filas = conn.execute(
                "SELECT date, window_start, window_end, hora_optima, ci_low, ci_high,"
                " prob_ventana, prob_riesgo, calidad, n_iter, computed_at"
                " FROM season_runs WHERE start_date = ? AND end_date = ?"
                " ORDER BY date",
                (start_date, end_date),
            ).fetchall()
        return pd.DataFrame(filas, columns=cols)
