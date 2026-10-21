"""Sección 📆 Temporada: KPIs y gráficas de la simulación histórica (ERA5)."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.colors import sequential as _SEQUENTIAL

from app.ui.constantes import (
    _CFG0,
    GRIS_CELDA,
    LAYOUT_BASE,
    MESES,
    MESES_CORTO,
    ROJO,
    TEAL,
)
from app.ui.helpers import _ejes_horas, _mostrar_grafico
from app.ui.state import (
    DB_RUTA,
    _cargar_temporada,
    _preparar_temporada,
    _rango_temporada,
    _rev_temporada,
)
from app.ui.textos import SIN_DIAS_CON_VENTANA
from src.pipeline import _hhmm


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
        **LAYOUT_BASE,
    )
    _mostrar_grafico(fig)
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
        **LAYOUT_BASE,
    )
    _mostrar_grafico(fig)
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
                          **LAYOUT_BASE)
        _mostrar_grafico(fig)
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
                           **LAYOUT_BASE)
        _mostrar_grafico(fig2)
        st.caption(f"Cálculo sobre los {len(df)} días simulados: recuento de días "
                   "cuya ventana [inicio–fin] incluye cada hora.")


def _box_temporada(df: pd.DataFrame) -> None:
    """Box plot de la hora óptima (decimal) por mes, con los puntos en jitter."""
    st.subheader("📦 Hora óptima por mes")
    con = df[df["ventana"]]
    if con.empty:
        st.info(SIN_DIAS_CON_VENTANA)
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
        **LAYOUT_BASE,
    )
    _mostrar_grafico(fig)
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
                      **LAYOUT_BASE)
    fig.update_xaxes(gridcolor="#E0E0E0", zeroline=False, title="Mes")
    fig.update_yaxes(title="Días", gridcolor="#E0E0E0", zeroline=False)
    _mostrar_grafico(fig)
    st.caption("Barra apilada por mes: verde = días con ventana (etiqueta "
               "«con ventana / total · %»), gris = días sin ventana.")


def _tabla_top10(df: pd.DataFrame) -> None:
    """Top-10 de los mejores días de la temporada (probabilidad de ventana)."""
    st.subheader("🏆 Top-10 mejores días")
    con = df[df["ventana"]]
    if con.empty:
        st.info(SIN_DIAS_CON_VENTANA)
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
