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
- sqlite3 puro, sin ORM. Conexión por operación (cierre garantizado, thread-safe),
  con WAL + busy_timeout para lecturas concurrentes (auditoría G4).
- Fechas en formato "YYYY-MM-DD", horas de lectura "HH:MM" (orden lexicográfico = cronológico).
- save_forecast reemplaza la previsión previa del día (DELETE + INSERT en transacción).
- save_season_runs es transaccional (DELETE + INSERT mismo `with conn` → rollback
  completo ante cualquier fallo a mitad) y valida `rows` antes de tocar la DB (M5).
- save_prediction sanitiza el payload a JSON estricto: NaN/inf → null (M5).
"""
from __future__ import annotations

import json
import math
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
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
CREATE TABLE IF NOT EXISTS harvests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    kg REAL NOT NULL,
    zone_id TEXT DEFAULT 'default',
    notes TEXT DEFAULT '',
    created_at TEXT,
    UNIQUE (date, zone_id)
);
CREATE INDEX IF NOT EXISTS idx_forecast_date ON forecast (date);
CREATE INDEX IF NOT EXISTS idx_readings_date ON readings (date);
CREATE INDEX IF NOT EXISTS idx_predictions_date ON predictions (date);
CREATE INDEX IF NOT EXISTS idx_season_rango ON season_runs (start_date, end_date, date);
CREATE INDEX IF NOT EXISTS idx_harvests_date ON harvests (date);
"""


