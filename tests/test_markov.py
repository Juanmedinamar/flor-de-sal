"""Tests de la capa de Márkov — estados, matrices, propagación y COHERENCIA MC↔Márkov.

Contrato (AGENTS.md §Capa de Márkov): la propagación π(h+1) = π(h)·T(h) debe
reproducir las marginales del ensemble del Monte Carlo (tolerancia 0.08 en
P(ventana)), con T(h) estimada contando saltos de estado entre horas
consecutivas de los mismos escenarios (mismo seed → mismo ensemble).
"""
from __future__ import annotations

import numpy as np
import pytest

from src import markov, montecarlo
from src.montecarlo import EnsembleResult

SEED = 42
N_ITER = 1000


def _ens_sintetico() -> EnsembleResult:
    """Ensemble sintético de 2 escenarios × 5 horas con ids de estado conocidos.

    umbral = 318 g/l y margen_critico_g_l = 15 → umbral − margen = 303 g/l:
      - 300.0 < 303 → 0 (inactivo); 303.0 >= 303 → 1 (justo en el límite);
      - fase 1 → 2, fase 2 → 3, fase 3 → 4.
    """
    horas = np.array([6.0, 8.0, 10.0, 12.0, 14.0])
    return EnsembleResult(
        hours=horas,
        c_g_l=np.array([[300.0, 303.0, 317.9, 325.0, 330.0],
                        [302.9, 303.1, 310.0, 325.0, 330.0]]),
        umbral=np.full((2, 5), 318.0),
        fase=np.array([[0, 0, 1, 2, 3],
                       [0, 0, 0, 2, 3]], dtype=np.int8),
        apertura=np.array([16.0, 16.0]),
        cierre=np.array([20.0, 20.0]),
        optima=np.array([18.0, 18.0]),
        valid=np.array([True, True]),
        riesgo_duro=np.array([False, False]),
        n_iter=2,
    )


# ---------------------------------------------------------------- estados ----

def test_estados_por_escenario_sintetico(cfg):
    """Caso sintético: ids esperados, incluido el límite umbral − margen."""
    ens = _ens_sintetico()
    estados = markov.estados_por_escenario(ens, cfg)
    assert estados.shape == (2, 5)
    assert estados.dtype == np.int8
    # fila 0: 300<303→0, 303>=303→1 (límite inclusivo), fase1→2, fase2→3, fase3→4
    assert estados[0].tolist() == [0, 1, 2, 3, 4]
    # fila 1: fase 0 las tres primeras horas (302.9<303→0; 303.1 y 310>=303→1)
    assert estados[1].tolist() == [0, 1, 1, 3, 4]


def test_estados_por_escenario_coherente_con_fase(cfg, dia_verano_cordoba):
    """Los ids derivados respetan la semántica de alerts.evaluar_fase (fase 0-3)."""
    ens = montecarlo.simulate_ensemble(dia_verano_cordoba, cfg,
                                       n_iter=N_ITER, seed=SEED)
    estados = markov.estados_por_escenario(ens, cfg)
    margen = cfg.markov.margen_critico_g_l
    critico = ens.c_g_l >= ens.umbral - margen
    assert np.all(estados[ens.fase == 1] == 2)   # nucleación
    assert np.all(estados[ens.fase == 2] == 3)   # ventana
    assert np.all(estados[ens.fase == 3] == 4)   # degradación
    assert np.all(estados[(ens.fase == 0) & critico] == 1)
    assert np.all(estados[(ens.fase == 0) & ~critico] == 0)
    assert np.all(np.isin(estados, [0, 1, 2, 3, 4]))


# -------------------------------------------------------------- matrices ----

def test_estimar_matrices_shape_filas_suman_uno(cfg, dia_verano_cordoba):
    """Shape (h-1, 5, 5), matrices[k] transiciona hours[k]→hours[k+1], sin NaN."""
    hours, matrices = markov.estimar_matrices(dia_verano_cordoba, cfg,
                                              n_iter=400, seed=SEED)
    assert hours.shape == (16,)                      # 06:00–21:00
    assert matrices.shape == (15, 5, 5)              # h-1 transiciones
    assert not np.isnan(matrices).any()
    assert np.all(matrices >= 0.0)
    np.testing.assert_allclose(matrices.sum(axis=2), 1.0, atol=1e-12)


