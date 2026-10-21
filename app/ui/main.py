"""Orquestación de la app: cabecera, sección elegida y pie de fuentes."""
from __future__ import annotations

from datetime import date

import streamlit as st

from app.ui.constantes import LOGO_BYTES, LOGO_PATH
from app.ui.panel_hoy import (
    _panel_calibracion,
    _panel_campana,
    _panel_cosecha,
    _panel_evolucion,
    _panel_formulario,
    _panel_lecturas,
    _panel_prevision_lecturas,
    _panel_semaforo,
    _panel_tabla,
    _panel_veredicto,
)
from app.ui.panel_temporada import _seccion_temporada
from app.ui.sidebar import _sidebar
from app.ui.state import (
    DB_RUTA,
    _calcular,
    _db,
    _inicializar_calibracion,
    _rango_temporada,
    _valores_calibracion,
)
from app.ui.textos import PIE_AVISO, PIE_FUENTE, TITULO_APP, texto_ubicacion


def _pie(datos: dict | None) -> None:
    """Fuente del modelo y aviso legal."""
    st.divider()
    st.markdown(PIE_FUENTE)
    st.caption(PIE_AVISO)
    if datos:
        v = datos["veredicto"]
        st.caption(f"Veredicto del {v.get('fecha', '—')} · calculado "
                   f"{v.get('computed_at', '—')} · {int(v.get('n_iter') or 0)} escenarios.")


def main() -> None:
    """Pinta la app: sección 🌞 Hoy o sección 📆 Temporada (según el radio)."""
    db = _db()
    db.init_schema()
    st.session_state.setdefault("rev", 0)
    _inicializar_calibracion()

    fecha, seccion = _sidebar(db)
    fecha_s = fecha.isoformat() if isinstance(fecha, date) else str(fecha)

    if LOGO_BYTES is not None:
        st.image(str(LOGO_PATH), width=340)   # "Salinas de Dueñas" (marca)
    st.title(TITULO_APP)
    if seccion.startswith("📆"):
        _start, _end = _rango_temporada()
        st.caption(texto_ubicacion(f"temporada {_start} → {_end} (ERA5)"))
    else:
        st.caption(texto_ubicacion(f"día {fecha_s}"))

    if "aviso" in st.session_state:
        tipo, txt = st.session_state.pop("aviso")
        (st.success if tipo == "ok" else st.error)(txt)

    if seccion.startswith("📆"):
        _seccion_temporada()
        _pie(None)
        return

    lecturas = db.get_readings(fecha_s)
    n_lecturas = 0 if lecturas is None else len(lecturas)
    datos: dict | None = None
    try:
        datos = _calcular(fecha_s, n_lecturas, _valores_calibracion(),
                          int(st.session_state["rev"]), DB_RUTA)
    except Exception as exc:
        st.error(f"**No se pudo calcular el veredicto del {fecha_s}:** {exc}")
        st.info("Si el día todavía no tiene previsión, usa el botón "
                "«⬇️ Descargar/guardar previsión del día» del menú lateral o ejecuta "
                "`python3 scripts/ingest_forecast.py`.")

    if datos:
        _panel_veredicto(datos["veredicto"])
        _panel_semaforo(datos)
        _panel_campana(datos)
        _panel_prevision_lecturas(datos, db, fecha_s)
        _panel_evolucion(db, fecha_s)
        _panel_tabla(datos)
    else:
        st.info("Sin veredicto para esta fecha todavía.")

    st.divider()
    _panel_formulario(db, fecha_s)
    _panel_lecturas(db, fecha_s, (datos["veredicto"].get("bias") if datos else {}) or {})
    _panel_cosecha(db, fecha_s)
    _panel_calibracion()
    _pie(datos)
