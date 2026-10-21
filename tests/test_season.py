"""Tests de la CLI de simulación de temporada (scripts/season_simulation.py).

Sin red: datos sintéticos + round-trip idempotente de save/get_season_runs en tmp_path,
y comprobación de los argumentos de la CLI (defaults de config.yaml y opciones).
Con red (@pytest.mark.integration): rango real corto de junio de 2026.
"""
from __future__ import annotations

import importlib.util
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from src.db import Database
from src.historical import COLUMNAS

ROOT = Path(__file__).resolve().parents[1]

# Carga el script como módulo (scripts/ no es un paquete).
_spec = importlib.util.spec_from_file_location("season_simulation",
                                               ROOT / "scripts" / "season_simulation.py")
assert _spec is not None and _spec.loader is not None
season_sim = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(season_sim)

INICIO = "2026-06-01"
FIN = "2026-06-05"      # 5 días de junio de 2026
COLUMNAS_RUN = ["date", "window_start", "window_end", "hora_optima", "ci_low",
                "ci_high", "prob_ventana", "prob_riesgo", "calidad", "n_iter",
                "computed_at"]


# ---------------------------------------------------------------------------
# Datos sintéticos (sin red)
# ---------------------------------------------------------------------------
def _dia_bueno() -> list[tuple[int, float, float, float, float]]:
    """Día veraniego del escenario del PDF (ampliado a 24 h): debe abrir ventana."""
    return [
        (0, 15.0, 95.0, 0.4, 0.0), (1, 14.5, 96.0, 0.4, 0.0),
        (2, 14.0, 97.0, 0.3, 0.0), (3, 13.5, 97.0, 0.3, 0.0),
        (4, 13.0, 98.0, 0.3, 0.0), (5, 14.0, 96.0, 0.4, 10.0),
        (6, 18.0, 85.0, 0.5, 50.0), (7, 20.0, 75.0, 0.8, 150.0),
        (8, 22.0, 65.0, 1.0, 300.0), (9, 24.0, 60.0, 1.25, 450.0),
        (10, 26.0, 55.0, 1.5, 600.0), (11, 28.5, 47.5, 2.0, 720.0),
        (12, 31.0, 40.0, 2.5, 820.0), (13, 32.5, 35.0, 2.75, 860.0),
        (14, 34.0, 30.0, 3.0, 830.0), (15, 34.5, 29.0, 3.0, 750.0),
        (16, 35.0, 28.0, 3.0, 620.0), (17, 33.5, 30.5, 2.75, 450.0),
        (18, 32.0, 33.0, 2.5, 280.0), (19, 29.0, 39.0, 2.0, 120.0),
        (20, 26.0, 45.0, 1.5, 30.0), (21, 24.0, 52.0, 1.0, 0.0),
        (22, 22.0, 58.0, 1.2, 0.0), (23, 20.0, 65.0, 1.0, 0.0),
    ]


def _dia_mal_ventana() -> list[tuple[int, float, float, float, float]]:
    """Día frío, muy húmedo y sin sol: NO debe abrir ventana (HR ~95 %, T ~15 °C)."""
    return [
        (h, 14.0 + h * 0.15, 99.0 - h * 0.2, 0.3 + h * 0.03,
         max(0.0, 60.0 - abs(h - 13) * 10.0))
        for h in range(24)
    ]


def _archive_sintetico(start: str = INICIO, end: str = FIN) -> pd.DataFrame:
    """24 h/día para [start, end]: 4 días buenos + el último sin ventana."""
    filas: list[dict] = []
    d, fin = date.fromisoformat(start), date.fromisoformat(end)
    i = 0
    while d <= fin:
        es_ultimo = d == fin
        for h, t, hr, v, rad in (_dia_mal_ventana() if es_ultimo else _dia_bueno()):
            filas.append({"date": d.isoformat(), "hour": h, "temp_c": t, "rh_pct": hr,
                          "wind_ms": v, "wind_dir_deg": 180.0, "radiation_w_m2": rad})
        d += timedelta(days=1)
        i += 1
    return pd.DataFrame(filas, columns=COLUMNAS)


