"""Tests de la capa de datos (src/db.py) sobre SQLite en tmp_path.

Cubre el contrato más las auditorías: conexiones con WAL/busy_timeout (G4),
JSON estricto en predicciones (NaN/inf/numpy → null) y season_runs transaccional
con validación previa y rollback completo (M5).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.config import DB_PATH
from src.db import Database

FECHA = "2026-07-15"


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    """Database en un archivo temporal con el esquema ya creado."""
    database = Database(tmp_path / "test_flor_desal.db")
    database.init_schema()
    return database


def _tabla_existe(db: Database, nombre: str) -> bool:
    with sqlite3.connect(db.path) as conn:
        fila = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (nombre,)
        ).fetchone()
    return fila is not None


# ---------------------------------------------------------------------------
# Esquema
# ---------------------------------------------------------------------------
def test_init_schema_es_idempotente(db: Database) -> None:
    """init_schema se puede llamar varias veces sin error y crea las 3 tablas."""
    db.init_schema()
    db.init_schema()
    for tabla in ("forecast", "readings", "predictions"):
        assert _tabla_existe(db, tabla), f"falta la tabla {tabla}"


def test_ruta_por_defecto_es_db_path(cfg) -> None:
    """Database() sin argumentos usa DB_PATH de la config (sin tocar el archivo)."""
    assert Database().path == DB_PATH


# ---------------------------------------------------------------------------
# Concurrencia SQLite (auditoría G4)
# ---------------------------------------------------------------------------
def test_conexiones_abren_con_wal_busy_timeout_y_synchronous(db: Database) -> None:
    """Cada conexión aplica los PRAGMAs de concurrencia antes de usar la DB."""
    with db._connect() as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        assert conn.execute("PRAGMA synchronous").fetchone()[0] == 1   # NORMAL


def test_journal_mode_wal_persiste_en_el_fichero(db: Database) -> None:
    """Tras init_schema el fichero queda en WAL: lecturas sin bloquear al escritor."""
    with sqlite3.connect(db.path) as conn:
        modo = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert modo.lower() == "wal"


# ---------------------------------------------------------------------------
# Previsión
# ---------------------------------------------------------------------------
def test_forecast_guarda_y_recupera(db: Database, dia_verano_cordoba: pd.DataFrame) -> None:
    """save_forecast/get_forecast conservan columnas, valores y orden por hora."""
    n = db.save_forecast(FECHA, dia_verano_cordoba)

    assert n == len(dia_verano_cordoba)
    df = db.get_forecast(FECHA)

    assert df is not None
    assert list(df.columns) == [
        "hour", "temp_c", "rh_pct", "wind_ms", "wind_dir_deg", "radiation_w_m2",
    ]
    assert len(df) == len(dia_verano_cordoba)
    assert df["hour"].is_monotonic_increasing
    assert df["hour"].tolist() == sorted(dia_verano_cordoba["hour"].tolist())
    assert pd.api.types.is_integer_dtype(df["hour"])
    # valores redondos del escenario del PDF
    fila_16h = df.loc[df["hour"] == 16].iloc[0]
    assert fila_16h["temp_c"] == pytest.approx(35.0)
    assert fila_16h["rh_pct"] == pytest.approx(28.0)
    assert fila_16h["wind_ms"] == pytest.approx(3.0)


def test_forecast_reemplaza_la_previa_del_dia(db: Database, dia_verano_cordoba: pd.DataFrame) -> None:
    """Volver a guardar el mismo día no duplica filas (reemplazo completo)."""
    db.save_forecast(FECHA, dia_verano_cordoba)
    actualizado = dia_verano_cordoba.copy()
    actualizado["temp_c"] = actualizado["temp_c"] + 1.0
    db.save_forecast(FECHA, actualizado)

    df = db.get_forecast(FECHA)
    assert df is not None
    assert len(df) == len(dia_verano_cordoba)
    assert df.loc[df["hour"] == 16, "temp_c"].iloc[0] == pytest.approx(36.0)


def test_forecast_desconocido_devuelve_none(db: Database) -> None:
    """Sin datos para la fecha, get_forecast devuelve None."""
    assert db.get_forecast("1999-01-01") is None


# ---------------------------------------------------------------------------
# Lecturas reales
# ---------------------------------------------------------------------------
def test_readings_guarda_y_recupera_ordenado(db: Database) -> None:
    """Las lecturas se recuperan ordenadas por reading_time con las columnas exactas."""
    db.save_reading(FECHA, "12:30", 31.0, 33.5, 300.0, 32.0, 38.0, 2.5, "primera")
    db.save_reading(FECHA, "09:15", 25.0, 27.0, 292.0, 24.0, 55.0, 1.2, "temprana")

    df = db.get_readings(FECHA)

    assert list(df.columns) == [
        "reading_time", "t_calentador_c", "t_cristalizador_c", "concentration_g_l",
        "t_ambiente_c", "rh_pct", "wind_ms", "notes",
    ]
    assert df["reading_time"].tolist() == ["09:15", "12:30"]  # orden cronológico
    assert df.loc[1, "concentration_g_l"] == pytest.approx(300.0)
    assert df.loc[0, "notes"] == "temprana"


def test_readings_admite_nulos_y_devuelve_id(db: Database) -> None:
    """Campos opcionales pueden ser None y save_reading devuelve el id insertado."""
    id1 = db.save_reading(FECHA, "08:00", None, None, None, None, None, None)
    id2 = db.save_reading(FECHA, "10:00", 26.0, 28.0, 295.0, 25.0, 60.0, 1.0)

    assert id2 > id1
    df = db.get_readings(FECHA)
    assert len(df) == 2
    assert pd.isna(df.loc[0, "t_calentador_c"])
    assert df.loc[1, "t_calentador_c"] == pytest.approx(26.0)


def test_readings_sin_datos_devuelve_dataframe_vacio(db: Database) -> None:
    """Sin lecturas, get_readings devuelve un DataFrame vacío con las columnas."""
    df = db.get_readings("1999-01-01")
    assert isinstance(df, pd.DataFrame)
    assert df.empty
    assert list(df.columns) == [
        "reading_time", "t_calentador_c", "t_cristalizador_c", "concentration_g_l",
        "t_ambiente_c", "rh_pct", "wind_ms", "notes",
    ]


# ---------------------------------------------------------------------------
# Predicciones
# ---------------------------------------------------------------------------
def test_predictions_guarda_y_decodifica_payload(db: Database) -> None:
    """El payload se serializa a JSON y vuelve como dict idéntico."""
    payload = {
        "fase": 2,
        "ventana_optima": ["15:30", "19:00"],
        "hora_optima_mediana": "17:10",
        "prob_ventana": 0.82,
        "ic95": ["16:20", "18:40"],
        "alertas": ["viento moderado"],
    }

    id1 = db.save_prediction(FECHA, "2026-07-15T06:05:00", payload)
    id2 = db.save_prediction(FECHA, "2026-07-15T12:00:00", {"fase": 3, "alertas": ["viento > 5.5 m/s"]})

    assert id2 > id1
    df = db.get_predictions(FECHA)
    assert list(df.columns) == ["id", "date", "computed_at", "payload"]
    assert len(df) == 2
    assert df.loc[0, "date"] == FECHA
    assert df.loc[0, "payload"] == payload
    assert df.loc[1, "payload"]["fase"] == 3


def test_predictions_sin_datos_devuelve_vacio(db: Database) -> None:
    """Sin predicciones, get_predictions devuelve un DataFrame vacío."""
    df = db.get_predictions("1999-01-01")
    assert df.empty
    assert list(df.columns) == ["id", "date", "computed_at", "payload"]


def test_predictions_json_estricto_nan_inf_y_numpy(db: Database) -> None:
    """NaN/inf → null y escalares numpy → Python nativo: el JSON guardado es estricto (M5)."""
    payload = {
        "prob_ventana": float("nan"),
        "ic95": [float("inf"), -float("inf")],
        "hora_optima": np.float64(17.5),
        "n_iter": np.int64(1000),
        "ok": 1.0,
        "anidado": {"v": [np.float32(2.5), float("nan")]},
    }

    db.save_prediction(FECHA, "2026-07-15T06:05:00", payload)

    with sqlite3.connect(db.path) as conn:
        crudo = conn.execute("SELECT payload_json FROM predictions").fetchone()[0]
    assert "NaN" not in crudo and "Infinity" not in crudo   # ni NaN ni ±Infinity
    decodificado = json.loads(crudo)   # parser JSON estricto: no lanza

    df = db.get_predictions(FECHA)
    got = df.loc[0, "payload"]
    assert got["prob_ventana"] is None
    assert got["ic95"] == [None, None]
    assert type(got["hora_optima"]) is float and got["hora_optima"] == 17.5
    assert type(got["n_iter"]) is int and got["n_iter"] == 1000
    assert got["anidado"]["v"] == [2.5, None]
    assert decodificado == got


# ---------------------------------------------------------------------------
# Simulación de temporada (auditoría M5): validación + transacción
# ---------------------------------------------------------------------------
def _fila_season(fecha: str) -> dict:
    """Fila válida para save_season_runs."""
    return {"date": fecha, "window_start": "16:00", "window_end": "19:30",
            "hora_optima": "17:45", "ci_low": "16:30", "ci_high": "18:30",
            "prob_ventana": 0.9, "prob_riesgo": 0.05, "calidad": "completo",
            "n_iter": 100}


def test_save_season_runs_valida_filas_antes_de_tocar_la_db(db: Database) -> None:
    """Sin 'date' (o sin dicts) → ValueError claro y la tabla NO cambia."""
    db.save_season_runs("2026-06-01", "2026-06-03", [_fila_season("2026-06-01")])

    with pytest.raises(ValueError, match="date"):
        db.save_season_runs("2026-06-01", "2026-06-03", [{"window_start": "16:00"}])
    with pytest.raises(ValueError, match=r"rows\[1\]"):
        db.save_season_runs("2026-06-01", "2026-06-03",
                            [_fila_season("2026-06-01"), "no-soy-un-dict"])

    assert db.get_season_runs("2026-06-01", "2026-06-03")["date"].tolist() == ["2026-06-01"]


def test_save_season_runs_rollback_completo_si_falla_a_mitad(db: Database) -> None:
    """Un valor no serializable a mitad de INSERT → rollback total (DELETE incluido)."""
    previas = [_fila_season("2026-06-01"), _fila_season("2026-06-02")]
    db.save_season_runs("2026-06-01", "2026-06-03", previas)

    filas_malas = [
        _fila_season("2026-06-01"),
        _fila_season("2026-06-02"),
        {**_fila_season("2026-06-03"), "prob_ventana": {1, 2}},   # set: no serializable
    ]
    with pytest.raises(sqlite3.Error):
        db.save_season_runs("2026-06-01", "2026-06-03", filas_malas)

    df = db.get_season_runs("2026-06-01", "2026-06-03")
    assert df["date"].tolist() == ["2026-06-01", "2026-06-02"]   # estado previo intacto
    assert df["prob_ventana"].tolist() == [0.9, 0.9]
