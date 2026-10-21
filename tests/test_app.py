"""Tests de la UI (Streamlit AppTest): humo de las dos secciones, sin red.

La app se ejecuta contra una base de datos temporal (`FLOR_DESAL_DB`) con una
previsión sintética del día (fixture `dia_verano_cordoba`) y unas filas de
`season_runs` de mentira, de modo que `pipeline._ensure_forecast` nunca necesita
red: si algo intentara descargar, el test falla con un mensaje claro. Ambos
gráficos y todos los paneles se pintan de verdad (los 7 gráficos de Temporada
incluidos).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parents[1]
APP = RAIZ / "app" / "streamlit_app.py"


def _fechas_de_hoy() -> set[str]:
    """«Hoy» según la tz de config.yaml y, por si acaso, la tz local del sistema."""
    from src.config import load_config

    fechas = {datetime.now().date().isoformat()}
    try:
        tz = ZoneInfo(str(load_config().location.timezone))
        fechas.add(datetime.now(tz).date().isoformat())
    except Exception:   # tz no disponible en este sistema
        pass
    return fechas


def _filas_temporada(start: str, end: str) -> list[dict]:
    """Filas sintéticas de `season_runs` (dos de cada cuatro días con ventana)."""
    import pandas as pd

    filas: list[dict] = []
    for i, fecha in enumerate(pd.date_range(start, end, freq="17D")):
        con_ventana = i % 4 != 3
        filas.append({
            "date": fecha.date().isoformat(),
            "window_start": "16:15" if con_ventana else None,
            "window_end": "19:30" if con_ventana else None,
            "hora_optima": "17:45" if con_ventana else None,
            "ci_low": "16:30" if con_ventana else None,
            "ci_high": "18:30" if con_ventana else None,
            "prob_ventana": round(max(0.05, 0.85 - 0.05 * i), 2) if con_ventana else 0.0,
            "prob_riesgo": 0.12,
            "calidad": "ok",
            "n_iter": 300,
        })
    return filas


@pytest.fixture(scope="module")
def db_ruta(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Ruta de DB estable para todo el módulo (la app la cachea al importar)."""
    return tmp_path_factory.mktemp("flor_desal_ui") / "test.db"


@pytest.fixture(autouse=True)
def _ui_sin_red(db_ruta: Path, monkeypatch: pytest.MonkeyPatch,
                dia_verano_cordoba, cfg):
    """DB aislada + previsión de hoy y temporada sintéticas + red bloqueada."""
    from src import weather
    from src.db import Database

    monkeypatch.setenv("FLOR_DESAL_DB", str(db_ruta))

    def _prohibida(*_args, **_kwargs):
        raise AssertionError("los tests de UI no deben usar la red")

    monkeypatch.setattr(weather, "fetch_forecast", _prohibida)

    db = Database(str(db_ruta))
    db.init_schema()
    for fecha in _fechas_de_hoy():
        db.save_forecast(fecha, dia_verano_cordoba)
    db.save_season_runs(str(cfg.season.start_date), str(cfg.season.end_date),
                        _filas_temporada(str(cfg.season.start_date),
                                         str(cfg.season.end_date)))
    return db_ruta


def _abrir() -> AppTest:
    """AppTest del punto de entrada real (`streamlit run app/streamlit_app.py`)."""
    return AppTest.from_file(str(APP), default_timeout=90)


def _textos(at: AppTest) -> str:
    """Concatenación de los textos visibles (subheaders, métricas, markdown…)."""
    partes = [str(s.value) for s in at.subheader]
    partes += [str(m.value) for m in at.markdown]
    partes += [f"{m.label} {m.value}" for m in at.metric]
    return " · ".join(partes)


def test_seccion_hoy_sin_excepciones() -> None:
    """La sección 🌞 Hoy pinta veredicto, gráficos y formulario sin excepciones."""
    at = _abrir().run()

    assert at.exception == [], f"excepción en Hoy: {at.exception}"
    assert [t.value for t in at.title] == ["🧂 Flor de Sal — Hora óptima de recolección"]
    visibles = _textos(at)
    assert "Veredicto del día" in visibles
    assert "Semáforo probabilístico de la balsa" in visibles
    assert "Campana de probabilidad de la hora óptima" in visibles
    assert "Tabla horaria del día" in visibles
    assert "Datos reales de campo" in visibles
    assert "Fuente del modelo" in visibles            # pie
    assert len(at.metric) >= 4                        # 4 métricas del veredicto
    assert not [e for e in at.error if "No se pudo calcular" in str(e.value)]


def test_seccion_temporada_sin_excepciones() -> None:
    """La sección 📆 Temporada pinta KPIs y sus 7 gráficas sin excepciones."""
    at = _abrir().run()
    assert at.exception == [], f"excepción al abrir Hoy: {at.exception}"

    at.radio(key="seccion").set_value("📆 Temporada").run()

    assert at.exception == [], f"excepción en Temporada: {at.exception}"
    visibles = _textos(at)
    assert "Días simulados" in visibles               # KPIs
    assert "Mapa de calor de la temporada" in visibles
    assert "Probabilidad de ventana día a día" in visibles
    assert "Distribución de la hora óptima" in visibles
    assert "Hora óptima por mes" in visibles
    assert "Días con ventana por mes" in visibles
    assert "Top-10 mejores días" in visibles
    assert "Fuente del modelo" in visibles            # pie