def test_estimar_matrices_fila_sin_observaciones_identidad(cfg, dia_nublado_humedo):
    """Fila sin escenarios → distribución unitaria en su propio estado.

    En el día nublado los estados 2 (nucleación) y 3 (ventana) NUNCA se ocupan
    (la salmuera no llega al umbral), y a las 06:00 ningún escenario está en
    estado 0: esas filas deben ser unitarias (auto-transición con p=1).
    """
    ens = montecarlo.simulate_ensemble(dia_nublado_humedo, cfg,
                                       n_iter=N_ITER, seed=SEED)
    estados = markov.estados_por_escenario(ens, cfg)
    hours, matrices = markov.estimar_matrices(dia_nublado_humedo, cfg,
                                              n_iter=N_ITER, seed=SEED)
    identidad = np.eye(5)
    for k in range(len(hours) - 1):
        for i in range(5):
            if not np.any(estados[:, k] == i):       # fila i sin observaciones
                np.testing.assert_allclose(matrices[k, i], identidad[i],
                                           atol=1e-12)
    # regla comprobada de forma independiente: la hora 0 está toda en degradación
    assert np.all(estados[:, 0] == 4)
    np.testing.assert_allclose(matrices[0, 0], identidad[0], atol=1e-12)
    np.testing.assert_allclose(matrices[:, 2, 2], 1.0)   # nucleación: jamás ocupada
    np.testing.assert_allclose(matrices[:, 3, 3], 1.0)   # ventana: jamás ocupada


def test_estimar_matrices_default_markov_iterations(cfg, dia_verano_cordoba):
    """Sin n_iter usa cfg.markov.iterations (mismo resultado que explícito)."""
    _, a = markov.estimar_matrices(dia_verano_cordoba, cfg, seed=SEED)
    _, b = markov.estimar_matrices(dia_verano_cordoba, cfg,
                                   n_iter=cfg.markov.iterations, seed=SEED)
    np.testing.assert_array_equal(a, b)
    assert a.shape == (15, 5, 5)  # = cfg.markov.iterations por defecto


# ------------------------------------------------------------ propagación ----

def test_propagar_estado_inicial_y_filas_suman_uno():
    """π(0) unitaria en estado_inicial; π(k+1)=π(k)·T(k); filas suman 1."""
    # matrices "de desplazamiento": estado i → estado (i+1) mod 5 con p=1
    matriz = np.roll(np.eye(5), 1, axis=1)
    matrices = np.repeat(matriz[None, :, :], 4, axis=0)   # (4, 5, 5)
    pi = markov.propagar(matrices, n_horas=5, estado_inicial=0)
    assert pi.shape == (5, 5)
    np.testing.assert_allclose(pi.sum(axis=1), 1.0, atol=1e-12)
    # cada hora avanza exactamente un estado
    for k in range(5):
        esperado = np.zeros(5)
        esperado[k % 5] = 1.0
        np.testing.assert_allclose(pi[k], esperado, atol=1e-12)
    # otro estado inicial
    pi3 = markov.propagar(matrices, n_horas=5, estado_inicial=3)
    assert pi3[0, 3] == 1.0 and pi3[1, 4] == 1.0


def test_propagar_formula_y_bordes():
    """Verifica π(k+1) = π(k)·T(k) con matrices arbitrarias y casos límite."""
    rng = np.random.default_rng(0)
    crudo = rng.random((3, 5, 5))
    matrices = crudo / crudo.sum(axis=2, keepdims=True)   # estocásticas
    pi = markov.propagar(matrices, n_horas=4, estado_inicial=2)
    assert pi[0, 2] == 1.0
    for k in range(3):
        np.testing.assert_allclose(pi[k + 1], pi[k] @ matrices[k], atol=1e-12)
    np.testing.assert_allclose(pi.sum(axis=1), 1.0, atol=1e-12)
    # sin matrices (n_horas=1) → solo la inicial; estado inválido → error
    una = markov.propagar(np.zeros((0, 5, 5)), n_horas=1)
    assert una.shape == (1, 5) and una[0, 0] == 1.0
    with pytest.raises(ValueError):
        markov.propagar(matrices, n_horas=4, estado_inicial=7)


# ------------------------------------------------------------- coherencia ----

