# 🧂 Flor de Sal — Predictor de la hora óptima de recolección

![Salinas de Dueñas](app/assets/logo.png)

App Python (Streamlit) que estima **con probabilidad** la ventana óptima de recolección de
flor de sal en una salina de Córdoba, cruzando tres fuentes de información:

1. **Previsión meteorológica horaria** de [Open-Meteo](https://open-meteo.com/) (sin API key).
2. **Datos reales de campo** que introduces a lo largo del día (Tª del calentador y del
   cristalizador, concentración g/l, Tª ambiente, HR y viento).
3. **Modelo físico + Monte Carlo** (1000 escenarios, <0,1 s) con **corrección por sesgo**
   (asimilación de las lecturas reales sobre la previsión).

Salen el **semáforo de fases** (0 inactividad · 1 nucleación · 2 ventana óptima ·
3 cierre/riesgo), la **ventana más probable**, la **hora óptima con su IC 95 %**, la
**probabilidad de ventana** y de **riesgo**, y las **alertas** del momento.

La app tiene **dos secciones** (radio en el menú lateral):

- **🌞 Hoy** — veredicto, semáforo probabilístico, campana, gráficas del día,
  formulario de datos reales y panel de calibración.
- **📆 Temporada** — simulación histórica de la temporada con meteorología
  observada (ERA5): KPIs, calendario de horas óptimas y mejores días.

- Modelo físico y memoria del proyecto: `AGENTS.md` y `../Modelo flor de sal.pdf`
  (Ley de Dalton modificada, umbral de sobresaturación, fases y reglas de riesgo).
- Todo es calibrable: los coeficientes no se guardan en el código, se ajustan desde la
  UI o en `config.yaml`.

## Instalación

```bash
python3 -m pip install -r requirements.txt
python3 scripts/init_db.py        # crea data/flor_desal.db (idempotente)
```

## Uso diario

```bash
# 1) Descargar la previsión del día (a las 06:00 o a demanda)
python3 scripts/ingest_forecast.py            # hoy
python3 scripts/ingest_forecast.py 2026-07-15 # fecha concreta (YYYY-MM-DD)

# 2) Lanzar la app
python3 -m streamlit run app/streamlit_app.py
```

> La app también descarga la previsión sola: si la fecha seleccionada no tiene datos,
> usa el botón **«⬇️ Descargar/guardar previsión del día»** del menú lateral (o el
> pipeline la descarga al calcular el veredicto).

Durante el día:

1. Abre la app (por defecto, la fecha de **hoy**) y lee el **veredicto**: fase actual,
   ventana, hora óptima con IC 95 % y alertas.
2. Cada 1–2 horas registra una lectura en **«📐 Datos reales de campo»**
   (hora, Tª, HR, viento, concentración…). Al guardarla, el veredicto **se recalcula
   solo** aplicando la corrección por sesgo (media de *real − previsto*) y la campana
   de probabilidad se estrecha.
3. Consulta la **campana** y la **tabla horaria** (Tª del agua, evaporación,
   concentración y fase hora a hora).
4. Si el modelo se desvía de lo que ves en la salina, ajusta los parámetros en el
   **panel de calibración** (Dalton a/b, sigmas, umbral, profundidad, minutos de
   crecimiento). Los cambios recalculan al instante y **no escriben** en `config.yaml`
   (botón **«↺ Restablecer valores»** para volver a los de fichero).
5. Cambia el radio del menú lateral a **«📆 Temporada»** para ver el calendario de
   horas óptimas, la probabilidad de ventana día a día y los mejores días del año
   (y **«🔄 (Re)simular temporada»** si acabas de cambiar el rango de `config.yaml`).

## La app, pantalla por pantalla (captura lógica del panel)

Así queda el panel al abrirlo (ejemplo con los valores de un día fresco y húmedo):

```
┌─ MENÚ LATERAL ─────────────────────┐
│ ## 🧂 Flor de Sal                  │
│ 📂 Sección: (🌞 Hoy)(📆 Temporada) │  ← radio de navegación
│ 📅 Fecha del veredicto   [hoy     ]│
│ [⬇️ Descargar/guardar previsión]   │
│ ─────────────────────────────────  │
│ Semáforo de fases                  │
│ ⬜ Fase 0 — Inactividad            │
│ 🟧 Fase 1 — Nucleación             │
│ 🟩 Fase 2 — Ventana óptima         │
│ 🟥 Fase 3 — Cierre/riesgo          │
│ Salina Córdoba · 37.89, -4.78      │
└────────────────────────────────────┘
 (en 📆 Temporada el bloque de fecha se sustituye por
  [🔄 (Re)simular temporada] + última salida de la CLI)

🧂 Flor de Sal — Hora óptima de recolección
Salina Córdoba · 37.8882, -4.7794 · día 2026-10-21

🚦 Veredicto del día
┌──────────────────────────────────────────────────────────────────────┐
│ ⬜ Fase 0 — Inactividad (la salmuera aún no está sobresaturada)      │  ← caja GRIS
│  (si fuera naranja → st.warning "Fase 1", verde → st.success        │
│   "Fase 2", rojo → st.error "Fase 3")                               │
├────────────────┬───────────────────┬────────────────┬────────────────┤
│ 🌀 Ventana     │ 🎯 Hora óptima    │ 📈 Prob. de    │ ⚠️ Prob. de    │
│ Sin ventana hoy│ —                 │ ventana  0%    │ riesgo     0%  │
│                │ sin estimación    │                │                │
├────────────────┴───────────────────┴────────────────┴────────────────┤
│ Probabilidad de ventana óptima      Probabilidad de riesgo (Fase 3)   │
│ ▓▓▓▓▓▓░░░░░░░░░░ 0% de los 1000     ░░░░░░░░░░░░░░░░ 0% cierran por  │
│                    escenarios abren               riesgo             │
├──────────────────────────────────────────────────────────────────────┤
│ 🔔 Alertas del momento                                               │
│ 🟥 Humedad relativa 67% > 65%: la flor de sal se rehidrata…          │
│ 🟨 Temperatura 15.2 °C: proceso lento, la ventana se retrasa.        │
└──────────────────────────────────────────────────────────────────────┘

🚦 Semáforo probabilístico de la balsa (Márkov)
 (áreas APILADAS hora a hora con los 5 estados, eje Y en %:
  gris #9E9E9E inactivo · ámbar #FFC107 concentración crítica ·
  naranja #FF9800 nucleación · verde #2E7D32 ventana ·
  rojo #C62828 degradación · línea vertical punteada «ahora» ·
  guía: «¿A qué hora es más probable que esté la ventana? 19h: 79%»)

🔔 Campana de probabilidad de la hora óptima
 (plotly) barras teal de densidad · sombreado verde = IC 95 % ·
 línea roja discontinua = mediana (hora óptima) · eje X en HH:MM
 (sin ventana → aviso informativo en lugar del gráfico)

🌤️ Previsión vs lecturas reales
 (3 mini-gráficos T / HR / V: línea teal = previsión horaria
  —con el sesgo aplicado en el subtítulo— y puntos rojos = lecturas
  del formulario; solo se muestra si ya hay lecturas)

📈 Evolución de la predicción del día
 (hora óptima de cada cálculo + banda IC 95 %, con línea discontinua
  en el último cálculo · <2 cálculos → texto explicativo)

📋 Tabla horaria del día
 Hora    T aire  HR  Viento  T agua  Evap.mm/h  Concentración  Fase
 06:00    12,4   88   0,6     16,8     0,031        300,0      ⬜ 0 · Inactividad
 …        …      …    …       …        …            …          🟧 1 · Nucleación
 14:00    24,1   49   2,4     31,2     0,114        318,6      🟩 2 · Ventana óptima
 18:00    22,8   55   1,9     26,4     0,072        342,1      🟥 3 · Cierre/riesgo
 (cada celda de la columna «Fase» lleva su badge de color)

📐 Datos reales de campo
 [Hora] [Tª calentador] [Tª cristalizador] [Concentración]
 [Tª ambiente] [HR] [Viento] [Notas]
 [💾 Guardar lectura]   → guarda y recalcula con corrección por sesgo

📔 Lecturas del día y sesgo aplicado
 tabla con las lecturas guardadas + "Corrección por sesgo aplicada
 a la previsión: temperatura +1,8 °C, HR −6 %, viento +0,4 m/s"

⚙️ Panel de calibración del modelo   (expander)
 [Dalton a] [Dalton b] [σ T] [σ HR] [σ viento]
 [umbral 300-340] [profundidad 5-10 cm] [minutos crecimiento 30-240]
 [↺ Restablecer valores]

──────────────────────────────────────────────────────────────────────
Fuente del modelo: «Modelo flor de sal.pdf» · Previsión: Open-Meteo ·
Simulación: Monte Carlo con corrección por sesgo.
⚠️ La predicción es una estimación probabilística, no una garantía: los
coeficientes se calibran con datos reales de campo.
```

## 🚦 Semáforo probabilístico (Márkov)

Gráfico de **áreas apiladas hora a hora** (06:00–21:00) con los 5 estados de la
capa de Márkov del PDF (pág. 8 §2), construido con `plotly go.Scatter` y
`stackgroup` (no `st.line_chart`, que no admite apilado ni anotaciones):

| Estado | Color | Significado |
|---|---|---|
| Inactivo | gris `#9E9E9E` | C por debajo del umbral |
| Concentración crítica | ámbar `#FFC107` | a <15 g/l del umbral |
| Nucleación | naranja `#FF9800` | C ≥ umbral: crecen microcristales |
| **Ventana** | verde `#2E7D32` | película cosechable |
| Degradación | rojo `#C62828` | rehidratación / cierre |

Eje Y en **%** (las cinco suman 100 % en cada hora), línea vertical punteada
**«ahora»** cuando la fecha es la de hoy, y texto guía con la hora más probable
de ventana (*p. ej. «19h: 79%»*). Es la lectura rápida de «¿a qué hora ir a la
salina?»: la franja verde que engorda marca el momento de salir con la rastrilla.

## 📆 Pestaña Temporada

Se abre con el radio **«📆 Temporada»** del menú lateral. Muestra la simulación
histórica de `scripts/season_simulation.py` (Open-Meteo Archive / ERA5, sin API
key) sobre el rango de `config.yaml` (`season.start_date → season.end_date`,
198 días de 2026-04-01 a 2026-10-15, 300 iteraciones Monte Carlo por día, sin
corrección por sesgo porque no hay lecturas de campo de esa temporada):

1. **KPIs** (`st.metric` en columnas): días simulados, **% de días con
   ventana**, **hora óptima mediana** de la temporada y **mes más productivo**.
2. **🗓️ Mapa de calor calendario** (`go.Heatmap`): Y = mes (abr…oct), X = día
   1-31, color = hora óptima con escala **YlOrRd** y barra de color en HH:MM;
   celdas de días **sin ventana** o **no simulados** en gris `#EEEEEE` y los días
   inexistentes (31 abr…) como hueco. Hover: fecha, ventana, hora óptima y
   probabilidad.
3. **📈 Probabilidad de ventana día a día** (área con `fill="tozeroy"`): de 0 a 1
   con umbral punteado al **50 %**; un día sin ventana vale 0.
4. **🕰️ Distribución de horas óptimas + cobertura por hora**: histograma con
   **bines de 30 min** y curva «en qué % de días la ventana cubre cada hora»
   (cuenta los días con `window_start ≤ h ≤ window_end`), con el pico marcado.
5. **📦 Box plot de la hora óptima por mes** (puntos dispersados, `jitter`).
6. **📊 Barras mensuales**: días con ventana vs total de días simulados, con la
   etiqueta «con ventana / total · %».
7. **🏆 Top-10 mejores días**: fecha, hora óptima, ventana y probabilidad de
   ventana (de mayor a menor).

Y en el menú lateral: **«🔄 (Re)simular temporada»**. Si la tabla `season_runs`
está vacía para el rango, la app **lo ofrece automáticamente**; el botón ejecuta
`python3 scripts/season_simulation.py` (≈15 s, `subprocess` con spinner y captura
de la salida, visible en «📤 Última salida»), limpia la caché de `st.cache_data`
y refresca la pantalla. Re-ejecutar es idempotente: la CLI reemplaza los
resultados del mismo rango.

## Desde el móvil

La interfaz es **responsive**: en escritorio usa layout ancho con columnas; en el
móvil todo se apila a una columna y se lee cómodamente.

1. Lanza la app escuchando en la red local:

   ```bash
   python3 -m streamlit run app/streamlit_app.py --server.address 0.0.0.0 --server.port 8501
   ```

2. Desde el navegador del móvil (misma Wi‑Fi que el PC) abre
   `http://IP-del-PC:8501`. Streamlit muestra la IP en la consola al arrancar
   (*Network URL*).

3. **Si el PC trabaja en WSL2** (como este proyecto, en `/mnt/c/...`): Windows
   reenvía `localhost` a WSL automáticamente, pero para llegar desde el móvil usa la
   **IP de Windows** y abre el puerto en el firewall:

   ```powershell
   netsh advfirewall firewall add rule name="Streamlit 8501" dir=in action=allow protocol=TCP localport=8501
   ```

4. Con la página abierta, elige **«Añadir a pantalla de inicio»** del navegador: queda
   como una app con icono propio, lista para registrar lecturas en la salina.

> Consejo: el formulario guarda la hora del momento; ajústala con `time_input` si
> transcribes lecturas al final del día. Cada guardado recalcula el veredicto.

## Tests

```bash
python3 -m pytest tests/ -q
```

Los tests cubren física, Monte Carlo, asimilación, previsión, base de datos
(fixtures con el día típico de Córdoba del PDF) y la UI: `tests/test_app.py`
ejecuta el punto de entrada real con `streamlit.testing.v1.AppTest` y comprueba
que **Hoy** y **Temporada** se pintan sin excepciones, usando una base de datos
temporal (`FLOR_DESAL_DB`) y con la red bloqueada.

```bash
python3 -m pytest tests/ -m "not integration"   # sin pruebas que piden red
```

## Estructura del proyecto

```
flor-de-sal/
├── AGENTS.md               # memoria del proyecto (modelo, decisiones, convenciones)
├── README.md               # este archivo
├── config.yaml             # constantes de la salina y del modelo (calibrables)
│                           #   sección season: rango e iteraciones de la temporada
├── requirements.txt
├── .streamlit/config.toml  # tema (verde/teal #00695C) y servidor
├── app/
│   ├── streamlit_app.py    # punto de entrada delgado: set_page_config + main()
│   │                       #   (sigue siendo el fichero de `streamlit run`)
│   ├── assets/logo.png     # logo de la salina (favicon de la pestaña y cabecera)
│   └── ui/                 # paquete con toda la interfaz:
│       ├── constantes.py   #   colores, estados de Márkov, calibración, layout plotly
│       ├── textos.py       #   textos compartidos en español (pie, leyenda, avisos)
│       ├── helpers.py      #   formatos, estilos de tabla, gráficos y zona horaria
│       ├── state.py        #   caché (Monte Carlo del día / season_runs) + session_state
│       ├── sidebar.py      #   menú lateral: navegación, fecha, descarga, simulación
│       ├── panel_hoy.py    #   sección 🌞 Hoy (veredicto, semáforo, campana, tabla…)
│       ├── panel_temporada.py  # sección 📆 Temporada (KPIs y gráficas)
│       └── main.py         #   cabecera, sección elegida y pie de fuentes
├── src/
│   ├── config.py           # carga de config.yaml
│   ├── weather.py          # previsión horaria (Open-Meteo)
│   ├── historical.py       # meteorología observada (Open-Meteo Archive / ERA5)
│   ├── db.py               # SQLite local (previsión, lecturas, predicciones,
│   │                       #   season_runs)
│   ├── physics.py          # evaporación, T del agua, concentración y fases
│   ├── montecarlo.py       # 1000 escenarios → distribución de la hora óptima
│   ├── markov.py           # cadena de Márkov → curva de estados por hora
│   ├── assimilation.py     # corrección por sesgo (real − previsto)
│   ├── alerts.py           # semáforo de fases y alertas
│   └── pipeline.py         # run_daily / recalc_with_field_data → veredicto
├── scripts/
│   ├── init_db.py          # crea el esquema de la DB
│   ├── ingest_forecast.py  # descarga y guarda la previsión del día
│   └── season_simulation.py# simula la temporada y guarda en season_runs
├── tests/                  # pytest (física, Monte Carlo, DB, temporada y
│                           #   humo de la UI con streamlit AppTest)
└── data/flor_desal.db      # SQLite local (se crea sola; no se versiona)
```

## Notas

- **Base de datos**: `data/flor_desal.db` es la fuente de verdad del PC (previsión,
  lecturas de campo y veredictos históricos). No se versiona (`.gitignore`).
  Para apuntar la app a otra DB (pruebas), define la variable de entorno
  `FLOR_DESAL_DB=/ruta/otra.db`; si no, se usa la del proyecto.
- **Rendimiento**: el veredicto se cachea 5 min (`st.cache_data`) y se invalida solo
  al guardar una lectura, cambiar la calibración o descargar previsión nueva
  (la clave ya no incluye la hora del sistema: el `ttl=300` refresca la fase a
  mitad de día sin recalcular la campana cada hora).
- **Zona horaria**: la «línea ahora» del semáforo, la fecha por defecto del
  selector y la hora de las lecturas usan `location.timezone` de `config.yaml`
  (con *fallback* a la hora local si la zona no existe en el equipo).
- **Unidades**: presión en hPa (se pasa a kPa a Dalton), evaporación en mm (= L/m²),
  viento m/s, concentración g/l, temperatura °C.
