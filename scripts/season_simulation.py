"""Simulación de temporada completa de flor de sal con datos reales (ERA5).

Recorre un rango de fechas con la meteorología observada/reanálisis de Open-Meteo
Archive, ejecuta el Monte Carlo por día (bias = 0: sin lecturas de campo de esa
temporada, ver AGENTS.md) y guarda los veredictos en la tabla `season_runs`.

Uso:
    python3 scripts/season_simulation.py                          # temporada de config.yaml
    python3 scripts/season_simulation.py --start 2026-06-01 --end 2026-06-05
    python3 scripts/season_simulation.py --iters 500
    python3 scripts/season_simulation.py --workers 2

Opciones:
    --start YYYY-MM-DD   inicio (por defecto cfg.season.start_date)
    --end   YYYY-MM-DD   fin    (por defecto cfg.season.end_date)
    --iters N            iteraciones Monte Carlo por día (por defecto cfg.season.iterations)
    --workers N          procesos paralelos (0 = auto min(4, CPU); 1 = serie;
                         por defecto cfg.season.workers — auditoría G7)

Flujo: init_schema → fetch_archive → calidad_datos → por cada día
montecarlo.simulate_day(dia, cfg, n_iter=iters) → db.save_season_runs(...).
Los días sin ventana quedan con window_start/hora_optima = None (NULL en DB).

Concurrencia (auditoría G7): los días se simulan con ProcessPoolExecutor.
El paralelismo NO cambia resultados: cada día se simula con la MISMA semilla
(cfg.montecarlo.seed, ver montecarlo.simulate_day), y los resultados se ordenan
por fecha antes de guardarlo. Si el pool falla (o workers<=1), se degrada a serie.
"""
from __future__ import annotations

import argparse
import math
import os
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context, set_forkserver_preload

import pandas as pd

from src import historical, montecarlo
from src.config import Config, load_config
from src.db import Database
from src.pipeline import _hhmm

# Pre-importa los módulos pesados en el servidor "forkserver" (una sola vez por
# proceso padre): los hijos nacen ya con pandas/numpy cargados y el fork ocurre
# en un proceso mono-hilo — rápido y sin el DeprecationWarning de Python 3.13
# ("multi-threaded, use of fork()") que daría el "fork" directo.
set_forkserver_preload(["pandas", "numpy"])


def _calidad_dia(dia) -> str:
    """Calidad de UN día: 24 horas → "completo"; si no, nº de horas disponibles."""
    n = len(dia)
    return "completo" if n == 24 else f"parcial: {n} h"


def _resuelve_workers(workers: int | None, cfg: Config) -> int:
    """Nº de procesos a usar: None → cfg.season.workers; 0 → auto; nunca < 1.

    - 0 (auto): min(4, nº de CPU) — suficiente para la salina y para no saturar
      una máquina pequeña (auditoría G7).
    - 1: serie.
    - N > 1: nº fijo de procesos.
    """
    if workers is None:
        workers = int(cfg.season.get("workers", 1))
    if workers <= 0:
        return max(1, min(4, os.cpu_count() or 1))
    return workers


def _simular_dia(tarea: tuple[str, pd.DataFrame, Config, int]) -> tuple[dict, float, float]:
    """Simula UN día y devuelve (fila para season_runs, prob_ventana, hora óptima decimal).

    Función de worker de nivel de módulo: debe ser picklable para ProcessPoolExecutor.
    Cada día se simula con la MISMA semilla (cfg.montecarlo.seed →
    montecarlo.simulate_day), por lo que el paralelismo NO cambia los resultados
    (determinismo, auditoría G7).
    """
    fecha, dia, cfg, n_iter = tarea
    r = montecarlo.simulate_day(dia, cfg, n_iter=n_iter)
    fila = {
        "date": fecha,
        "window_start": _hhmm(r.window_start_median),
        "window_end": _hhmm(r.window_end_median),
        "hora_optima": _hhmm(r.median_hour),     # None si no hay ventana (NULL)
        "ci_low": _hhmm(r.ci_low),
        "ci_high": _hhmm(r.ci_high),
        "prob_ventana": round(r.prob_ventana, 4),
        "prob_riesgo": round(r.prob_fase3, 4),   # columna season_runs.prob_riesgo
        "calidad": _calidad_dia(dia),
        "n_iter": r.n_iter,
    }
    return fila, float(r.prob_ventana), float(r.median_hour)