def test_coherencia_mc_markov_verano(cfg, dia_verano_cordoba):
    """COHERENCIA MC↔Márkov: P(ventana) de la propagación ≈ fracción real de
    escenarios en Fase 2 esa misma hora (tolerancia abs ≤ 0.08, n_iter=1000,
    mismo seed). Ambas rutas usan montecarlo.simulate_ensemble (solo lectura).
    """
    hours, matrices = markov.estimar_matrices(dia_verano_cordoba, cfg,
                                              n_iter=N_ITER, seed=SEED)
    pi = markov.propagar(matrices, hours.size)
    ens = montecarlo.simulate_ensemble(dia_verano_cordoba, cfg,
                                       n_iter=N_ITER, seed=SEED)
    assert np.array_equal(hours, ens.hours)
    fracc_real = (ens.fase == 2).mean(axis=0)          # Fase 2 = ventana
    error = np.abs(pi[:, 3] - fracc_real)              # estado 3 = ventana
    assert error.max() <= 0.08, f"desviación MC↔Márkov {error.max():.4f} > 0.08"
    # la ventana aparece por la tarde (nucleación ~14h) y es mayoritaria
    tarde = (hours >= 16.0) & (hours <= 18.0)
    assert pi[tarde, 3].max() >= 0.8
    assert np.all(pi[hours <= 12.0, 3] <= 0.05)        # por la mañana, nada


def test_coherencia_mc_markov_nublado(cfg, dia_nublado_humedo):
    """Misma coherencia en el día nublado: P(ventana) ≈ 0 (igual que el MC)."""
    hours, matrices = markov.estimar_matrices(dia_nublado_humedo, cfg,
                                              n_iter=N_ITER, seed=SEED)
    pi = markov.propagar(matrices, hours.size)
    ens = montecarlo.simulate_ensemble(dia_nublado_humedo, cfg,
                                       n_iter=N_ITER, seed=SEED)
    fracc_real = (ens.fase == 2).mean(axis=0)
    assert np.abs(pi[:, 3] - fracc_real).max() <= 0.08
    assert fracc_real.max() == 0.0                      # el MC tampoco abre ventana
    assert pi[:, 3].max() <= 0.08


def test_dia_nublado_ventana_cero_probabilidad_en_reposo(cfg, dia_nublado_humedo):
    """Día nublado: P(ventana) cerca de 0 toda la tarde y probabilidad
    concentrada en los estados de NO cosecha (arranca en 'inactivo'; después la
    HR > 65% mantiene la masa en degradación/Fase 3 — rehidratación del PDF).
    """
    curva = markov.curva_markov(dia_nublado_humedo, cfg,
                                n_iter=N_ITER, seed=SEED)
    tarde = curva["hour"] >= 12.0
    assert curva.loc[tarde, "P_ventana"].max() <= 0.08
    assert curva["P_ventana"].max() <= 0.08
    assert curva["P_nucleacion"].max() <= 0.08
    # masa en estados que NO son cosecha: inactivo + crítica + degradación
    no_cosecha = (curva["P_inactivo"] + curva["P_concentracion_critica"]
                  + curva["P_degradacion"])
    assert no_cosecha.min() >= 0.95
    # al amanecer la cadena está en 'inactivo' (π(0)=e_0 y la hora 0 sin obs.)
    manana = curva[curva["hour"].isin([6.0, 7.0])]
    assert (manana["P_inactivo"] >= 0.95).all()


# ------------------------------------------------------------ curva UI ------

def test_curva_markov_columnas_exactas_y_filas(cfg, dia_verano_cordoba):
    """Columnas EXACTAS hour + P_<estado> (5 estados, sin duplicados), filas ≈ 1."""
    curva = markov.curva_markov(dia_verano_cordoba, cfg,
                                n_iter=N_ITER, seed=SEED)
    assert list(curva.columns) == [
        "hour", "P_inactivo", "P_concentracion_critica", "P_nucleacion",
        "P_ventana", "P_degradacion",
    ]
    assert len(curva) == 16                            # 06:00–21:00
    assert list(curva["hour"]) == list(range(6, 22))
    cols = [c for c in curva.columns if c.startswith("P_")]
    np.testing.assert_allclose(curva[cols].sum(axis=1), 1.0, atol=1e-12)
    assert ((curva[cols] >= 0.0) & (curva[cols] <= 1.0)).all().all()
    # reproducible con el mismo seed
    otra = markov.curva_markov(dia_verano_cordoba, cfg,
                               n_iter=N_ITER, seed=SEED)
    np.testing.assert_array_equal(curva.to_numpy(), otra.to_numpy())
