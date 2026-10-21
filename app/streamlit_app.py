"""App Streamlit — Flor de Sal.

App con DOS secciones (radio en el menú lateral): **🌞 Hoy** y **📆 Temporada**.

🌞 HOY — el veredicto del día que produce `pipeline.run_daily` (previsión
Open-Meteo + datos de campo + Monte Carlo):

  1. Selector de fecha y botón de descarga de previsión (sidebar).
  2. Panel de veredicto: semáforo de fase (0 gris · 1 naranja · 2 verde · 3 rojo),
     ventana más probable, hora óptima con IC95, probabilidad de ventana y de
     riesgo (st.progress) y alertas por nivel.
  3. Semáforo probabilístico (Márkov): áreas apiladas hora a hora con los 5
     estados y línea vertical «ahora».
  4. Campana de probabilidad de la hora óptima (plotly, con sombreado del IC95 y
     línea en la mediana) + tabla horaria del día con badge de color por fase.
  5. Previsión vs lecturas reales (T, HR y V) con el sesgo aplicado.
  6. Evolución de la predicción del día (hora óptima + IC95 por cálculo).
  7. Formulario "Datos reales de campo" → db.save_reading y recálculo con
     corrección por sesgo; debajo, las lecturas del día y el bias aplicado.
  8. Panel de calibración (expander) con los parámetros del modelo y botón de
     restablecer.

📆 TEMPORADA — la simulación histórica de `scripts/season_simulation.py`
(tabla `season_runs`): KPIs, mapa de calor calendario, serie diaria de
probabilidad, distribución de horas óptimas + cobertura por hora, box plot por
mes, barras mensuales y Top-10 de días, con botón de (re)simulación.

Uso:  python3 -m streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import date, datetime
from datetime import time as Hora
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.colors import sequential as _SEQUENTIAL

from src import assimilation, montecarlo, physics, weather
from src.config import DB_PATH, Config, load_config
from src.db import Database
from src.pipeline import _hhmm, run_daily

# Logo de la salina (app/assets/logo.png): favicon de la pestaña y cabecera.
# Si no existe, se usa el emoji 🧂 como marca de agua (no debe romper el arranque).
LOGO_PATH = Path(__file__).resolve().parent / "assets" / "logo.png"
try:
    _LOGO_BYTES = LOGO_PATH.read_bytes() if LOGO_PATH.exists() else None
except OSError:
    _LOGO_BYTES = None

st.set_page_config(page_title="Flor de Sal — Hora óptima de recolección",
                   page_icon=_LOGO_BYTES if _LOGO_BYTES else "🧂", layout="wide")

# ------------------------------------------------------------------ constantes
TEAL = "#00695C"          # color primario (.streamlit/config.toml)
ROJO = "#C62828"
COLORES_FASE: dict[int, str] = {0: "#9E9E9E", 1: "#EF6C00", 2: TEAL, 3: ROJO}
BADGE_FASE: dict[int, str] = {0: "⬜", 1: "🟧", 2: "🟩", 3: "🟥"}
NOMBRE_FASE: dict[int, str] = {
    0: "Inactividad",
    1: "Nucleación",
    2: "Ventana óptima",
    3: "Cierre/riesgo",
}
FONDO_FASE: dict[int, str] = {0: "#EEEEEE", 1: "#FFE0B2", 2: "#C8E6C9", 3: "#FFCDD2"}

# Estados de la capa de Márkov (AGENTS.md): (columna del veredicto, nombre, color).
# El orden del gráfico apilado es de abajo arriba: inactivo → … → degradación.
ESTADOS_MARKOV: list[tuple[str, str, str]] = [
    ("P_inactivo", "Inactivo", "#9E9E9E"),
    ("P_concentracion_critica", "Concentración crítica", "#FFC107"),
    ("P_nucleacion", "Nucleación", "#FF9800"),
    ("P_ventana", "Ventana", "#2E7D32"),
    ("P_degradacion", "Degradación", "#C62828"),
]

MESES: list[str] = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
MESES_CORTO: list[str] = ["ene", "feb", "mar", "abr", "may", "jun",
                          "jul", "ago", "sep", "oct", "nov", "dic"]
GRIS_CELDA = "#EEEEEE"      # celdas del calendario sin ventana / no simuladas

_CFG0 = load_config()

# Ruta de la base de datos: data/flor_desal.db salvo que se indique lo contrario
# (variable opcional, pensada para pruebas: no toca la DB real del proyecto).
DB_RUTA: str = str(os.environ.get("FLOR_DESAL_DB") or DB_PATH)


def _db() -> Database:
    """Conexión a la base de datos local (una por operación, sin estado)."""
    return Database(DB_RUTA)


# Especificación del panel de calibración:
#   key → clave de widget, sec → sección del Config, attr → atributo de esa sección
CALIB: list[dict] = [
    {"key": "dalton_a", "sec": "physics", "attr": "dalton_a",
     "label": "Dalton · a (mm/día por kPa)", "min": 0.1, "max": 1.5, "step": 0.01,
     "fmt": "%.2f",
     "ayuda": "Evaporación con viento cero. Literatura para lámina libre: 0,17; "
              "la lámina somera del cristalizador evapora más."},
    {"key": "dalton_b", "sec": "physics", "attr": "dalton_b",
     "label": "Dalton · b (mm/día por kPa·m/s)", "min": 0.5, "max": 5.0, "step": 0.01,
     "fmt": "%.2f",
     "ayuda": "Aumento de evaporación por cada m/s de viento. Literatura: 0,87."},
    {"key": "sigma_temp", "sec": "montecarlo", "attr": "sigma_temp_c",
     "label": "σ temperatura (°C)", "min": 0.1, "max": 5.0, "step": 0.1, "fmt": "%.1f",
     "ayuda": "Incertidumbre de la previsión de temperatura en el Monte Carlo."},
    {"key": "sigma_rh", "sec": "montecarlo", "attr": "sigma_rh_pct",
     "label": "σ HR (%)", "min": 1.0, "max": 20.0, "step": 0.5, "fmt": "%.1f",
     "ayuda": "Incertidumbre de la humedad relativa: más σ → campana más ancha."},
    {"key": "sigma_wind", "sec": "montecarlo", "attr": "sigma_wind_ms",
     "label": "σ viento (m/s)", "min": 0.05, "max": 3.0, "step": 0.05, "fmt": "%.2f",
     "ayuda": "Incertidumbre del viento previsto."},
    {"key": "umbral", "sec": "water", "attr": "umbral_sobresaturacion_g_l",
     "label": "Umbral de sobresaturación (g/l)", "min": 300.0, "max": 340.0,
     "step": 1.0, "fmt": "%.0f",
     "ayuda": "Concentración a la que empieza la nucleación (rango del PDF: 315-320)."},
    {"key": "profundidad", "sec": "water", "attr": "profundidad_lamina_cm",
     "label": "Profundidad de lámina (cm)", "min": 5.0, "max": 10.0, "step": 0.5,
     "fmt": "%.1f",
     "ayuda": "Tiraje del cristalizador: lámina más fina concentra antes."},
    {"key": "crecimiento", "sec": "simulation", "attr": "minutos_crecimiento",
     "label": "Minutos de crecimiento (min)", "min": 30, "max": 240, "step": 15,
     "fmt": "%d",
     "ayuda": "Tiempo que la película crece tras la nucleación antes de ser "
              "cosechable (por defecto 120 min)."},
]

COLUMNAS_LECTURAS = {
    "reading_time": "Hora",
    "t_calentador_c": "T calentador °C",
    "t_cristalizador_c": "T cristalizador °C",
    "concentration_g_l": "Concentración g/l",
    "t_ambiente_c": "T ambiente °C",
    "rh_pct": "HR %",
    "wind_ms": "Viento m/s",
    "notes": "Notas",
}

CONFIG_TABLA = {
    "T aire °C": st.column_config.NumberColumn("T aire °C", format="%.1f"),
    "HR %": st.column_config.NumberColumn("HR %", format="%.0f"),
    "Viento m/s": st.column_config.NumberColumn("Viento m/s", format="%.1f"),
    "T agua °C": st.column_config.NumberColumn("T agua °C", format="%.1f"),
    "Evap. mm/h": st.column_config.NumberColumn("Evap. mm/h", format="%.3f"),
    "Concentración g/l": st.column_config.NumberColumn("Concentración g/l", format="%.1f"),
    "Fase": st.column_config.TextColumn("Fase", width="medium"),
}


# ------------------------------------------------------------- helpers generales
def _hhmm_decimal(hhmm: str | None) -> float | None:
    """'17:45' → 17.75 (para los ejes y líneas verticales de plotly)."""
    if not hhmm:
        return None
    try:
        h, m = str(hhmm).split(":")
        return int(h) + int(m) / 60.0
    except (ValueError, AttributeError):
        return None


def _texto_bias(bias: dict | None) -> str:
    """«temperatura +1,8 °C, HR −6 %, viento +0,4 m/s» (vacío si no hay sesgo)."""
    bias = bias or {}
    partes = []
    if bias.get("temp_c") is not None:
        partes.append(f"temperatura {bias['temp_c']:+.1f} °C")
    if bias.get("rh_pct") is not None:
        partes.append(f"HR {bias['rh_pct']:+.0f} %")
    if bias.get("wind_ms") is not None:
        partes.append(f"viento {bias['wind_ms']:+.1f} m/s")
    return ", ".join(partes)


def _valor_defecto(spec: dict):
    """Valor por defecto (config.yaml) del parámetro de calibración `spec`."""
    return getattr(getattr(_CFG0, spec["sec"]), spec["attr"])


def _inicializar_calibracion() -> None:
    """Copia los valores por defecto (o el reset pendiente) a session_state.

    Se ejecuta SIEMPRE antes de instanciar los widgets del panel de calibración
    (Streamlit no deja modificar la clave de un widget ya instanciado).
    """
    if st.session_state.pop("reset_calibracion", False):
        for spec in CALIB:
            st.session_state[f"calib_{spec['key']}"] = _valor_defecto(spec)
        st.session_state["aviso"] = ("ok", "Calibración restablecida a los valores de config.yaml.")
    for spec in CALIB:
        st.session_state.setdefault(f"calib_{spec['key']}", _valor_defecto(spec))


def _valores_calibracion() -> tuple:
    """Tuple (hashable) con los valores actuales del panel → clave de caché."""
    return tuple(st.session_state[f"calib_{spec['key']}"] for spec in CALIB)


def _cfg_calibrado(valores: dict) -> Config:
    """Config fresco (config.yaml) con los overrides de la UI aplicados."""
    cfg = load_config()
    for spec in CALIB:
        setattr(getattr(cfg, spec["sec"]), spec["attr"], valores[spec["key"]])
    return cfg


@st.cache_data(ttl=300, show_spinner="Calculando el veredicto (Monte Carlo)…")
def _calcular(fecha: str, n_lecturas: int, calibracion: tuple,
              rev: int, hora: int, db_ruta: str = DB_RUTA) -> dict:
    """Veredicto + campana + tabla horaria del día (cacheados 5 min).

    La clave incluye nº de lecturas (nueva lectura → recálculo con sesgo),
    parámetros de calibración (cambio → recálculo), un contador `rev` que se
    incrementa al descargar previsión o guardar lecturas, y la hora del sistema
    (cambio de fase a mitad de día).
    """
    cfg = _cfg_calibrado(dict(zip([s["key"] for s in CALIB], calibracion, strict=False)))
    db = Database(db_ruta)
    veredicto = run_daily(db, fecha, cfg=cfg)
    datos: dict = {"veredicto": veredicto, "tabla": None, "forecast": None,
                   "hist_hours": np.array([]), "hist_probs": np.array([])}

    prev = db.get_forecast(fecha)
    if prev is None or prev.empty:
        return datos

    bias = veredicto.get("bias") or {}
    ajuste = assimilation.apply_bias(prev, bias) if bias else prev
    datos["forecast"] = ajuste   # previsión horaria (con sesgo si hay lecturas)

    # Misma simulación que el pipeline (misma semilla) para la campana de prob.
    r = montecarlo.simulate_day(ajuste, cfg)
    datos["hist_hours"] = r.hist_hours
    datos["hist_probs"] = r.hist_probs

    # Tabla horaria: modelo hora a hora solo sobre las horas simuladas (06-21),
    # igual que hace el Monte Carlo, para que fase y concentración coincidan.
    h0, h1 = int(cfg.simulation.hora_inicio), int(cfg.simulation.hora_fin)
    base = ajuste[(ajuste["hour"] >= h0) & (ajuste["hour"] <= h1)].sort_values("hour")
    datos["tabla"] = _tabla_desde_sim(physics.concentrations_over_day(base, cfg))
    return datos


def _tabla_desde_sim(sim: pd.DataFrame) -> pd.DataFrame:
    """DataFrame mostrable (hora HH:MM, meteo, T agua, evaporación, C y fase)."""
    def _fase_txt(f) -> str:
        n = int(f)
        return f"{BADGE_FASE.get(n, '⚪')} {n} · {NOMBRE_FASE.get(n, '—')}"

    return pd.DataFrame({
        "Hora": [_hhmm(float(h)) for h in sim["hour"]],
        "T aire °C": sim["temp_c"].astype(float).round(1),
        "HR %": sim["rh_pct"].astype(float).round(0),
        "Viento m/s": sim["wind_ms"].astype(float).round(1),
        "T agua °C": sim["t_water_c"].astype(float).round(1),
        "Evap. mm/h": sim["evap_mm_h"].astype(float).round(3),
        "Concentración g/l": (sim["c_g_l"].astype(float)
                              .where(np.isfinite(sim["c_g_l"].astype(float))).round(1)),
        "Fase": [_fase_txt(f) for f in sim["fase"]],
    })


def _css_fase(valor) -> str:
    """Estilo de badge por fase para Styler.map (columna 'Fase')."""
    m = re.search(r"(\d)", str(valor))
    n = int(m.group(1)) if m else -1
    fondo = FONDO_FASE.get(n, "#FFFFFF")
    return f"background-color: {fondo}; font-weight: 600;"


def _estilizar(tabla: pd.DataFrame):
    """Tabla con la columna 'Fase' pintada (fallback: tabla sin estilo)."""
    try:
        return tabla.style.map(_css_fase, subset=["Fase"])
    except Exception:  # pandas sin Styler.map u otro fallo cosmético
        return tabla


# ------------------------------------------------------------ datos de temporada
def _rango_temporada() -> tuple[str, str]:
    """(inicio, fin) de la temporada de config.yaml (sección `season`)."""
    return str(_CFG0.season.start_date), str(_CFG0.season.end_date)


def _rev_temporada() -> int:
    """Contador que invalida la caché de `season_runs` tras una re-simulación."""
    return int(st.session_state.get("rev_temporada", 0))


@st.cache_data(ttl=300, show_spinner=False)
def _cargar_temporada(start: str, end: str, rev: int,
                      db_ruta: str = DB_RUTA) -> pd.DataFrame:
    """season_runs del rango [start, end] (cacheado 5 min; `rev` lo invalida)."""
    return Database(db_ruta).get_season_runs(start, end)


def _ejecutar_simulacion_temporada() -> None:
    """Ejecuta `scripts/season_simulation.py` (≈15 s) y refresca la caché."""
    raiz = Path(__file__).resolve().parents[1]
    cmd = [sys.executable, str(raiz / "scripts" / "season_simulation.py")]
    try:
        with st.spinner("Simulando la temporada con meteorología observada (ERA5)…"):
            r = subprocess.run(cmd, check=False, cwd=str(raiz), capture_output=True,
                               text=True, timeout=600, encoding="utf-8",
                               errors="replace")
    except Exception as exc:  # timeout, permisos, intérprete no encontrado…
        st.session_state["aviso"] = ("err", f"No se pudo ejecutar la simulación: {exc}")
        st.rerun()
        return

    salida = (r.stdout or "") + (f"\n{r.stderr}" if r.stderr else "")
    st.session_state["salida_temporada"] = salida.strip()
    st.session_state["rev_temporada"] = _rev_temporada() + 1
    if r.returncode == 0:
        resumen = next((ln for ln in salida.splitlines() if ln.startswith("Días simulados")),
                       "temporada guardada en la tabla season_runs")
        st.session_state["aviso"] = ("ok", f"✅ Temporada simulada: {resumen}.")
    else:
        st.session_state["aviso"] = ("err",
                                     (f"La simulación falló (código {r.returncode}): "
                                      f"{salida.strip()[-400:]}"))
    st.cache_data.clear()   # season_runs + veredicto del día, todo a cero
    st.rerun()


def _preparar_temporada(df: pd.DataFrame) -> pd.DataFrame:
    """Columnas derivadas para todos los gráficos de la pestaña Temporada.

    Añade: fecha (datetime), mes/día del calendario, `hora_dec` (hora óptima en
    decimal), `ini_dec`/`fin_dec` (ventana en decimal) y la marca booleana
    `ventana` (¿ese día abrió ventana de cosecha?).
    """
    out = df.copy()
    out["fecha"] = pd.to_datetime(out["date"], errors="coerce")
    out["mes"] = out["fecha"].dt.month.astype("Int64")
    out["dia"] = out["fecha"].dt.day.astype("Int64")
    out["hora_dec"] = pd.to_numeric(out["hora_optima"].map(_hhmm_decimal),
                                    errors="coerce").astype(float)
    out["ini_dec"] = pd.to_numeric(out["window_start"].map(_hhmm_decimal),
                                   errors="coerce").astype(float)
    out["fin_dec"] = pd.to_numeric(out["window_end"].map(_hhmm_decimal),
                                   errors="coerce").astype(float)
    out["prob_ventana"] = pd.to_numeric(out["prob_ventana"], errors="coerce").fillna(0.0)
    out["prob_riesgo"] = pd.to_numeric(out["prob_riesgo"], errors="coerce").fillna(0.0)
    out["ventana"] = out["hora_dec"].notna()
    return out


# ------------------------------------------------------------------- paneles
def _sidebar(db: Database) -> tuple[date, str]:
    """Navegación (Hoy/Temporada), selector de fecha y leyenda de fases.

    Returns:
        (fecha del veredicto, sección elegida). La fecha solo se usa en «Hoy».
    """
    with st.sidebar:
        st.markdown("## 🧂 Flor de Sal")
        st.caption("Predicción probabilística de la ventana de cosecha")
        seccion = st.radio(
            "📂 Sección", ["🌞 Hoy", "📆 Temporada"], horizontal=True, key="seccion",
            help="«Hoy»: veredicto y datos del día · «Temporada»: simulación histórica.",
        )

        if seccion.startswith("📆"):
            _sidebar_temporada()
            st.divider()
            st.markdown("**Semáforo de fases**")
            for n, nombre in NOMBRE_FASE.items():
                st.markdown(f"{BADGE_FASE[n]} **Fase {n}** — {nombre}")
            st.divider()
            st.caption(f"{_CFG0.location.name} · {_CFG0.location.latitude}, "
                       f"{_CFG0.location.longitude} · tz {_CFG0.location.timezone}")
            return date.today(), seccion

        fecha = st.date_input("📅 Fecha del veredicto", value=date.today(),
                              width="stretch", help="Día que quieres estudiar (por defecto, hoy).")
        fecha_s = fecha.isoformat() if isinstance(fecha, date) else str(fecha)

        if st.button("⬇️ Descargar/guardar previsión del día", key="btn_descarga",
                     type="primary", width="stretch",
                     help="Descarga la serie horaria de Open-Meteo para las coordenadas de "
                          "config.yaml y la guarda en la base de datos local."):
            try:
                with st.spinner("Descargando previsión de Open-Meteo…"):
                    df = weather.fetch_forecast(
                        float(_CFG0.location.latitude), float(_CFG0.location.longitude),
                        fecha_s, str(_CFG0.location.timezone))
                    n = db.save_forecast(fecha_s, df)
                st.session_state["rev"] = int(st.session_state.get("rev", 0)) + 1
                st.session_state["aviso"] = ("ok",
                                             f"Previsión del {fecha_s} guardada ({n} horas).")
            except Exception as exc:  # red caída, día futuro fuera de rango, etc.
                st.session_state["aviso"] = ("err",
                                             f"No se pudo descargar la previsión: {exc}")
            st.rerun()

        st.divider()
        st.markdown("**Semáforo de fases**")
        for n, nombre in NOMBRE_FASE.items():
            st.markdown(f"{BADGE_FASE[n]} **Fase {n}** — {nombre}")
        st.divider()
        st.caption(f"{_CFG0.location.name} · {_CFG0.location.latitude}, "
                   f"{_CFG0.location.longitude} · tz {_CFG0.location.timezone}")
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


def _panel_veredicto(v: dict) -> None:
    """Semáforo, ventana, hora óptima ± IC95, probabilidades y alertas."""
    fase = int(v.get("fase_actual", 0))
    desc = str(v.get("fase_descripcion") or "")

    st.subheader("🚦 Veredicto del día")
    if fase == 2:
        st.success(f"**Fase 2** — {desc}")
    elif fase == 1:
        st.warning(f"**Fase 1** — {desc}")
    elif fase == 3:
        st.error(f"**Fase 3** — {desc}")
    else:
        st.markdown(
            f'<div style="background:#EEEEEE;border-left:6px solid {COLORES_FASE[0]};'
            f'border-radius:6px;padding:0.75rem 1rem;color:#424242;">'
            f"<b>⬜ Fase 0</b> — {desc}</div>",
            unsafe_allow_html=True,
        )

    vi, vf = v.get("ventana_inicio"), v.get("ventana_fin")
    ventana_txt = f"{vi} – {vf}" if vi and vf else "Sin ventana hoy"
    hora = v.get("hora_optima") or "—"
    ic = v.get("hora_optima_ci") or [None, None]
    ic_txt = (f"IC95 {ic[0]}–{ic[1]}" if ic[0] and ic[1]
              else "sin estimación (sin ventana)")
    p_vent = float(v.get("prob_ventana") or 0.0)
    p_riesgo = float(v.get("prob_riesgo") or 0.0)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🌀 Ventana más probable", ventana_txt,
              help="Tramo en el que la mayoría de escenarios tiene la película cosechable.")
    c2.metric("🎯 Hora óptima", hora, delta=ic_txt, delta_color="off",
              help="Mediana de los escenarios con ventana; el IC95 son los "
                   "percentiles 5 y 95 (horas 5 y 95 de la campana).")
    c3.metric("📈 Probabilidad de ventana", f"{p_vent:.0%}",
              help="Fracción de escenarios del Monte Carlo en los que se abre ventana.")
    c4.metric("⚠️ Probabilidad de riesgo (Fase 3)", f"{p_riesgo:.0%}",
              help="Fracción de escenarios que cierran por riesgo duro "
                   "(viento > 5,5 m/s o HR > 65 %).")

    b1, b2 = st.columns(2)
    with b1:
        st.markdown("**Probabilidad de ventana óptima**")
        st.progress(min(max(p_vent, 0.0), 1.0),
                    text=f"{p_vent:.0%} de los {int(v.get('n_iter') or 0)} escenarios abren ventana")
    with b2:
        st.markdown("**Probabilidad de riesgo (Fase 3)**")
        st.progress(min(max(p_riesgo, 0.0), 1.0),
                    text=f"{p_riesgo:.0%} cierran por riesgo (hundimiento/rehidratación)")

    alertas = v.get("alertas") or []
    if alertas:
        st.markdown("**🔔 Alertas del momento**")
        for a in alertas:
            msg = str(a.get("mensaje", ""))
            nivel = a.get("nivel", "verde")
            if nivel == "rojo":
                st.error(msg)
            elif nivel == "amarillo":
                st.warning(msg)
            else:
                st.success(msg)

    st.caption(f"Veredicto calculado a las {v.get('hora_veredicto', '—')} · "
               f"{int(v.get('n_iter') or 0)} escenarios · último cálculo "
               f"{v.get('computed_at', '—')}")


def _panel_campana(datos: dict) -> None:
    """Curva/barras de la densidad de la hora óptima con IC95 sombreado."""
    st.subheader("🔔 Campana de probabilidad de la hora óptima")
    horas = np.asarray(datos.get("hist_hours") if datos.get("hist_hours") is not None
                       else [], dtype=float)
    probs = np.asarray(datos.get("hist_probs") if datos.get("hist_probs") is not None
                       else [], dtype=float)
    if horas.size == 0 or probs.size == 0 or not np.any(probs > 0):
        st.info("Hoy ningún escenario alcanza la ventana de cosecha: no hay campana "
                "de probabilidad. Revisa las alertas, la previsión del día o los "
                "parámetros de calibración.")
        return

    v = datos["veredicto"]
    ci = v.get("hora_optima_ci") or [None, None]
    fig = go.Figure()
    x_ci0, x_ci1 = _hhmm_decimal(ci[0]), _hhmm_decimal(ci[1])
    if x_ci0 is not None and x_ci1 is not None:
        fig.add_vrect(x0=x_ci0, x1=x_ci1, fillcolor="rgba(0,105,92,0.18)",
                      line_width=0, annotation_text="IC 95 %",
                      annotation_position="top", annotation_font_size=11)
    fig.add_trace(go.Bar(
        x=horas, y=probs, name="Densidad",
        marker={"color": TEAL, "line": {"width": 0}}, opacity=0.9,
        customdata=[_hhmm(float(h)) for h in horas],
        hovertemplate="Hora %{customdata}<br>densidad %{y:.3f}<extra></extra>",
    ))
    x_med = _hhmm_decimal(v.get("hora_optima"))
    if x_med is not None:
        fig.add_vline(x=x_med, line_dash="dash", line_color=ROJO, line_width=2,
                      annotation_text=f"Mediana {v['hora_optima']}",
                      annotation_font_color=ROJO, annotation_font_size=12)
    ticks = list(range(6, 22, 2))
    fig.update_xaxes(tickvals=ticks, ticktext=[f"{t:02d}:00" for t in ticks],
                     title="Hora del día", gridcolor="#E0E0E0", zeroline=False)
    fig.update_yaxes(title="Densidad de probabilidad", gridcolor="#E0E0E0",
                     zeroline=False)
    fig.update_layout(
        barmode="overlay", height=380, bargap=0.05,
        margin={"l": 10, "r": 10, "t": 45, "b": 10},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#212121"},
    )
    st.plotly_chart(fig, width="stretch", theme="streamlit",
                    config={"displayModeBar": False})
    st.caption("Barras: densidad de probabilidad de la hora óptima sobre los escenarios "
               "con ventana (área total = 1). Sombreado verde = IC 95 %; línea roja "
               "discontinua = mediana (la hora óptima recomendada).")


def _panel_semaforo(datos: dict) -> None:
    """Áreas apiladas hora a hora con los 5 estados de Márkov (en %)."""
    st.subheader("🚦 Semáforo probabilístico de la balsa (Márkov)")

    filas = (datos["veredicto"].get("estados_por_hora") or [])
    if not filas:
        st.info("Sin curva de Márkov para este día (hace falta previsión horaria).")
        return

    horas = [float(f.get("hour", i)) for i, f in enumerate(filas)]
    fig = go.Figure()
    for col, nombre, color in ESTADOS_MARKOV:
        vals = [100.0 * float(f.get(col) or 0.0) for f in filas]
        fig.add_trace(go.Scatter(
            x=horas, y=vals, name=nombre, mode="lines", stackgroup="one",
            customdata=[_hhmm(h) for h in horas],
            line={"color": color, "width": 1},
            fillcolor=color,
            hovertemplate="Hora %{customdata}<br>%{y:.0f} % · " + nombre +
                          "<extra></extra>",
        ))

    # Texto guía: hora con más probabilidad de ventana
    p_vent = [float(f.get("P_ventana") or 0.0) for f in filas]
    i_max = int(np.argmax(p_vent))
    if p_vent[i_max] > 0:
        h_txt = (_hhmm(horas[i_max]) or "").replace(":00", "")
        st.markdown(f"**¿A qué hora es más probable que esté la ventana? "
                    f"{h_txt}h: {p_vent[i_max]:.0%}**")
    else:
        st.markdown("**¿A qué hora es más probable que esté la ventana?** "
                    "hoy ningún escenario alcanza la ventana en ninguna hora.")

    es_hoy = str(datos["veredicto"].get("fecha")) == date.today().isoformat()
    if es_hoy:
        ahora = datetime.now()
        x_ahora = ahora.hour + ahora.minute / 60.0
        if min(horas) <= x_ahora <= max(horas):
            fig.add_vline(x=x_ahora, line_dash="dot", line_color="#424242",
                          line_width=2, annotation_text="ahora",
                          annotation_font_color="#424242", annotation_font_size=11)

    ticks = list(range(int(min(horas)), int(max(horas)) + 1, 2))
    fig.update_xaxes(tickvals=ticks, ticktext=[f"{t:02d}:00" for t in ticks],
                     title="Hora del día", gridcolor="#E0E0E0", zeroline=False)
    fig.update_yaxes(title="Probabilidad (%)", range=[0, 100], dtick=25,
                     gridcolor="#E0E0E0", zeroline=False)
    fig.update_layout(
        height=380, margin={"l": 10, "r": 10, "t": 45, "b": 10},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        hovermode="x unified",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#212121"},
    )
    st.plotly_chart(fig, width="stretch", theme="streamlit",
                    config={"displayModeBar": False})
    st.caption("Cada franja es la probabilidad de estar en ese estado a cada hora "
               "(las cinco suman 100 %): gris inactivo · ámbar concentración crítica · "
               "naranja nucleación · verde ventana · rojo degradación. La línea "
               "discontinua marca la hora actual.")


def _panel_tabla(datos: dict) -> None:
    """Tabla horaria del día (meteo, T agua, evaporación, concentración y fase)."""
    st.subheader("📋 Tabla horaria del día")
    tabla = datos.get("tabla")
    if tabla is None or tabla.empty:
        st.info("Sin previsión horaria para esta fecha: descárgala con el botón del "
                "menú lateral.")
        return
    bias = datos["veredicto"].get("bias") or {}
    nota = ("con corrección por sesgo aplicada" if bias else "previsión en bruto")
    st.caption(f"Modelo hora a hora (06:00–21:00) sobre la previsión {nota}. "
               "El badge de color de la columna «Fase» sigue el semáforo.")
    st.dataframe(_estilizar(tabla), width="stretch", hide_index=True,
                 column_config=CONFIG_TABLA, row_height=34)


def _panel_prevision_lecturas(datos: dict, db: Database, fecha_s: str) -> None:
    """3 mini-gráficos (T, HR, V): previsión horaria frente a las lecturas reales."""
    st.subheader("🌤️ Previsión vs lecturas reales")

    lecturas = db.get_readings(fecha_s)
    if lecturas is None or lecturas.empty:
        st.info("Aún no hay lecturas para este día: guarda la primera con el formulario "
                "y podrás comparar la previsión con lo medido en la salina.")
        return
    prev = datos.get("forecast")
    if prev is None or len(prev) == 0:
        st.info("Sin previsión horaria para comparar: descárgala desde el menú lateral.")
        return

    bias = datos["veredicto"].get("bias") or {}
    sesgo = _texto_bias(bias)
    origen = f"**con corrección por sesgo**: {sesgo}" if sesgo else "**en bruto** (sin sesgo)"
    st.caption(f"Línea teal = previsión horaria {origen} · puntos rojos = lecturas "
               "reales del formulario.")

    specs = [
        ("🌡️ Tª ambiente (°C)", "temp_c", "t_ambiente_c", "°C"),
        ("💧 HR (%)", "rh_pct", "rh_pct", "%"),
        ("🍃 Viento (m/s)", "wind_ms", "wind_ms", "m/s"),
    ]
    for col, (titulo, c_prev, c_lec, unidad) in zip(st.columns(3), specs, strict=False):
        with col:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=prev["hour"].astype(float), y=prev[c_prev].astype(float),
                mode="lines", name="Previsión", line={"color": TEAL, "width": 2.5},
                hovertemplate="%{x:.0f}:00 · %{y:.1f} " + unidad +
                              "<extra>Previsión</extra>",
            ))
            lec = lecturas.dropna(subset=[c_lec])
            xs = [_hhmm_decimal(t) for t in lec["reading_time"]]
            ys = pd.to_numeric(lec[c_lec], errors="coerce")
            con_datos = [(x, float(y)) for x, y in zip(xs, ys, strict=False)
                         if x is not None and pd.notna(y)]
            if con_datos:
                fig.add_trace(go.Scatter(
                    x=[c[0] for c in con_datos], y=[c[1] for c in con_datos],
                    mode="markers", name="Lecturas",
                    marker={"color": ROJO, "size": 8, "line": {"width": 1, "color": "#FFFFFF"}},
                    customdata=[_hhmm(c[0]) for c in con_datos],
                    hovertemplate="%{customdata} · %{y:.1f} " + unidad +
                                  "<extra>Lectura real</extra>",
                ))
            fig.update_layout(
                height=250, margin={"l": 5, "r": 5, "t": 34, "b": 5}, title=titulo,
                title_font_size=13, showlegend=False,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font={"color": "#212121", "size": 11},
                hovermode="closest",
            )
            eje_x = {"range": [0, 24], "dtick": 6, "tickvals": list(range(0, 25, 6)),
                         "ticktext": [f"{t:02d}:00" for t in range(0, 25, 6)],
                         "gridcolor": "#E0E0E0", "zeroline": False}
            eje_y = {"range": [0, 100], "dtick": 50, "gridcolor": "#E0E0E0",
                         "zeroline": False} if c_prev == "rh_pct" else \
                    {"gridcolor": "#E0E0E0", "zeroline": False}
            fig.update_xaxes(**eje_x)
            fig.update_yaxes(**eje_y)
            st.plotly_chart(fig, width="stretch", theme="streamlit",
                            config={"displayModeBar": False})
            if not con_datos:
                st.caption("Sin lecturas de este tipo para el día.")


def _panel_evolucion(db: Database, fecha_s: str) -> None:
    """Hora óptima + IC95 de cada cálculo del día: cómo se estrecha la estimación."""
    st.subheader("📈 Evolución de la predicción del día")

    preds = db.get_predictions(fecha_s)
    n = 0 if preds is None else len(preds)
    if n < 2:
        st.info(f"Hace falta recalcular el veredicto al menos dos veces durante el día "
                f"(ahora hay {n} cálculo(s)): cada lectura guardada o descarga de "
                "previsión añade un punto y verás cómo se estrecha la estimación.")
        return

    filas: list[dict] = []
    for _, r in preds.iterrows():
        p = r.get("payload") or {}
        hora_calc = str(p.get("hora_veredicto") or str(r.get("computed_at") or "00:00")[11:16])
        opt = p.get("hora_optima")
        ci = p.get("hora_optima_ci") or [None, None]
        filas.append({
            "x": _hhmm_decimal(hora_calc),
            "hora": hora_calc,
            "opt": _hhmm_decimal(opt),
            "ci0": _hhmm_decimal(ci[0] if ci else None),
            "ci1": _hhmm_decimal(ci[1] if ci else None),
            "pv": float(p.get("prob_ventana") or 0.0),
        })

    con = sorted((f for f in filas if f["x"] is not None and f["opt"] is not None),
                 key=lambda f: f["x"])
    if len(con) < 2:
        probs = [f["pv"] for f in filas if f["x"] is not None]
        rango = (f"{min(probs):.0%}–{max(probs):.0%}" if probs else "—")
        st.info(f"{n} cálculos hoy, pero ninguno encuentra ventana de cosecha "
                f"(probabilidad de ventana entre {rango}). Cuando el modelo anticipe "
                "ventana, aquí verás la hora óptima y su IC 95 % estrechándose a lo "
                "largo del día con los datos reales.")
        return

    xs = [f["x"] for f in con]
    # Banda del IC 95 % (si un cálculo no tiene IC, se cierra sobre la mediana)
    inf = [f["ci0"] if f["ci0"] is not None else f["opt"] for f in con]
    sup = [f["ci1"] if f["ci1"] is not None else f["opt"] for f in con]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=sup, mode="lines", name="IC 95 %",
                             line={"width": 0}, hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=xs, y=inf, mode="lines", name="IC 95 %",
                             line={"width": 0}, fill="tonexty",
                             fillcolor="rgba(0,105,92,0.20)",
                             hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(
        x=xs, y=[f["opt"] for f in con], mode="lines+markers", name="Hora óptima",
        line={"color": TEAL, "width": 2.5}, marker={"color": TEAL, "size": 8},
        customdata=[(f["hora"], _hhmm(f["opt"]) or "—", f"{f['pv']:.0%}",
                     _hhmm(f["ci0"]) or "—", _hhmm(f["ci1"]) or "—") for f in con],
        hovertemplate="cálculo %{customdata[0]}<br>óptima %{customdata[1]} "
                      "(IC95 %{customdata[3]}–%{customdata[4]})"
                      "<br>prob. ventana %{customdata[2]}<extra></extra>",
    ))
    fig.add_vline(x=xs[-1], line_dash="dot", line_color="#424242", line_width=2,
                  annotation_text="último cálculo",
                  annotation_font_color="#424242", annotation_font_size=11)

    ancho = xs[-1] - xs[0]
    dtick = 1.0 if ancho >= 3 else 0.5
    ticks = list(np.arange(np.floor(xs[0]), xs[-1] + 0.01, dtick))
    fig.update_xaxes(tickvals=ticks, ticktext=[_hhmm(t) or "" for t in ticks],
                     title="Hora del cálculo", gridcolor="#E0E0E0", zeroline=False)
    ymin, ymax = min(inf + [f["opt"] for f in con]), max(sup + [f["opt"] for f in con])
    yt = list(np.arange(np.floor(ymin), np.ceil(ymax) + 0.01, 1.0))
    fig.update_yaxes(tickvals=yt, ticktext=[_hhmm(t) or "" for t in yt],
                     title="Hora óptima", range=[ymin - 0.5, ymax + 0.5],
                     gridcolor="#E0E0E0", zeroline=False)
    fig.update_layout(
        height=340, margin={"l": 10, "r": 10, "t": 40, "b": 10},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#212121"},
    )
    st.plotly_chart(fig, width="stretch", theme="streamlit",
                    config={"displayModeBar": False})
    st.caption(f"{len(con)} de {n} cálculos con ventana · cada punto es un veredicto "
               "del día; el sombreado es el IC 95 %. Con cada lectura real la banda "
               "se estrecha alrededor de lo medido (corrección por sesgo).")


def _panel_formulario(db: Database, fecha_s: str) -> None:
    """Formulario de datos reales de campo → db.save_reading + recálculo."""
    st.subheader("📐 Datos reales de campo")
    st.caption("Registra una lectura cada 1-2 horas: la predicción se recalcula sola "
               "con la corrección por sesgo (media de real − previsto).")

    with st.form("form_lecturas", clear_on_submit=True, width="stretch"):
        f1 = st.columns(4)
        hora = f1[0].time_input("Hora", value="now", format="24h",
                                help="Hora de la lectura.")
        t_cal = f1[1].number_input("Tª calentador (°C)", min_value=0.0, max_value=100.0,
                                   value=None, step=0.5, format="%.1f", placeholder="—")
        t_cri = f1[2].number_input("Tª cristalizador (°C)", min_value=0.0,
                                   max_value=100.0, value=None, step=0.5, format="%.1f",
                                   placeholder="—")
        conc = f1[3].number_input("Concentración (g/l)", min_value=0.0, max_value=400.0,
                                  value=None, step=1.0, format="%.0f", placeholder="—")

        f2 = st.columns(4)
        t_amb = f2[0].number_input("Tª ambiente (°C)", min_value=-10.0, max_value=60.0,
                                   value=None, step=0.5, format="%.1f", placeholder="—")
        rh = f2[1].number_input("HR (%)", min_value=0.0, max_value=100.0, value=None,
                                step=1.0, format="%.0f", placeholder="—")
        viento = f2[2].number_input("Viento (m/s)", min_value=0.0, max_value=30.0,
                                    value=None, step=0.1, format="%.1f",
                                    placeholder="—")
        notas = f2[3].text_input("Notas", placeholder="p. ej. «laminas limpias»")

        enviado = st.form_submit_button("💾 Guardar lectura", type="primary",
                                        width="stretch")

    if not enviado:
        return
    if all(x is None for x in (t_cal, t_cri, conc, t_amb, rh, viento)):
        st.warning("Introduce al menos un valor (T, HR, viento o concentración) "
                   "para guardar la lectura.")
        return
    lectura_hora = hora.strftime("%H:%M") if isinstance(hora, (datetime, Hora)) \
        else str(hora)[:5]
    db.save_reading(fecha_s, lectura_hora, t_cal, t_cri, conc, t_amb, rh, viento, notas)
    st.session_state["rev"] = int(st.session_state.get("rev", 0)) + 1
    st.session_state["aviso"] = ("ok",
                                 f"Lectura de las {lectura_hora} guardada. Veredicto "
                                 "recalculado con la corrección por sesgo.")
    st.rerun()


def _panel_lecturas(db: Database, fecha_s: str, bias: dict) -> None:
    """Lecturas del día + sesgo aplicado."""
    st.subheader("📔 Lecturas del día y sesgo aplicado")
    lecturas = db.get_readings(fecha_s)
    if lecturas is None or lecturas.empty:
        st.info("Todavía no hay lecturas para este día. Guarda la primera con el "
                "formulario de arriba.")
    else:
        mostrar = lecturas.rename(columns=COLUMNAS_LECTURAS)
        st.dataframe(mostrar, width="stretch", hide_index=True, row_height=34,
                     column_config={
                         "T calentador °C": st.column_config.NumberColumn(
                             "T calentador °C", format="%.1f"),
                         "T cristalizador °C": st.column_config.NumberColumn(
                             "T cristalizador °C", format="%.1f"),
                         "Concentración g/l": st.column_config.NumberColumn(
                             "Concentración g/l", format="%.0f"),
                         "T ambiente °C": st.column_config.NumberColumn(
                             "T ambiente °C", format="%.1f"),
                         "HR %": st.column_config.NumberColumn("HR %", format="%.0f"),
                         "Viento m/s": st.column_config.NumberColumn(
                             "Viento m/s", format="%.1f"),
                     })
        st.caption(f"{len(lecturas)} lectura(s) registradas el {fecha_s}.")

    texto_bias = _texto_bias(bias)
    if texto_bias:
        st.info("**Corrección por sesgo aplicada a la previsión** (media de "
                f"real − previsto de las últimas lecturas): {texto_bias}. "
                "La campana de probabilidad se estrecha alrededor de lo medido.")
    else:
        st.caption("Sin corrección por sesgo todavía: se activa al guardar lecturas "
                   "con Tª ambiente, HR o viento.")


def _panel_calibracion() -> None:
    """Overrides de config.yaml sobre una copia del Config, con recálculo al vuelo."""
    with st.expander("⚙️ Panel de calibración del modelo", expanded=False):
        st.caption("Mueve cualquier parámetro y el veredicto se recalcula con el "
                   "Monte Carlo. Valores por defecto = config.yaml (calibrados contra "
                   "el escenario del PDF). No se escriben en el archivo.")
        cols = st.columns(3, gap="small")
        for i, spec in enumerate(CALIB):
            with cols[i % 3]:
                # El valor vive en session_state (inicializado antes de instanciar
                # el widget): pasar `value` a la vez generaría un aviso de Streamlit.
                st.slider(spec["label"], min_value=spec["min"], max_value=spec["max"],
                          step=spec["step"], format=spec["fmt"],
                          key=f"calib_{spec['key']}", help=spec["ayuda"])
        if st.button("↺ Restablecer valores", key="btn_reset_calib", width="stretch"):
            # Se marca la orden y se aplica al arrancar el siguiente run (antes
            # de instanciar los widgets; Streamlit no permite lo contrario).
            st.session_state["reset_calibracion"] = True
            st.rerun()


# ----------------------------------------------------------- sección temporada
def _seccion_temporada() -> None:
    """Pestaña 📆 Temporada: KPIs + gráficas de la simulación histórica (ERA5)."""
    start, end = _rango_temporada()
    st.subheader(f"📆 Temporada {start} → {end}")

    df = _cargar_temporada(start, end, _rev_temporada(), DB_RUTA)
    if df is None or df.empty:
        st.warning(f"No hay resultados simulados para {start} → {end}.")
        st.info("Usa el botón **«🔄 (Re)simular temporada»** del menú lateral: descarga "
                "la meteorología observada (Open-Meteo Archive / ERA5) y simula cada "
                "día con Monte Carlo (≈15 s).")
        return

    df = _preparar_temporada(df)
    st.caption(f"{len(df)} días simulados con meteorología observada (ERA5), "
               f"{int(_CFG0.season.iterations)} iteraciones Monte Carlo por día y "
               "**sin corrección por sesgo** (no hay lecturas de campo de esa "
               "temporada).")
    _kpi_temporada(df)
    _mapa_calor_temporada(df)
    _serie_prob_temporada(df)
    _hist_cobertura_temporada(df)
    _box_temporada(df)
    _barras_temporada(df)
    _tabla_top10(df)


def _kpi_temporada(df: pd.DataFrame) -> None:
    """Días simulados, % con ventana, hora óptima mediana y mes más productivo."""
    n = len(df)
    con = df[df["ventana"]]
    cv = len(con)
    pct = 100.0 * cv / n if n else 0.0
    mediana = _hhmm(float(con["hora_dec"].median())) if cv else None

    por_mes = con.groupby("mes").size()
    if len(por_mes):
        m = int(por_mes.idxmax())
        mejor = f"{MESES[m - 1].capitalize()} ({int(por_mes.max())} días)"
    else:
        mejor = "—"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🗓️ Días simulados", f"{n}", help=f"Rango {df['date'].iloc[0]} → "
              f"{df['date'].iloc[-1]}.")
    c2.metric("🌿 Días con ventana", f"{pct:.0f}%", delta=f"{cv} de {n}",
              help="Días en los que al menos un escenario abre ventana de cosecha.")
    c3.metric("🎯 Hora óptima mediana", mediana or "—",
              help="Mediana de las horas óptimas de los días con ventana.")
    c4.metric("🏆 Mes más productivo", mejor,
              help="Mes con más días que alcanzan la ventana de cosecha.")


def _mapa_calor_temporada(df: pd.DataFrame) -> None:
    """Calendario (Y = mes, X = día) coloreado por la hora óptima de cada día."""
    st.subheader("🗓️ Mapa de calor de la temporada")
    con = df[df["ventana"]]
    if con.empty or con["hora_dec"].isna().all():
        st.info("Ningún día de la temporada alcanzó ventana de cosecha.")
        return

    horas = con["hora_dec"].dropna().to_numpy()
    zmin = float(np.floor(horas.min())) - 0.5
    zmax = float(np.ceil(horas.max())) + 0.5
    sin_dato = zmin - 1.0            # por debajo de zmin → gris (celdas sin ventana)
    # YlOrRd salvo el tramo inicial de la escala, reservado al gris "sin ventana"
    escala = [[0.0, GRIS_CELDA], [0.005, GRIS_CELDA]]
    n_colores = len(_SEQUENTIAL.YlOrRd) - 1
    escala += [[0.01 + 0.99 * i / n_colores, c]
               for i, c in enumerate(_SEQUENTIAL.YlOrRd)]

    anio = int(df["fecha"].dt.year.dropna().iloc[0])
    meses = sorted(int(m) for m in df["mes"].dropna().unique())
    registros = {(int(r.mes), int(r.dia)): r for r in df.itertuples(index=False)
                 if pd.notna(r.mes) and pd.notna(r.dia)}

    z: list[list[float | None]] = []
    texto: list[list[str | None]] = []
    for m in meses:
        fila_z: list[float | None] = []
        fila_t: list[str | None] = []
        for d in range(1, 32):
            try:
                fecha_txt = date(anio, m, d).isoformat()
            except ValueError:          # p. ej. 31 de abril → celda inexistente
                fila_z.append(None)
                fila_t.append(None)
                continue
            reg = registros.get((m, d))
            if reg is None:
                fila_z.append(sin_dato)
                fila_t.append(f"{fecha_txt}<br>no simulado")
            elif not bool(reg.ventana):
                fila_z.append(sin_dato)
                fila_t.append(f"{fecha_txt}<br>sin ventana<br>"
                              f"prob. {reg.prob_ventana:.0%}")
            else:
                fila_z.append(float(reg.hora_dec))
                fila_t.append(f"{fecha_txt}<br>ventana {reg.window_start}–"
                              f"{reg.window_end}<br>óptima {reg.hora_optima} · "
                              f"prob. {reg.prob_ventana:.0%}")
        z.append(fila_z)
        texto.append(fila_t)

    ticks_hora = list(np.arange(np.ceil(zmin), np.floor(zmax) + 0.01, 1.0))
    fig = go.Figure(go.Heatmap(
        z=z, x=list(range(1, 32)), y=[MESES_CORTO[m - 1] for m in meses],
        text=texto, colorscale=escala, zmin=zmin, zmax=zmax,
        xgap=1, ygap=1, hovertemplate="%{text}<extra></extra>",
        colorbar={"title": "Hora", "title_font_size": 11, "thickness": 14, "len": 0.9,
                      "tickvals": ticks_hora,
                      "ticktext": [_hhmm(t) or "" for t in ticks_hora],
                      "tickfont_size": 10},
    ))
    fig.update_xaxes(dtick=2, tickfont_size=10, title="Día del mes",
                     gridcolor="#FFFFFF", zeroline=False)
    fig.update_yaxes(autorange="reversed", tickfont_size=11, title="Mes",
                     gridcolor="#FFFFFF", zeroline=False)
    fig.update_layout(
        height=400, margin={"l": 10, "r": 10, "t": 45, "b": 10},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#212121"},
    )
    st.plotly_chart(fig, width="stretch", theme="streamlit",
                    config={"displayModeBar": False})
    st.caption("Color = hora óptima (barra de color en HH:MM) · gris = día sin "
               "ventana o no simulado · blanco = día inexistente. Pasa el cursor "
               "para ver fecha, ventana y probabilidad.")


def _serie_prob_temporada(df: pd.DataFrame) -> None:
    """Área diaria de la probabilidad de ventana (0-1) con umbral al 50 %."""
    st.subheader("📈 Probabilidad de ventana día a día")
    y = df["prob_ventana"].astype(float).fillna(0.0)   # día sin ventana → 0
    fig = go.Figure(go.Scatter(
        x=df["fecha"], y=y, mode="lines", name="Probabilidad",
        line={"color": TEAL, "width": 2}, fill="tozeroy",
        fillcolor="rgba(0,105,92,0.25)",
        customdata=[f"{d} · {p:.0%}" for d, p in zip(df["date"], y, strict=False)],
        hovertemplate="%{customdata}<extra></extra>",
    ))
    fig.add_hline(y=0.5, line_dash="dot", line_color=ROJO, line_width=2,
                  annotation_text="50 %", annotation_font_color=ROJO)
    fig.update_xaxes(gridcolor="#E0E0E0", zeroline=False)
    fig.update_yaxes(title="Probabilidad de ventana", range=[0, 1], dtick=0.25,
                     tickformat=".0%", gridcolor="#E0E0E0", zeroline=False)
    fig.update_layout(
        height=320, margin={"l": 10, "r": 10, "t": 40, "b": 10}, showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#212121"},
    )
    st.plotly_chart(fig, width="stretch", theme="streamlit",
                    config={"displayModeBar": False})
    st.caption("Área = probabilidad de que ese día haya ventana (días sin ventana, "
               "0 %). Por encima de la línea roja discontinua el día es «seguro».")


def _hist_cobertura_temporada(df: pd.DataFrame) -> None:
    """Histograma de horas óptimas (bines de 30 min) + % de días con ventana por hora."""
    st.subheader("🕰️ Distribución de la hora óptima y cobertura por hora")
    con = df[df["ventana"]]
    if con.empty:
        st.info("Sin días con ventana en la temporada: no hay horas óptimas que repartir.")
        return

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Días por hora óptima**")
        bins = np.floor(con["hora_dec"].to_numpy() * 2.0) / 2.0
        conteo = pd.Series(bins).value_counts().sort_index()
        fig = go.Figure(go.Bar(
            x=[float(i) for i in conteo.index], y=[int(v) for v in conteo.values],
            width=0.45, marker={"color": TEAL, "line": {"width": 1, "color": "#FFFFFF"}},
            customdata=[_hhmm(float(i)) for i in conteo.index],
            hovertemplate="Óptima %{customdata}<br>%{y} día(s)<extra></extra>",
        ))
        _ejes_horas(fig, titulo_y="Días")
        fig.update_layout(height=320, margin={"l": 10, "r": 10, "t": 10, "b": 10},
                          paper_bgcolor="rgba(0,0,0,0)",
                          plot_bgcolor="rgba(0,0,0,0)", font={"color": "#212121"})
        st.plotly_chart(fig, width="stretch", theme="streamlit",
                        config={"displayModeBar": False})
        st.caption(f"Bines de 30 min sobre los {len(con)} días con ventana.")

    with c2:
        st.markdown("**% de días en los que la ventana cubre cada hora**")
        horas = np.arange(6.0, 21.01, 0.25)
        ini = con["ini_dec"].to_numpy()
        fin = con["fin_dec"].to_numpy()
        ok = ~np.isnan(ini) & ~np.isnan(fin)
        cob = [100.0 * float(np.sum(ok & (ini <= h) & (fin >= h))) / len(df)
               for h in horas]
        fig2 = go.Figure(go.Scatter(
            x=horas, y=cob, mode="lines", name="Cobertura",
            line={"color": "#2E7D32", "width": 2.5}, fill="tozeroy",
            fillcolor="rgba(46,125,50,0.20)",
            customdata=[_hhmm(h) for h in horas],
            hovertemplate="%{customdata} · %{y:.0f} % de días<extra></extra>",
        ))
        i_pico = int(np.argmax(cob))
        if cob[i_pico] > 0:
            fig2.add_trace(go.Scatter(
                x=[horas[i_pico]], y=[cob[i_pico]], mode="markers+text",
                marker={"color": ROJO, "size": 8},
                text=[f"{_hhmm(horas[i_pico])} · {cob[i_pico]:.0f} %"],
                textposition="top center", textfont={"color": ROJO, "size": 11},
                showlegend=False, hoverinfo="skip",
            ))
        _ejes_horas(fig2, titulo_y="% de días", rango_y=[0, 100])
        fig2.update_yaxes(dtick=25)
        fig2.update_layout(height=320, margin={"l": 10, "r": 10, "t": 10, "b": 10},
                           paper_bgcolor="rgba(0,0,0,0)",
                           plot_bgcolor="rgba(0,0,0,0)", font={"color": "#212121"})
        st.plotly_chart(fig2, width="stretch", theme="streamlit",
                        config={"displayModeBar": False})
        st.caption(f"Cálculo sobre los {len(df)} días simulados: recuento de días "
                   "cuya ventana [inicio–fin] incluye cada hora.")


def _ejes_horas(fig: go.Figure, titulo_y: str = "", rango_y: list | None = None) -> None:
    """Ejes con horas en HH:MM (X) y rejilla suave (común a los gráficos de temporada)."""
    ticks = list(range(6, 22, 2))
    fig.update_xaxes(tickvals=ticks, ticktext=[f"{t:02d}:00" for t in ticks],
                     gridcolor="#E0E0E0", zeroline=False)
    ejey: dict = {"title": titulo_y, "gridcolor": "#E0E0E0", "zeroline": False}
    if rango_y:
        ejey["range"] = rango_y
    fig.update_yaxes(**ejey)


def _box_temporada(df: pd.DataFrame) -> None:
    """Box plot de la hora óptima (decimal) por mes, con los puntos en jitter."""
    st.subheader("📦 Hora óptima por mes")
    con = df[df["ventana"]]
    if con.empty:
        st.info("Sin días con ventana en la temporada.")
        return
    fig = go.Figure()
    for m in sorted(int(x) for x in con["mes"].dropna().unique()):
        sub = con[con["mes"] == m]
        fig.add_trace(go.Box(
            y=sub["hora_dec"].to_numpy(), name=MESES_CORTO[m - 1],
            boxpoints="all", jitter=0.35, pointpos=0,   # todos los puntos, dispersados
            marker={"color": TEAL, "size": 4, "opacity": 0.55},
            line={"color": TEAL, "width": 2}, fillcolor="rgba(0,105,92,0.15)",
            customdata=[_hhmm(float(v)) for v in sub["hora_dec"]],
            hovertemplate="%{customdata}<extra></extra>",
            showlegend=False,
        ))
    _ejes_horas(fig, titulo_y="Hora óptima")
    ymin = float(np.floor(con["hora_dec"].min()))
    ymax = float(np.ceil(con["hora_dec"].max())) + 1.0
    yt = list(np.arange(ymin, ymax + 0.01, 1.0))
    fig.update_yaxes(tickvals=yt, ticktext=[_hhmm(t) or "" for t in yt],
                     title="Hora óptima", range=[ymin - 0.5, ymax + 0.5],
                     gridcolor="#E0E0E0", zeroline=False)
    fig.update_layout(
        height=340, margin={"l": 10, "r": 10, "t": 10, "b": 10}, showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#212121"},
    )
    st.plotly_chart(fig, width="stretch", theme="streamlit",
                    config={"displayModeBar": False})
    st.caption("Caja = meses 25-75 % con mediana · puntos = días concretos · "
               "bigotes = rango típico. Compara la dispersión entre meses: a más "
               "caja ancha, más variable es la hora de cosecha.")


def _barras_temporada(df: pd.DataFrame) -> None:
    """Barras mensuales apiladas: días con ventana vs total de días simulados."""
    st.subheader("📊 Días con ventana por mes")
    meses = sorted(int(m) for m in df["mes"].dropna().unique())
    totales = df.groupby("mes").size()
    con_ventana = df[df["ventana"]].groupby("mes").size()
    tot = [int(totales.get(m, 0)) for m in meses]
    con = [int(con_ventana.get(m, 0)) for m in meses]
    etiquetas = [f"{c}/{t} · {100.0 * c / t:.0f} %" if t else ""
                 for c, t in zip(con, tot, strict=False)]
    nombres = [MESES_CORTO[m - 1] for m in meses]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=nombres, y=con, name="Con ventana", marker={"color": TEAL},
        text=etiquetas, textposition="inside", textfont={"color": "#FFFFFF", "size": 11},
        customdata=[f"{MESES[m - 1]}" for m in meses],
        hovertemplate="%{customdata}<br>%{y} días con ventana<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=nombres, y=[t - c for t, c in zip(tot, con, strict=False)], name="Sin ventana",
        marker={"color": GRIS_CELDA, "line": {"color": "#BDBDBD", "width": 1}},
        hovertemplate="%{x}<br>%{y} días sin ventana<extra></extra>",
    ))
    fig.update_layout(barmode="stack", height=340,
                      margin={"l": 10, "r": 10, "t": 10, "b": 10},
                      legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font={"color": "#212121"})
    fig.update_xaxes(gridcolor="#E0E0E0", zeroline=False, title="Mes")
    fig.update_yaxes(title="Días", gridcolor="#E0E0E0", zeroline=False)
    st.plotly_chart(fig, width="stretch", theme="streamlit",
                    config={"displayModeBar": False})
    st.caption("Barra apilada por mes: verde = días con ventana (etiqueta "
               "«con ventana / total · %»), gris = días sin ventana.")


def _tabla_top10(df: pd.DataFrame) -> None:
    """Top-10 de los mejores días de la temporada (probabilidad de ventana)."""
    st.subheader("🏆 Top-10 mejores días")
    con = df[df["ventana"]]
    if con.empty:
        st.info("Sin días con ventana en la temporada.")
        return
    top = con.sort_values("prob_ventana", ascending=False).head(10)
    tabla = pd.DataFrame({
        "Fecha": [str(d) for d in top["date"]],
        "Hora óptima": [str(h) for h in top["hora_optima"]],
        "Ventana": [f"{a} – {b}" for a, b in zip(top["window_start"], top["window_end"], strict=False)],
        "Prob. ventana": [f"{float(p):.0%}" for p in top["prob_ventana"]],
    })
    st.dataframe(tabla, width="stretch", hide_index=True, row_height=34)
    st.caption("Ordenado por probabilidad de ventana (de mayor a menor).")


def _pie(datos: dict | None) -> None:
    """Fuente del modelo y aviso legal."""
    st.divider()
    st.markdown(
        "**Fuente del modelo:** «Modelo flor de sal.pdf» (Ley de Dalton modificada, "
        "umbral de sobresaturación y fases 0–3) · **Previsión:** Open-Meteo (sin API key) "
        "· **Simulación:** Monte Carlo con corrección por sesgo sobre datos de campo."
    )
    st.caption(
        "⚠️ La predicción es una **estimación probabilística**, no una garantía: las "
        "condiciones reales de la salina prevalecen siempre. Los coeficientes del "
        "modelo (Dalton a/b, sigmas, umbral, lámina y minutos de crecimiento) se "
        "calibran con datos reales mediante el panel de calibración y la corrección "
        "por sesgo, por lo que la predicción mejora a medida que registras lecturas."
    )
    if datos:
        v = datos["veredicto"]
        st.caption(f"Veredicto del {v.get('fecha', '—')} · calculado "
                   f"{v.get('computed_at', '—')} · {int(v.get('n_iter') or 0)} escenarios.")


# --------------------------------------------------------------------- app
def main() -> None:
    """Pinta la app: sección 🌞 Hoy o sección 📆 Temporada (según el radio)."""
    db = _db()
    db.init_schema()
    st.session_state.setdefault("rev", 0)
    _inicializar_calibracion()

    fecha, seccion = _sidebar(db)
    fecha_s = fecha.isoformat() if isinstance(fecha, date) else str(fecha)

    if _LOGO_BYTES is not None:
        st.image(str(LOGO_PATH), width=340)   # "Salinas de Dueñas" (marca)
    st.title("🧂 Flor de Sal — Hora óptima de recolección")
    if seccion.startswith("📆"):
        _start, _end = _rango_temporada()
        st.caption(f"{_CFG0.location.name} · {_CFG0.location.latitude}, "
                   f"{_CFG0.location.longitude} · temporada {_start} → {_end} (ERA5)")
    else:
        st.caption(f"{_CFG0.location.name} · {_CFG0.location.latitude}, "
                   f"{_CFG0.location.longitude} · día {fecha_s}")

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
                          int(st.session_state["rev"]), datetime.now().hour, DB_RUTA)
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
    _panel_calibracion()
    _pie(datos)


main()
