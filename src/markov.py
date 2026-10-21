"""Cadenas de Márkov de los estados de la balsa (PDF pág. 8, §2).

Estados (cfg.markov.estados):
  0 inactivo              — C < umbral − margen_critico_g_l        (Fase 0)
  1 concentracion_critica — umbral − margen <= C < umbral          (Fase 0, "a punto de")
  2 nucleacion            — C >= umbral, en crecimiento            (Fase 1)
  3 ventana               — ventana de cosecha abierta             (Fase 2)
  4 degradacion           — Fase 3 (viento/HR de peligro o repunte) (Fase 3)

Las matrices de transición T(h) [h → h+1] se ESTIMAN del ensemble del Monte
Carlo (src.montecarlo.simulate_ensemble): se cuentan los saltos de estado entre
horas consecutivas de los n escenarios y se normalizan (filas que suman 1).
La propagación π(h+1) = π(h)·T(h) reproduce las marginales del ensemble (ley de
la probabilidad total), y es instantánea: es el "semáforo probabilístico hora a
hora" que se redibuja con cada dato real.

CONTRATO — a implementar por el agente `markov`. Firmas exactas:

    ESTADOS: tuple[str, ...]   # = tuple(cfg.markov.estados)

    def estados_por_escenario(ens: EnsembleResult, cfg: Config) -> np.ndarray
        # (n, h) de ids 0-4 derivados de ens.fase, ens.c_g_l y ens.umbral según la
        # leyenda de arriba (fase0 → 0 u 1 según margen_critico_g_l; 1→2; 2→3; 3→4).

    def estimar_matrices(forecast_df: pd.DataFrame, cfg: Config,
                         bias: dict | None = None, n_iter: int | None = None,
                         seed: int | None = None) -> tuple[np.ndarray, np.ndarray]
        # Ejecuta montecarlo.simulate_ensemble con los mismos argumentos, convierte a
        # estados y devuelve (hours (h,), matrices (h-1, 5, 5)) donde matrices[k]
        # transiciona de hours[k] a hours[k+1]; filas que suman 1 (una fila sin
        # observaciones → distribución unitaria en su propio estado).

    def propagar(matrices: np.ndarray, n_horas: int, estado_inicial: int = 0) -> np.ndarray
        # (n_horas, 5): π(0) = unitaria en estado_inicial; π(k+1) = π(k)·matrices[k].
        # Cada fila suma 1 (conservación de probabilidad).

    def curva_markov(forecast_df: pd.DataFrame, cfg: Config,
                     bias: dict | None = None, n_iter: int | None = None,
                     seed: int | None = None) -> pd.DataFrame
        # Comodín para la UI: columnas hour + P_<estado> por cada estado (0-1),
        # más P_ventana = P_ventana (columna 'P_ventana' para conveniencia).

Tests (tests/test_markov.py):
  - estados_por_escenario: caso sintético conocido → ids esperados (umbral−margen, etc.).
  - matrices: shape correcto, filas suman 1, no hay NaN.
  - propagar: filas suman 1, estado inicial correcto.
  - COHERENCIA MC↔Markov: en dia_verano_cordoba, la P(ventana) hora a hora de la
    propagación ≈ fracción real de escenarios del ensemble en Fase 2 esa hora
    (tolerancia abs ≤ 0.08, n_iter=1000, mismo seed).
  - Día nublado: P(ventana) cerca de 0 toda la tarde; probabilidad concentrada en
    'inactivo'.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from src import montecarlo
from src.config import Config

if TYPE_CHECKING:
    from src.montecarlo import EnsembleResult

ESTADOS: tuple[str, ...] = ("inactivo", "concentracion_critica", "nucleacion",
                            "ventana", "degradacion")

_N_ESTADOS = 5


def estados_por_escenario(ens: EnsembleResult, cfg: Config) -> np.ndarray:
    """Convierte las fases del ensemble en ids de estado de la cadena (0-4).

    Reglas (una por fase de alerts.evaluar_fase):
      - fase 0 (inactividad) → 0 si C < umbral − margen_critico_g_l, en otro
        caso 1 (concentración crítica: "a menos de `margen_critico_g_l` g/l del
        umbral"), es decir  estado = 1 si c_g_l >= umbral − margen.
      - fase 1 (nucleación)  → 2
      - fase 2 (ventana)     → 3
      - fase 3 (degradación) → 4

    Devuelve un ndarray (n_escenarios, h_horas) con dtype int8.
    """
    margen = float(cfg.markov.margen_critico_g_l)
    fase = np.asarray(ens.fase)
    critico = np.asarray(ens.c_g_l) >= np.asarray(ens.umbral) - margen
    estados = np.zeros(fase.shape, dtype=np.int8)
    # fase 0 → 0 (inactivo) o 1 (concentración crítica según el margen)
    estados[fase == 0] = np.where(critico[fase == 0], 1, 0).astype(np.int8)
    estados[fase == 1] = 2   # nucleación
    estados[fase == 2] = 3   # ventana de cosecha
    estados[fase == 3] = 4   # degradación / cierre
    return estados


def _normalizar(conteos: np.ndarray) -> np.ndarray:
    """Normaliza conteos (m, 5, 5) a matrices estocásticas por filas.

    Cada fila i de la matriz T(k) es la distribución condicional P(X_{k+1}=· |
    X_k=i): se divide cada fila por su suma. Una fila sin observaciones (ningún
    escenario estuvo en ese estado a esa hora) → distribución unitaria en su
    propio estado (auto-transición con probabilidad 1).
    """
    matriz = np.array(conteos, dtype=np.float64, copy=True)
    if matriz.size == 0:
        return matriz
    vacias = matriz.sum(axis=2) == 0.0       # (m, 5): fila i sin observaciones
    identidad = np.eye(_N_ESTADOS, dtype=np.float64)[None, :, :]
    matriz = np.where(vacias[..., None], identidad, matriz)  # (m,5,1)→(m,5,5)
    totales = matriz.sum(axis=2, keepdims=True)
    return matriz / np.where(totales == 0.0, 1.0, totales)


def estimar_matrices(forecast_df: pd.DataFrame, cfg: Config,
                     bias: dict | None = None, n_iter: int | None = None,
                     seed: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Estima las matrices de transición hora→hora a partir del ensemble.

    Ejecuta ``montecarlo.simulate_ensemble(forecast_df, cfg, bias, n_iter,
    seed)`` (con ``n_iter`` por defecto ``cfg.markov.iterations``), convierte
    cada escenario/hora a estado con :func:`estados_por_escenario` y CUENTA los
    saltos entre horas consecutivas de los n escenarios, vectorizado con
    ``np.add.at`` (sin bucles por escenario):

        T[k, i, j] = #(escenarios en estado i a hours[k] y en j a hours[k+1])
                     / #(escenarios en estado i a hours[k]]

    Devuelve ``(hours (h,), matrices (h-1, 5, 5))``; ``matrices[k]`` transiciona
    de ``hours[k]`` a ``hours[k+1]``. Filas que suman 1; una fila sin
    observaciones queda como distribución unitaria en su propio estado.
    """
    n = cfg.markov.iterations if n_iter is None else int(n_iter)
    ens = montecarlo.simulate_ensemble(forecast_df, cfg, bias=bias,
                                       n_iter=n, seed=seed)
    estados = estados_por_escenario(ens, cfg)
    hours = np.asarray(ens.hours)
    h = hours.size
    conteos = np.zeros((max(h - 1, 0), _N_ESTADOS, _N_ESTADOS), dtype=np.float64)
    if h >= 2:
        origen = estados[:, :-1].astype(np.intp)          # estado en hours[k]
        destino = estados[:, 1:].astype(np.intp)          # estado en hours[k+1]
        k = np.broadcast_to(np.arange(h - 1, dtype=np.intp)[None, :], origen.shape)
        np.add.at(conteos, (k, origen, destino), 1.0)     # conteos[k, i, j] += 1
    return hours, _normalizar(conteos)


def propagar(matrices: np.ndarray, n_horas: int, estado_inicial: int = 0) -> np.ndarray:
    """Propaga la distribución de probabilidad de estados por el día.

    Fórmula (PDF pág. 8, §2):

        π(0) = e_estado_inicial        (distribución unitaria)
        π(k+1) = π(k) · T(k)           (multiplicación fila × matriz)

    Devuelve un ndarray (n_horas, 5) cuyas filas suman 1 (conservación de la
    probabilidad, porque cada T(k) es estocástica por filas). Si faltan matrices
    (n_horas > matrices.shape[0] + 1) se mantiene la última distribución.
    """
    if not 0 <= estado_inicial < _N_ESTADOS:
        raise ValueError(f"estado_inicial {estado_inicial} fuera de rango 0-4")
    pi = np.zeros((int(n_horas), _N_ESTADOS), dtype=np.float64)
    if pi.shape[0] == 0:
        return pi
    pi[0, estado_inicial] = 1.0
    for k in range(pi.shape[0] - 1):
        # π(k+1) = π(k)·T(k); si no hay T(k), se arrastra π(k)
        pi[k + 1] = pi[k] @ matrices[k] if k < matrices.shape[0] else pi[k]
    return pi


def curva_markov(forecast_df: pd.DataFrame, cfg: Config,
                 bias: dict | None = None, n_iter: int | None = None,
                 seed: int | None = None) -> pd.DataFrame:
    """Semáforo probabilístico hora a hora (comodín para la UI).

    Combina :func:`estimar_matrices` + :func:`propagar` y devuelve un DataFrame
    con exactamente las columnas ``hour`` y ``P_<estado>`` por cada uno de los
    5 estados (valores 0-1): ``P_inactivo``, ``P_concentracion_critica``,
    ``P_nucleacion``, ``P_ventana``, ``P_degradacion``. Cada fila (hora) suma 1.
    Se recalcula al instante con cada dato real nuevo (bias).
    """
    hours, matrices = estimar_matrices(forecast_df, cfg, bias=bias,
                                       n_iter=n_iter, seed=seed)
    pi = propagar(matrices, hours.size)
    datos: dict[str, np.ndarray] = {"hour": hours}
    for i, estado in enumerate(ESTADOS):
        datos[f"P_{estado}"] = pi[:, i]
    return pd.DataFrame(datos)
