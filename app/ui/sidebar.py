"""Menú lateral: navegación entre secciones, fecha/descarga y leyenda de fases."""
from __future__ import annotations

from datetime import date

import streamlit as st

from app.ui.constantes import _CFG0, BADGE_FASE, NOMBRE_FASE
from app.ui.helpers import hoy
from app.ui.state import (
    DB_RUTA,
    _cargar_temporada,
    _ejecutar_simulacion_temporada,
    _rango_temporada,
    _rev_temporada,
)
from app.ui.textos import SEMAFORO_FASES, SUBTITULO_SIDEBAR, texto_ubicacion
from src import weather
from src.db import Database


def _pintar_semaforo_fases() -> None:
    """Bloque «Semáforo de fases» (idéntico en las dos secciones del menú)."""
    st.markdown(SEMAFORO_FASES)
    for n, nombre in NOMBRE_FASE.items():
        st.markdown(f"{BADGE_FASE[n]} **Fase {n}** — {nombre}")


def _sidebar(db: Database) -> tuple[date, str]:
    """Navegación (Hoy/Temporada), selector de fecha y leyenda de fases.

    Returns:
        (fecha del veredicto, sección elegida). La fecha solo se usa en «Hoy».
    """
    with st.sidebar:
        st.markdown("## 🧂 Flor de Sal")
        st.caption(SUBTITULO_SIDEBAR)
        seccion = st.radio(
            "📂 Sección", ["🌞 Hoy", "📆 Temporada"], horizontal=True, key="seccion",
            help="«Hoy»: veredicto y datos del día · «Temporada»: simulación histórica.",
        )

        if seccion.startswith("📆"):
            _sidebar_temporada()
            st.divider()
            _pintar_semaforo_fases()
            st.divider()
            st.caption(texto_ubicacion(f"tz {_CFG0.location.timezone}"))
            return hoy(), seccion

        fecha = st.date_input("📅 Fecha del veredicto", value=hoy(),
                              width="stretch", help="Día que quieres estudiar (por defecto, hoy).")
        fecha_s = fecha.isoformat() if isinstance(fecha, date) else str(fecha)
        es_pasado = fecha < hoy()

        # --- Botón 1: previsión futura (Open-Meteo Forecast) ---
        if not es_pasado:
            if st.button("⬇️ Descargar/guardar previsión del día", key="btn_descarga",
                         type="primary", width="stretch",
                         help="Descarga la serie horaria de Open-Meteo Forecast para las coordenadas "
                              "de config.yaml y la guarda en la base de datos local."):
                try:
                    with st.spinner("Descargando previsión de Open-Meteo…"):
                        df = weather.fetch_forecast(
                            float(_CFG0.location.latitude), float(_CFG0.location.longitude),
                            fecha_s, str(_CFG0.location.timezone))
                        n = db.save_forecast(fecha_s, df)
                    st.session_state["rev"] = int(st.session_state.get("rev", 0)) + 1
                    st.session_state["aviso"] = ("ok",
                                                 f"Previsión del {fecha_s} guardada ({n} horas).")
                except Exception as exc:
                    st.session_state["aviso"] = ("err",
                                                 f"No se pudo descargar la previsión: {exc}")
                st.rerun()
        else:
            st.caption("⚠️ Fecha pasada: usa el botón de abajo para simular con datos observados (ERA5).")

        # --- Botón 2: simulación histórica (Open-Meteo Archive / ERA5) ---
        if st.button("🕰️ Simular día histórico (ERA5)", key="btn_historico",
                     type="secondary", width="stretch",
                     help="Descarga la meteorología OBSERVADA (ERA5 / Open-Meteo Archive) para "
                          "esta fecha y la guarda como previsión. Útil para fechas pasadas."):
            try:
                with st.spinner("Descargando ERA5 de Open-Meteo Archive…"):
                    from src import historical
                    df = historical.fetch_archive(
                        fecha_s, fecha_s,
                        float(_CFG0.location.latitude), float(_CFG0.location.longitude),
                        str(_CFG0.location.timezone))
                    n = db.save_forecast(fecha_s, df)
                st.session_state["rev"] = int(st.session_state.get("rev", 0)) + 1
                st.session_state["aviso"] = ("ok",
                                             f"ERA5 del {fecha_s} guardado ({n} horas).")
            except Exception as exc:
                st.session_state["aviso"] = ("err",
                                             f"No se pudo descargar ERA5: {exc}")
            st.rerun()

        st.divider()
        _pintar_semaforo_fases()
        st.divider()
        st.caption(texto_ubicacion(f"tz {_CFG0.location.timezone}"))
    return fecha, seccion


def _sidebar_temporada() -> None:
    """Menú lateral de la sección Temporada: botón de (re)simulación + última salida."""
    start, end = _rango_temporada()
    st.markdown("**📆 Temporada**")
    st.caption(f"{start} → {end} · {int(_CFG0.season.iterations)} iteraciones/día · ERA5")

    df = _cargar_temporada(start, end, _rev_temporada(), DB_RUTA)
    if df is None or df.empty:
        st.info("Sin simulación para este rango. Pulsa el botón para crearla "
                "(≈15 s, datos observados de Open-Meteo Archive).")

    if st.button("🔄 (Re)simular temporada", key="btn_temporada", type="primary",
                 width="stretch",
                 help="Ejecuta scripts/season_simulation.py con la meteorología "
                      "observada (ERA5) del rango de config.yaml y vuelve a guardar "
                      "los resultados en la tabla season_runs."):
        _ejecutar_simulacion_temporada()

    salida = st.session_state.get("salida_temporada")
    if salida:
        with st.expander("📤 Última salida de la simulación"):
            st.code(str(salida)[-3000:], language="text")