def _ahora() -> str:
    """Marca de tiempo local "YYYY-MM-DD HH:MM:SS" para columnas de auditoría."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _sanitizar_json(valor: Any) -> Any:
    """Convierte `valor` a algo serializable con JSON estricto (auditoría M5).

    - NaN / ±inf → None: ``json.dumps`` por defecto escribiría ``NaN``/`Infinity``,
      que un parser JSON estricto rechaza.
    - Escalares numpy (np.float64, np.int64, np.bool_…) → tipos Python nativos.
    - dict, list y tuple se recorren recursivamente (claves intactas).

    Cualquier otra cosa no serializable la resuelve ``default=str`` en save_prediction.
    """
    if isinstance(valor, dict):
        return {k: _sanitizar_json(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_sanitizar_json(v) for v in valor]
    if isinstance(valor, np.generic):
        valor = valor.item()   # p. ej. np.float64 → float antes del chequeo de finito
    if isinstance(valor, float) and not math.isfinite(valor):
        return None
    return valor


class Database:
    """Acceso a la base de datos local SQLite de la salina (una conexión por operación)."""

    def __init__(self, path: str | Path | None = None) -> None:
        """Constructor. `path=None` usa DB_PATH de src.config (data/flor_desal.db)."""
        self.path: Path = Path(path) if path else DB_PATH

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Context manager: conexión con PRAGMAs de concurrencia, commit y cierre.

        PRAGMAs al abrir (auditoría G4 — Streamlit con varios onglets / futuro web):

        - ``journal_mode=WAL``: las lecturas no bloquean al escritor (y viceversa).
        - ``busy_timeout=5000``: ante una escritura ajena en curso espera hasta 5 s
          antes de fallar con "database is locked" (además del timeout=5 s de connect).
        - ``synchronous=NORMAL``: con WAL es seguro y más rápido que FULL.

        ``with conn`` hace commit si todo va bien y rollback si hay excepción
        (transacción completa para DELETE+INSERT de reemplazos).
        """
        conn = sqlite3.connect(self.path, timeout=5.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA synchronous=NORMAL")
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
                int(row.hour),  # type: ignore[arg-type]
                float(row.temp_c),  # type: ignore[arg-type]
                float(row.rh_pct),  # type: ignore[arg-type]
                float(row.wind_ms),  # type: ignore[arg-type]
                float(row.wind_dir_deg),  # type: ignore[arg-type]
                float(row.radiation_w_m2),  # type: ignore[arg-type]
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
            return int(cur.lastrowid)  # type: ignore[arg-type]

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
        """Guarda el veredicto del día serializando `payload` a JSON estricto.

        El payload se sanitiza antes (auditoría M5): NaN/±inf → null, escalares
        numpy → tipos Python nativos, dict/list/tuple recursivos. Así el JSON
        guardado siempre lo parsea un parser estricto (json.loads lo recupera).

        Args:
            date: Día de la predicción "YYYY-MM-DD".
            computed_at: Marca de cálculo (la entrega el pipeline).
            payload: Dict serializable con el veredicto.

        Returns:
            id de la fila insertada.
        """
        payload_json = json.dumps(_sanitizar_json(payload), ensure_ascii=False, default=str)
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO predictions (date, computed_at, payload_json) VALUES (?, ?, ?)",
                (date, computed_at, payload_json),
            )
            return int(cur.lastrowid)  # type: ignore[arg-type]

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

        Transaccional (auditoría M5): el DELETE del rango y el INSERT de las filas
        van en la MISMA transacción; si un insert falla a mitad, el rollback
        devuelve la tabla a su estado anterior (nunca queda "a medias"). Además
        valida `rows` ANTES de tocar la DB.

        Raises:
            ValueError: Si alguna fila no es dict o no tiene el campo 'date'.

        Returns: nº de filas guardadas.
        """
        if not rows:
            return 0
        for i, fila in enumerate(rows):
            if not isinstance(fila, dict):
                raise ValueError(
                    f"save_season_runs: rows[{i}] debe ser un dict "
                    f"(recibido {type(fila).__name__}).")
            fecha = fila.get("date")
            if not isinstance(fecha, str) or not fecha.strip():
                raise ValueError(
                    f"save_season_runs: rows[{i}] sin el campo obligatorio "
                    f"'date' (fecha 'YYYY-MM-DD').")
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

    # ------------------------------------------------ Cosecha (kg/día)
    def save_harvest(self, date: str, kg: float, zone_id: str = "default",
                     notes: str = "") -> int:
        """Guarda o actualiza la cosecha del día.

        Args:
            date: "YYYY-MM-DD"
            kg: kilogramos de flor de sal recolectados ese día
            zone_id: identificador de zona (por defecto "default")
            notes: observaciones opcionales

        Returns: id de la fila guardada.
        """
        if kg < 0:
            raise ValueError("kg no puede ser negativo")
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO harvests (date, kg, zone_id, notes, created_at)"
                " VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT(date, zone_id) DO UPDATE SET kg=excluded.kg,"
                " notes=excluded.notes, created_at=excluded.created_at",
                (date, float(kg), zone_id, notes or "", _ahora()),
            )
            return int(cur.lastrowid)  # type: ignore[arg-type]

    def get_harvests(self, start_date: str | None = None,
                     end_date: str | None = None,
                     zone_id: str = "default") -> pd.DataFrame:
        """Devuelve las cosechas en el rango [start_date, end_date] (inclusive).

        Args:
            start_date: "YYYY-MM-DD" (inclusive), None = sin límite inferior
            end_date: "YYYY-MM-DD" (inclusive), None = sin límite superior
            zone_id: filtrar por zona

        Returns: DataFrame con columnas date, kg, zone_id, notes, created_at.
        """
        sql = ("SELECT date, kg, zone_id, notes, created_at FROM harvests"
               " WHERE zone_id = ?")
        params: list[Any] = [zone_id]
        if start_date is not None:
            sql += " AND date >= ?"
            params.append(start_date)
        if end_date is not None:
            sql += " AND date <= ?"
            params.append(end_date)
        sql += " ORDER BY date"
        with self._connect() as conn:
            filas = conn.execute(sql, params).fetchall()
        return pd.DataFrame(filas, columns=["date", "kg", "zone_id", "notes", "created_at"])
