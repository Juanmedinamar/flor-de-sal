"""Paquete UI de Flor de Sal (Streamlit).

Estructura:

- `constantes.py` — colores, estados de Márkov, espec de calibración y datos fijos.
- `textos.py`     — textos en español compartidos por varios paneles (sin i18n).
- `helpers.py`    — formatos, estilos de tabla, gráficos y zona horaria.
- `state.py`      — caché de cálculo (Monte Carlo / temporada) y session_state.
- `sidebar.py`    — menú lateral (navegación, fecha, descarga, simulación).
- `panel_hoy.py`  — sección 🌞 Hoy (veredicto, semáforo, campana, formulario…).
- `panel_temporada.py` — sección 📆 Temporada (KPIs y gráficas históricas).
- `main.py`       — orquestación: pinta la sección elegida y el pie.
"""
