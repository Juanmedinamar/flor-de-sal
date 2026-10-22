"""Sección 🌞 Hoy: veredicto, semáforo Márkov, campana, datos del día y formulario."""
from __future__ import annotations

from datetime import datetime
from datetime import time as Hora

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.ui.constantes import (
    CALIB,
    COLORES_FASE,
    COLUMNAS_LECTURAS,
    CONFIG_TABLA,
    ESTADOS_MARKOV,
    LAYOUT_BASE,
    ROJO,
    TEAL,
)
from app.ui.helpers import (
    _estilizar,
    _hhmm_decimal,
    _mostrar_grafico,
    _texto_bias,
    ahora,
    hoy,
)
from src.db import Database
from src.pipeline import _hhmm


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
        **LAYOUT_BASE,
    )
    _mostrar_grafico(fig)
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

    es_hoy = str(datos["veredicto"].get("fecha")) == hoy().isoformat()
    if es_hoy:
        x_ahora = ahora()
        x_dec = x_ahora.hour + x_ahora.minute / 60.0
        if min(horas) <= x_dec <= max(horas):
            fig.add_vline(x=x_dec, line_dash="dot", line_color="#424242",
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
        **LAYOUT_BASE,
    )
    _mostrar_grafico(fig)
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
            _mostrar_grafico(fig)
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
        **LAYOUT_BASE,
    )
    _mostrar_grafico(fig)
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
        hora = f1[0].time_input("Hora", value=ahora().time().replace(second=0, microsecond=0),
                                format="24h", help="Hora de la lectura.")
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


def _panel_cosecha(db: Database, fecha_s: str) -> None:
    """Formulario para registrar kg de flor de sal cosechados."""
    st.subheader("🌾 Cosecha del día")
    st.caption("Registra los kg de flor de sal recolectados hoy. Se guarda en la BD "
               "para comparar con la predicción y validar el modelo.")
    with st.form("form_cosecha", clear_on_submit=True, width="stretch"):
        f1 = st.columns(3)
        kg = f1[0].number_input("Kg cosechados", min_value=0.0, max_value=10000.0,
                                value=None, step=0.5, format="%.1f", placeholder="—",
                                help="Kilogramos de flor de sal recolectados hoy.")
        zone_id = f1[1].text_input("Zona", value="default", max_chars=20,
                                   placeholder="default", help="Identificador de zona "
                                   "(para futuro multi-zona).")
        notas = f1[2].text_input("Notas", placeholder="p. ej. «cosecha completa zona A»")
        enviado = st.form_submit_button("💾 Guardar cosecha", type="primary",
                                        width="stretch")

    if not enviado:
        return
    if kg is None or kg <= 0:
        st.warning("Introduce un valor positivo de kg.")
        return
    db.save_harvest(fecha_s, float(kg), zone_id=zone_id or "default", notes=notas or "")
    st.session_state["rev"] = int(st.session_state.get("rev", 0)) + 1
    st.session_state["aviso"] = ("ok",
                                 f"Cosecha de {kg:.1f} kg guardada para {fecha_s}.")
    st.rerun()


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
