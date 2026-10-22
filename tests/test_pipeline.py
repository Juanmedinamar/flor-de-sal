"""Tests del pipeline diario — SIN red: la previsión se guarda en una DB temporal.

Cubren la orquestación run_daily/recalc_with_field_data (veredicto completo,
persistencia con db.save_prediction, estados por hora que suman 1) y las
auditorías del módulo: G8 (un SOLO ensemble compartido por el MC y Márkov) y
M9 (tiempos del veredicto en la zona horaria de la salina, con fallback).
"""
from __future__ import annotations

import copy
import re
from unittest import mock

import pytest

from src import markov, montecarlo, pipeline
from src.db import Database

FECHA = "2026-07-15"
N_ITER = 300


@pytest.fixture
def db(tmp_path, dia_verano_cordoba):
    """DB SQLite temporal con la previsión del día de verano ya guardada (sin red)."""
    database = Database(tmp_path / "test.db")
    database.init_schema()
    database.save_forecast(FECHA, dia_verano_cordoba)
    return database


# ------------------------------------------------------------ run_daily -----

def test_run_daily_veredicto_claves(db, cfg):
    """El veredicto contiene las claves del contrato (AGENTS.md) y tipos correctos."""
    v = pipeline.run_daily(db, FECHA, cfg=cfg, n_iter=N_ITER)
    esperadas = {
        "fecha", "fase_actual", "fase_descripcion", "ventana_inicio", "ventana_fin",
        "hora_optima", "hora_optima_ci", "prob_ventana", "prob_riesgo",
        "estados_por_hora", "alertas", "bias", "n_iter", "computed_at",
        "hora_veredicto",
    }
    assert esperadas <= set(v)
    assert v["fecha"] == FECHA
    assert v["n_iter"] == N_ITER
    assert isinstance(v["fase_actual"], int) and 0 <= v["fase_actual"] <= 3
    assert isinstance(v["fase_descripcion"], str) and v["fase_descripcion"]
    # Día de verano del PDF: ventana casi segura, óptima por la tarde
    assert v["prob_ventana"] > 0.8
    assert v["hora_optima"] is not None and re.fullmatch(r"\d{2}:\d{2}", v["hora_optima"])
    assert v["ventana_inicio"] < v["hora_optima"] < v["ventana_fin"]
    assert len(v["hora_optima_ci"]) == 2
    # Alertas: lista de dicts con el trinomio nivel/codigo/mensaje
    assert v["alertas"] and all({"nivel", "codigo", "mensaje"} <= set(a)
                                for a in v["alertas"])
    assert v["bias"] == {}            # sin lecturas de campo no hay sesgo


def test_run_daily_estados_por_hora_suman_uno(db, cfg):
    """La curva de Márkov del veredicto: 16 horas (06-21), filas que suman 1."""
    v = pipeline.run_daily(db, FECHA, cfg=cfg, n_iter=N_ITER)
    filas = v["estados_por_hora"]
    assert len(filas) == 16
    assert [f["hour"] for f in filas] == list(range(6, 22))
    for fila in filas:
        total = sum(fila[f"P_{estado}"] for estado in markov.ESTADOS)
        assert total == pytest.approx(1.0, abs=1e-3)   # valores redondeados a 4 dec.


def test_run_daily_persiste_prediccion(db, cfg):
    """save_prediction persiste el veredicto completo y recuperable con get_predictions."""
    v = pipeline.run_daily(db, FECHA, cfg=cfg, n_iter=N_ITER)
    preds = db.get_predictions(FECHA)
    assert len(preds) == 1
    assert preds.iloc[0]["computed_at"] == v["computed_at"]
    payload = preds.iloc[0]["payload"]
    assert payload["hora_optima"] == v["hora_optima"]
    assert payload["prob_ventana"] == v["prob_ventana"]
    assert payload["estados_por_hora"] == v["estados_por_hora"]
    assert payload["n_iter"] == N_ITER


# --------------------------------------------------------- auditoría G8 -----

def test_run_daily_un_solo_monte_carlo(db, cfg):
    """Auditoría G8: run_daily ejecuta simulate_ensemble UNA sola vez
    (antes: doble MC — simulate_day + curva_markov con el mismo ensemble)."""
    with mock.patch.object(pipeline.montecarlo, "simulate_ensemble",
                           wraps=pipeline.montecarlo.simulate_ensemble) as espia:
        pipeline.run_daily(db, FECHA, cfg=cfg, n_iter=N_ITER)
    assert espia.call_count == 1