def _contexto_procesos():
    """Contexto de multiprocessing: "forkserver" si existe (hijos rápidos y
    mono-hilo), si no "spawn", y si no hay ningún método (plataforma rara)
    devuelve None → el caller degrada a serie.

    Nunca se usa "fork" directamente: desde un proceso multi-hilo (Streamlit)
    Python 3.13 lo marca como DeprecationWarning por riesgo de deadlock.
    """
    for nombre in ("forkserver", "spawn"):
        try:
            return get_context(nombre)
        except ValueError:
            continue
    return None


def _simular_dias(dias: list[tuple[str, pd.DataFrame]], cfg: Config,
                  n_iter: int, workers: int) -> list[tuple[dict, float, float]]:
    """Simula la lista de días (paralelo si workers>1) con resultados ordenados por fecha.

    Degradación a serie (auditoría G7): si workers<=1 o el pool lanza cualquier
    excepción (pickling, memoria, señal…), se simula todo en serie — el veredicto
    es el mismo, solo tarda más.
    """
    tareas = [(fecha, dia, cfg, n_iter) for fecha, dia in dias]
    resultados: list[tuple[dict, float, float]] | None = None
    if workers > 1 and tareas:
        ctx = _contexto_procesos()   # None → sin multiprocessing → serie
        try:
            if ctx is None:
                raise RuntimeError("sin método de procesos disponible")
            chunksize = max(1, len(tareas) // (workers * 4))
            # "forkserver" en lugar de "fork": el fork se hace en un proceso
            # mono-hilo (evita el DeprecationWarning de Python 3.13 y el riesgo
            # de deadlock al lanzarse desde Streamlit). Fallback a "spawn" y,
            # si no hay método de proceso, degradación a serie más abajo.
            with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as pool:
                resultados = list(pool.map(_simular_dia, tareas, chunksize=chunksize))
        except Exception as exc:  # cualquier fallo del pool → degradar a serie (G7)
            print(f"Aviso: el paralelismo con {workers} procesos falló ({exc});"
                  " se continúa en serie.")
    if resultados is None:
        resultados = [_simular_dia(t) for t in tareas]
    resultados.sort(key=lambda t: t[0]["date"])   # determinismo: mismo orden que en serie
    return resultados


def run_season(start_date: str, end_date: str, n_iter: int,
               cfg: Config | None = None, db: Database | None = None,
               workers: int | None = None) -> dict:
    """Simula el rango [start_date, end_date] día a día y guarda los veredictos.

    Args:
        start_date: Inicio "YYYY-MM-DD" (inclusivo).
        end_date: Fin "YYYY-MM-DD" (inclusivo).
        n_iter: Iteraciones de Monte Carlo por día.
        cfg: Configuración (por defecto load_config()).
        db: Base de datos (por defecto Database() → data/flor_desal.db).
        workers: Procesos paralelos (None → cfg.season.workers; 0 = auto;
            1 = serie; ver _resuelve_workers).

    Returns:
        Resumen (ver _resumen): días simulados, días con ventana, probabilidades,
        hora óptima mediana/rango, calidad del rango, tiempo, nº de procesos y
        ruta de la DB.
    """
    cfg = cfg or load_config()
    db = db or Database()
    db.init_schema()

    t0 = time.perf_counter()
    df = historical.fetch_archive(
        start_date, end_date,
        float(cfg.location.latitude), float(cfg.location.longitude),
        str(cfg.location.timezone), cfg=cfg,
    )
    calidad_rango = historical.calidad_datos(df, start_date, end_date)

    n_workers = _resuelve_workers(workers, cfg)
    dias = list(historical.iter_days(df, start_date, end_date))
    resultados = _simular_dias(dias, cfg, n_iter, n_workers)

    filas = [fila for fila, _prob, _optima in resultados]
    probs = [prob for _fila, prob, _optima in resultados]
    optimas = [optima for _fila, _prob, optima in resultados
               if not math.isnan(optima)]   # hubo ventana de cosecha

    n_guardadas = db.save_season_runs(start_date, end_date, filas)
    segundos = time.perf_counter() - t0

    return _resumen(start_date, end_date, n_iter, filas, optimas, probs,
                    calidad_rango, n_guardadas, segundos, db.path, n_workers)


def _resumen(start_date: str, end_date: str, n_iter: int, filas: list[dict],
             optimas: list[float], probs: list[float], calidad_rango: str,
             n_guardadas: int, segundos: float, db_path, workers: int) -> dict:
    """Agrega los veredictos diarios en el resumen de la temporada."""
    con_ventana = [f for f in filas if f["hora_optima"] is not None]
    horas_txt = sorted(f["hora_optima"] for f in con_ventana)  # "HH:MM" = orden cronológico
    return {
        "start_date": start_date,
        "end_date": end_date,
        "n_iter": n_iter,
        "n_dias": len(filas),
        "n_guardadas": n_guardadas,
        "n_con_ventana": len(con_ventana),
        "prob_media": (sum(probs) / len(probs)) if probs else 0.0,
        "optima_mediana": _hhmm(statistics.median(optimas)) if optimas else None,
        "optima_min": horas_txt[0] if horas_txt else None,
        "optima_max": horas_txt[-1] if horas_txt else None,
        "optimas_decimales": optimas,
        "calidad": calidad_rango,
        "segundos": segundos,
        "workers": workers,
        "db_path": str(db_path),
        "mejores_dias": sorted(con_ventana, key=lambda f: f["prob_ventana"],
                               reverse=True)[:5],
    }


def imprimir_resumen(resumen: dict) -> None:
    """Imprime por stdout el resumen de run_season (días, ventana, hora óptima, tiempo)."""
    n = resumen["n_dias"]
    cv = resumen["n_con_ventana"]
    print(f"\nTemporada {resumen['start_date']} → {resumen['end_date']} "
          f"(ERA5, {resumen['n_iter']} iteraciones/día)")
    print(f"Calidad de los datos: {resumen['calidad']}")
    if n == 0:
        print("¡No se han simulado días (sin datos en el rango)!")
    else:
        pct = 100.0 * cv / n
        print(f"Días simulados: {n} · con ventana: {cv} ({pct:.0f}%)"
              f" · sin ventana: {n - cv}")
        print(f"Probabilidad media de ventana: {resumen['prob_media']:.3f}")
        if resumen["optima_mediana"] is not None:
            print(f"Hora óptima mediana: {resumen['optima_mediana']} "
                  f"(rango {resumen['optima_min']}–{resumen['optima_max']})")
        else:
            print("Sin días con ventana de cosecha.")
        if resumen["mejores_dias"]:
            print("Mejores días (prob. de ventana más alta):")
            for f in resumen["mejores_dias"]:
                print(f"  {f['date']}  ventana {f['window_start']}–{f['window_end']}"
                      f"  óptima {f['hora_optima']}  prob {f['prob_ventana']:.3f}")
    print(f"Tiempo total: {resumen['segundos']:.1f} s "
          f"(procesos: {resumen.get('workers', 1)})")
    print(f"Guardado en: {resumen['db_path']} (tabla season_runs, "
          f"rango {resumen['start_date']}..{resumen['end_date']}, "
          f"{resumen['n_guardadas']} filas)")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Argumentos de la CLI: --start, --end, --iters, --workers (por defecto config.yaml)."""
    parser = argparse.ArgumentParser(
        description="Simula la temporada de flor de sal con datos reales ERA5.",
    )
    parser.add_argument("--start", metavar="YYYY-MM-DD",
                        help="fecha de inicio (por defecto: season.start_date de config.yaml)")
    parser.add_argument("--end", metavar="YYYY-MM-DD",
                        help="fecha de fin (por defecto: season.end_date de config.yaml)")
    parser.add_argument("--iters", type=int, metavar="N",
                        help="iteraciones de Monte Carlo por día "
                             "(por defecto: season.iterations de config.yaml)")
    parser.add_argument("--workers", type=int, metavar="N",
                        help="procesos paralelos: 0 = auto (min(4, CPU)), 1 = serie, "
                             ">1 = nº fijo (por defecto: season.workers de config.yaml)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict:
    """CLI: resuelve el rango (opciones o config), simula la temporada e imprime el resumen."""
    args = _parse_args(argv)
    cfg = load_config()

    start = args.start if args.start is not None else str(cfg.season.start_date)
    end = args.end if args.end is not None else str(cfg.season.end_date)
    iters = args.iters if args.iters is not None else int(cfg.season.iterations)
    workers = args.workers if args.workers is not None else None  # None → cfg.season.workers

    for valor, nombre in ((start, "--start"), (end, "--end")):
        try:
            datetime.strptime(valor, "%Y-%m-%d")
        except ValueError:
            print(f"Fecha inválida {valor!r} en {nombre}: se espera formato YYYY-MM-DD.")
            sys.exit(1)
    if iters < 1:
        print(f"--iters debe ser >= 1 (recibido {iters}).")
        sys.exit(1)
    if workers is not None and workers < 0:
        print(f"--workers debe ser >= 0 (recibido {workers}).")
        sys.exit(1)

    resumen = run_season(start, end, iters, cfg=cfg, workers=workers)
    imprimir_resumen(resumen)
    return resumen


if __name__ == "__main__":
    main()
