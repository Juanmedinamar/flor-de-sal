# Flor de Sal — Memoria del proyecto (AGENTS.md)

## Qué es esto
App Python (Streamlit) que **predice con probabilidad la hora óptima de recogida de flor de sal**
en una salina de Córdoba, cruzando:
1. **Previsión meteorológica** horaria (Open-Meteo, sin API key).
2. **Datos reales de campo** introducidos a lo largo del día (Tª calentador/cristalizadores,
   concentración g/l, T/HR/V medidos).
3. **Motor físico + Monte Carlo** (1000 escenarios) con corrección por sesgo (rolling forecast).

Fuente del modelo: `../Modelo flor de sal.pdf` (10 páginas). Resumen del modelo abajo.

## Modelo físico (fiel al PDF)

### Evaporación — Ley de Dalton modificada
```
E_día[mm/día] = (a + b·V[viento m/s]) · VPD[kPa]
E_hora = E_día / 24
VPD = Psat(T_agua) − Pvapor_aire        (en kPa; internamente se calcula en hPa y se pasa a kPa)
Psat(T) = 6.1078 · exp(17.27·T / (T+237.3))   [hPa, Tetens]
Pvapor_aire = HR/100 · Psat(T_ambiente)
```
Coeficientes por defecto: `a=0.17`, `b=0.87` (calibrables en `config.yaml` y UI).

### Temperatura del agua (lámina superficial)
```
T_agua(h) = T_ambiente(h) + coef_solar·(radiación/1000) + extra_mañana(h)
extra_mañana: t_extra_manana_c decae linealmente de las 06:00 a las 12:00 (entrada caliente del concentrador)
```

### Concentración (masa de sal constante, se pierde agua)
```
Modelo "masa" (default, físicamente correcto):  C_t = C0 / (1 − ΣE/h)
Modelo "lineal" (aprox. PDF):                   C_t = C0 · (1 + ΣE/h)
h = profundidad de lámina en mm (cm·10). ΣE en mm acumulados.
```
Arranque: C0 = 295 g/l (entrada del cristalizador, tras concentrador 290-300).

### Umbral de sobresaturación (nucleación)
```
umbral(T_agua) = 318 + 0.5·(T_agua − 25)    [g/l]  (rango PDF: 315-320)
```

### Fases del día (semáforo)
- **Fase 0 — Inactividad**: C_sup < umbral.
- **Fase 1 — Nucleación**: C_sup ≥ umbral; empiezan los microcristales.
- **Fase 2 — Ventana óptima**: nucleación + `minutos_crecimiento` (120 min) → crece la película.
- **Fase 3 — Cierre/riesgo**: viento > 5.5 m/s (hundimiento), o HR repunta por encima de
  `hr_cierre_tarde_pct` (45%) tras el mínimo, o HR > 65% (rehidratación), o fin de sim (21:00).

**Hora óptima (por escenario)** = centro de la ventana de cosecha
(`apertura + 0.5·duración`): el tramo final es el más espeso pero también el más
arriesgado (Fase 3), y al abrir la película aún está fresca; el centro es el
momento representativo más seguro para pasar la rastrilla. Si nunca se abre
ventana → escenario sin cosecha (NaN).

### Monte Carlo
- Muestrear por hora: `T ~ N(Tprev, σT)`, `HR ~ N(HRprev, σHR)` trunc [5,99],
  `V ~ N(Vprev, σV)` trunc [0,∞). σ por defecto en `config.yaml`.
- Corrección por sesgo (asimilación): `bias = media(real − previsto)` últimas N horas;
  se aplica a las horas restantes del día → la campana se estrecha.

### Calibración por defecto (importante)
Los coeficientes de Dalton por defecto (a=0.45, b=2.30) son ~2,6× la literatura clásica
(a≈0.17, b≈0.87 para láminas libres): la lámina somera y oscura del cristalizador
evapora más. Con C0=300 g/l y pendiente de umbral 0.25 g/l/°C, el escenario de verano
del PDF produce: ventana 16:00-20:00, óptima 18:00 con IC95 16:30-18:30 (coherente con
la cosecha 16-19h del PDF). Todos estos valores son calibrables con datos reales.
El Monte Carlo está vectorizado (NumPy): 1000 escenarios en <0,1 s.