@pytest.fixture()
def fetch_sintetico(monkeypatch: pytest.MonkeyPatch) -> pd.DataFrame:
    """Sustituye historical.fetch_archive por datos sintéticos (sin red)."""
    df = _archive_sintetico()
    llamadas: list[tuple[str, str]] = []

    def fake(start_date: str, end_date: str, latitude: float, longitude: float,
             timezone: str = "Europe/Madrid") -> pd.DataFrame:
        llamadas.append((start_date, end_date))
        return df.copy()

    monkeypatch.setattr(season_sim.historical, "fetch_archive", fake)
    monkeypatch.setattr(season_sim, "_llamadas_fetch", llamadas, raising=False)
    return df


# ---------------------------------------------------------------------------
# Sin red: round-trip idempotente de la temporada
# ---------------------------------------------------------------------------
def test_temporada_sintetica_round_trip_idempotente(cfg, tmp_path: Path,
                                                    fetch_sintetico: pd.DataFrame) -> None:
    """run_season dos veces → save_season_runs+get_season_runs sin duplicados ni cambios."""
    db = Database(tmp_path / "temporada.db")

    res1 = season_sim.run_season(INICIO, FIN, 100, cfg=cfg, db=db)
    df1 = db.get_season_runs(INICIO, FIN)

    assert res1["n_dias"] == 5
    assert res1["n_guardadas"] == 5
    assert list(df1.columns) == COLUMNAS_RUN
    assert len(df1) == 5, "la tabla debe tener exactamente 1 fila por día"
    assert df1["date"].tolist() == [(date(2026, 6, 1) + timedelta(days=k)).isoformat()
                                    for k in range(5)]
    assert (df1["n_iter"] == 100).all()
    assert (df1["calidad"] == "completo").all()
    # 4 días buenos con ventana; el último (húmedo/frío) sin ventana → NULL
    assert res1["n_con_ventana"] == 4
    con_ventana = df1[df1["hora_optima"].notna()]
    sin_ventana = df1[df1["hora_optima"].isna()]
    assert len(con_ventana) == 4
    assert len(sin_ventana) == 1
    # NULL en DB → leído como NaN/None por pandas
    assert pd.isna(sin_ventana.iloc[0]["window_start"])
    assert pd.isna(sin_ventana.iloc[0]["window_end"])
    assert pd.isna(sin_ventana.iloc[0]["ci_low"])
    assert pd.isna(sin_ventana.iloc[0]["ci_high"])
    assert sin_ventana.iloc[0]["prob_ventana"] == 0.0
    for fila in con_ventana.itertuples(index=False):
        assert len(fila.hora_optima) == 5 and fila.hora_optima[2] == ":"
        assert not pd.isna(fila.window_start) and not pd.isna(fila.window_end)
        assert 0.0 < fila.prob_ventana <= 1.0
        assert 0.0 <= fila.prob_riesgo <= 1.0
        assert fila.window_start <= fila.hora_optima <= fila.window_end
    # el fetch recibió exactamente el rango pedido
    assert season_sim._llamadas_fetch == [(INICIO, FIN)]

    # Re-ejecutar el MISMO rango es idempotente: mismo nº de filas y mismos valores
    res2 = season_sim.run_season(INICIO, FIN, 100, cfg=cfg, db=db)
    df2 = db.get_season_runs(INICIO, FIN)

    assert res2["n_guardadas"] == 5
    assert len(df2) == 5, "re-ejecutar no debe duplicar filas"
    pd.testing.assert_frame_equal(
        df1.drop(columns=["computed_at"]), df2.drop(columns=["computed_at"]))
    assert res1["n_con_ventana"] == res2["n_con_ventana"]
    assert res1["prob_media"] == pytest.approx(res2["prob_media"])


def test_resumen_de_temporada_sintetica(cfg, tmp_path: Path,
                                        fetch_sintetico: pd.DataFrame) -> None:
    """El resumen agrega días, ventana, prob. media y hora óptima mediana en rango."""
    res = season_sim.run_season(INICIO, FIN, 60, cfg=cfg,
                                db=Database(tmp_path / "resumen.db"))

    assert res["start_date"] == INICIO and res["end_date"] == FIN
    assert res["n_iter"] == 60
    assert res["n_dias"] == 5 and res["n_con_ventana"] == 4
    assert 0.0 < res["prob_media"] <= 1.0
    assert res["optima_min"] <= res["optima_mediana"] <= res["optima_max"]
    assert ":" in res["optima_mediana"]
    assert res["calidad"] == "completo"
    assert res["segundos"] > 0
    assert res["db_path"].endswith("resumen.db")
    assert len(res["mejores_dias"]) == 4

    # imprimir_resumen no falla con el resumen real (smoke test de la salida)
    season_sim.imprimir_resumen(res)