def test_run_daily_mc_y_markov_comparten_ensemble(db, cfg, dia_verano_cordoba):
    """El MC y la curva de Márkov del pipeline provienen del MISMO ensemble:
    reproducirlos con las funciones sobre un ensemble manual da idénticos."""
    v = pipeline.run_daily(db, FECHA, cfg=cfg, n_iter=N_ITER)
    ens = montecarlo.simulate_ensemble(dia_verano_cordoba, cfg, n_iter=N_ITER,
                                       seed=cfg.montecarlo.seed)
    r = montecarlo.simulate_day_desde_ensemble(ens)
    assert v["hora_optima"] == pipeline._hhmm(r.median_hour)
    assert v["prob_ventana"] == pytest.approx(r.prob_ventana, abs=1e-3)
    assert v["prob_riesgo"] == pytest.approx(r.prob_fase3, abs=1e-3)
    # La curva de Márkov del pipeline = curva_markov_desde_ensemble del ensamble
    curva = markov.curva_markov_desde_ensemble(ens, cfg)
    filas = [{k: (round(float(x), 4) if isinstance(x, float) else int(x))
              for k, x in fila.items()}
             for fila in curva.to_dict("records")]
    assert v["estados_por_hora"] == filas


def test_curva_markov_delega_en_desde_ensemble(cfg, dia_verano_cordoba):
    """La API pública curva_markov sigue funcionando y coincide con la variante
    _desde_ensemble sobre el mismo ensamble (contrato no roto por G8)."""
    n = cfg.markov.iterations
    publica = markov.curva_markov(dia_verano_cordoba, cfg, n_iter=n, seed=42)
    ens = montecarlo.simulate_ensemble(dia_verano_cordoba, cfg, n_iter=n, seed=42)
    variante = markov.curva_markov_desde_ensemble(ens, cfg)
    assert list(publica.columns) == list(variante.columns)
    assert publica.equals(variante)


# ------------------------------------------------- recalc con campo real ----

def test_recalc_with_field_data_usa_lecturas(db, cfg):
    """Con lecturas reales se calcula el sesgo (temp +2, HR −5, viento −1.5) y
    el recalculado persiste como una predicción."""
    # A las 12h el forecast prevé T=31, HR=40, V=2.5 (dia_verano_cordoba)
    db.save_reading(FECHA, "12:00", None, None, None, 33.0, 35.0, 1.0, "mediodía")
    v = pipeline.recalc_with_field_data(db, FECHA, cfg=cfg, n_iter=N_ITER)
    assert v["bias"]["temp_c"] == pytest.approx(2.0, abs=1e-6)     # 33 − 31
    assert v["bias"]["rh_pct"] == pytest.approx(-5.0, abs=1e-6)    # 35 − 40
    assert v["bias"]["wind_ms"] == pytest.approx(-1.5, abs=1e-6)   # 1.0 − 2.5
    assert v["n_iter"] == N_ITER
    # _ultimo_meteo usa la lectura real para las alertas (HR 35% → sin aviso rojo)
    assert all(a["codigo"] != "hr_peligro" for a in v["alertas"])
    preds = db.get_predictions(FECHA)
    assert len(preds) == 1
    assert preds.iloc[0]["payload"]["bias"] == v["bias"]


# --------------------------------------------------------- auditoría M9 -----

def test_tiempos_en_zona_horaria_salina(db, cfg):
    """Auditoría M9: computed_at lleva el desplazamiento horario de Europa/Madrid."""
    v = pipeline.run_daily(db, FECHA, cfg=cfg, n_iter=150)
    assert re.fullmatch(r"\d{2}:\d{2}", v["hora_veredicto"])
    assert re.search(r"[+-]\d{2}:\d{2}$", v["computed_at"]), \
        "computed_at debe llevar el offset de la tz de la salina"


def test_fallback_hora_local_si_tz_invalida(db, cfg):
    """Si la tz de la salina no existe, se cae a la hora local (sin offset)."""
    cfg_local = copy.deepcopy(cfg)
    cfg_local.location.timezone = "Zona/Inexistente"
    v = pipeline.run_daily(db, FECHA, cfg=cfg_local, n_iter=150)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", v["computed_at"])
    assert re.fullmatch(r"\d{2}:\d{2}", v["hora_veredicto"])