### Salida esperada (veredicto del día)
- Fase actual, ventana más probable [inicio–fin], hora óptima mediana + IC 95%,
  prob. de ventana, prob. de Fase 3 (riesgo), alertas.

### Escenario de validación (día típico verano Córdoba, del PDF)
06h:18°C/HR85%/V0.5 · 10h:26/55/1.5 · 12h:31/40/2.5 · 14h:34/30/3 ·
16h:35/28/3 · 18h:32/33/2.5 · 20h:26/45/1.5.
**Resultado esperado**: nucleación ~14h, ventana ~16:00-19:30, óptima ~17:45
(PDF: cosecha 16-19h), sin ventana en día nublado/húmedo (HR>70%).

## Decisiones tomadas
- **Open-Meteo** (sin API key) para previsión horaria. Coordenadas en `config.yaml`.
- **SQLite local** en `data/flor_desal.db` (fuente de verdad en el PC).
- **Monte Carlo 1000** iteraciones (no Márkov ni EDE en v1).
- **Streamlit** como UI; estructura lista para despliegue futuro (config externa).
- Simulación horaria 06:00–21:00.

## Mapa de propiedad de archivos (NO toques archivos de otro agente)
- `temporada`: `src/historical.py`, `scripts/season_simulation.py`, `tests/test_historical.py`
- `markov`: `src/markov.py`, `tests/test_markov.py`
- `fisica-sal`: `src/physics.py`, `tests/test_physics.py` (montecarlo/asimilación completados por el coordinador)
- `data-ingest`: `src/weather.py`, `scripts/init_db.py`, `scripts/ingest_forecast.py`, `tests/test_weather.py`, `tests/test_db.py`
- `ui-streamlit`: `app/streamlit_app.py`, `app/assets/` (logo), `.streamlit/config.toml`, `README.md`
- Coordinador (principal): `src/config.py`, `src/alerts.py`, `src/pipeline.py`, `src/db.py`,
  `src/montecarlo.py`, `src/assimilation.py`, `config.yaml`, `tests/conftest.py`, `AGENTS.md`

## Capa de Márkov (semáforo probabilístico, PDF pág. 8 §2)
- 5 estados: inactivo, concentración crítica (a <`margen_critico_g_l` del umbral),
  nucleación, ventana, degradación.
- Matriz de transición hora→hora estimada contando saltos de estado en el ensemble
  del Monte Carlo (`montecarlo.simulate_ensemble` → `EnsembleResult` con fase/C/umbral
  por escenario y hora).
- Propagación π(h+1)=π(h)·T(h) → curva "P(estado a cada hora)" (instantánea).
- Coherencia MC↔Markov garantizada por test (tolerancia 0.08).

## Simulación de temporada (histórico)
- Fuente: Open-Meteo Archive (ERA5, observado/reanálisis), sin API key.
- Rango por defecto: 2026-04-01 → 2026-10-15 (verificado en Fase 0: datos hasta 2026-10-21).
- `scripts/season_simulation.py` recorre los días, ejecuta Monte Carlo (bias=0,
  reconstrucción con meteorología observada) y guarda en tabla `season_runs` (db.py).
- Sin lecturas de campo de esa temporada → no hay corrección por sesgo (documentado).

## Cómo ejecutar
```bash
# dependencias
python3 -m pip install -r requirements.txt
# base de datos
python3 scripts/init_db.py
# previsión del día (a las 06:00 o a demanda)
python3 scripts/ingest_forecast.py            # hoy
python3 scripts/ingest_forecast.py 2026-07-15 # fecha concreta
# tests
python3 -m pytest tests/ -q
# app
python3 -m streamlit run app/streamlit_app.py
```

## Convenciones
- Python 3.13, type hints, docstrings en español con la ecuación usada.
- Unidades: presiones hPa (se convierten a kPa para Dalton), E en mm (=L/m²), V m/s, C g/l, T °C.
- Sin dependencias nuevas fuera de `requirements.txt` sin consultarlo.
- Los tests deben pasar con `pytest -q` antes de dar por terminada una tarea.