# ---------------------------------------------------------------------------
# Sin red: argumentos de la CLI
# ---------------------------------------------------------------------------
def test_cli_sin_argumentos_usa_config(cfg, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin opciones, la CLI usa cfg.season.{start_date,end_date,iterations}."""
    capturado: dict = {}
    monkeypatch.setattr(season_sim, "run_season",
                        lambda s, e, i, **kw: capturado.update(
                            start=s, end=e, iters=i, kwargs=kw) or {"n_dias": 0})
    monkeypatch.setattr(season_sim, "imprimir_resumen", lambda res: None)

    season_sim.main([])

    assert capturado["start"] == str(cfg.season.start_date)
    assert capturado["end"] == str(cfg.season.end_date)
    assert capturado["iters"] == int(cfg.season.iterations)


def test_cli_con_opciones_explicitas(monkeypatch: pytest.MonkeyPatch) -> None:
    """--start/--end/--iters tienen prioridad sobre la configuración."""
    capturado: dict = {}
    monkeypatch.setattr(season_sim, "run_season",
                        lambda s, e, i, **kw: capturado.update(
                            start=s, end=e, iters=i) or {"n_dias": 0})
    monkeypatch.setattr(season_sim, "imprimir_resumen", lambda res: None)

    season_sim.main(["--start", "2026-06-01", "--end", "2026-06-05", "--iters", "42"])

    assert capturado == {"start": "2026-06-01", "end": "2026-06-05", "iters": 42}


def test_cli_fecha_invalida_sale_con_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Una fecha mal formada aborta con exit code 1 sin simular nada."""
    monkeypatch.setattr(season_sim, "run_season",
                        lambda *a, **kw: pytest.fail("no debe simularse"))
    with pytest.raises(SystemExit) as exc:
        season_sim.main(["--start", "ayer"])
    assert exc.value.code == 1


def test_cli_iters_invalido_sale_con_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """--iters < 1 aborta con exit code 1 sin simular nada."""
    monkeypatch.setattr(season_sim, "run_season",
                        lambda *a, **kw: pytest.fail("no debe simularse"))
    with pytest.raises(SystemExit) as exc:
        season_sim.main(["--iters", "0"])
    assert exc.value.code == 1


# ---------------------------------------------------------------------------
# Integración real (red): rango corto de junio de 2026
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_integracion_temporada_real_cinco_dias_junio(cfg, tmp_path: Path) -> None:
    """Cinco días reales de junio de 2026 → 5 filas en season_runs y round-trip."""
    db = Database(tmp_path / "temporada_real.db")

    res = season_sim.run_season(INICIO, FIN, 50, cfg=cfg, db=db)
    df = db.get_season_runs(INICIO, FIN)

    assert res["n_dias"] == 5
    assert res["n_guardadas"] == 5
    assert res["calidad"] in ("completo",) or res["calidad"].startswith("parcial:")
    assert list(df.columns) == COLUMNAS_RUN
    assert len(df) == 5
    assert res["n_con_ventana"] >= 1, "en junio en Córdoba debe haber días con ventana"
    for fila in df.itertuples(index=False):
        for valor in (fila.hora_optima, fila.window_start, fila.window_end,
                      fila.ci_low, fila.ci_high):
            assert pd.isna(valor) or (len(valor) == 5 and valor[2] == ":")
        assert 0.0 <= fila.prob_ventana <= 1.0
        assert fila.n_iter == 50

    # idempotente también con datos reales
    season_sim.run_season(INICIO, FIN, 50, cfg=cfg, db=db)
    assert len(db.get_season_runs(INICIO, FIN)) == 5
    print(f"\n[integración] temporada {INICIO}..{FIN}: {res['n_con_ventana']}/5 días "
          f"con ventana · prob media {res['prob_media']:.3f} · "
          f"óptima mediana {res['optima_mediana']} · {res['segundos']:.1f} s")
