# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es/1.0.0/),
y el proyecto usa [Semantic Versioning](https://semver.org/lang/es/).

## [Unreleased]

### Añadido
- Configuración estricta de mypy (progresiva módulo a módulo) para Ola 3
- Objetivo de cobertura ≥85% (actual ≥80%)
- Más property-based tests con Hypothesis (física, Monte Carlo, asimilación)

### Cambiado
- (pendiente) `disallow_untyped_defs = true` módulo a módulo en `pyproject.toml`

### Corregido
- (pendiente) Limpieza de `type: ignore` temporales

## [0.3.0] - 2026-10-21

### Añadido — Ola 1 (Modelo físico + Monte Carlo + Márkov + Pipeline + UI)
- **G2** `src/physics.py`: evaporación (Dalton), T_agua, concentración, fases, umbral
- **G3** `src/montecarlo.py`: 1000 escenarios vectorizados, hora óptima, IC 95%, probabilidades
- **G4** `src/markov.py`: 5 estados (inactivo, concentración_critica, nucleación, ventana, degradación), matriz de transición hora→hora, curva P(estado|hora)
- **G5** `src/weather.py`: cliente Open-Meteo con reintentos, backoff exponencial, timeout, Archive (ERA5)
- **G6** `src/historical.py`: iteración días ERA5, calidad de datos, fetch_archive
- **G7** `src/assimilation.py`: bias rolling (real − previsto), aplicación a previsión, max_hours_back configurable
- **G8** `src/pipeline.py`: run_daily / recalc_with_field_data, un solo ensemble MC+Márkov, zona horaria salina

### Añadido — Ola 1 (Base de datos + Scripts CLI)
- **M1** `src/db.py`: SQLite local, esquema (forecast, readings, predictions, season_runs), migraciones idempotentes
- **M2** `scripts/init_db.py`: crea esquema, idempotente
- **M3** `scripts/ingest_forecast.py`: descarga previsión día (hoy o fecha), guarda en DB, resumen por horas
- **M4** `scripts/season_simulation.py`: simula rango config.yaml (ERA5), ProcessPoolExecutor (forkserver), degrada a serie, determinismo semilla
- **M5** `src/config.py`: carga config.yaml tipada (Config TypedDict), validación, defaults
- **M6** `src/alerts.py`: evaluación de riesgos (viento, HR, temperatura), descripciones de fase
- **M7** `src/errors.py`: jerarquía de excepciones (ForecastError, DBError, ConfigError, SimulationError)
- **M8** `config.yaml`: todas las constantes calibrables (ubicación, agua, física, simulación, MC, límites, asimilación, red, temporada, Márkov)
- **M9** Zona horaria de la salina en veredictos (Europe/Madrid), fallback a local

### Añadido — Ola 1 (UI Streamlit)
- `app/streamlit_app.py`: entrypoint delgado, set_page_config, main()
- `app/ui/`: paquete modular (constantes, textos, helpers, state, sidebar, panel_hoy, panel_temporada, main)
- **Sección 🌞 Hoy**: veredicto (fase, ventana, hora óptima IC95, prob ventana/riesgo), semáforo probabilístico (áreas apiladas Plotly), campana de probabilidad, previsión vs lecturas, evolución predicción, tabla horaria, formulario datos reales, panel calibración
- **Sección 📆 Temporada**: KPIs, mapa calor calendario, prob. ventana día a día, distribución horas óptimas + cobertura, boxplot por mes, barras mensuales, top-10 mejores días, botón (Re)simular
- Responsive (móvil/escritorio), tema verde/teal (#00695C), logo salina
- Cacheo 5 min (st.cache_data), invalidación al guardar lectura / cambiar calibración / descargar previsión

### Añadido — Ola 1 (Tests)
- Tests unitarios: física, Monte Carlo, asimilación, weather, DB, Márkov, histórico, pipeline, temporada
- Test de humo UI: `tests/test_app.py` con `streamlit.testing.v1.AppTest`, DB temporal, red bloqueada
- Fixtures: día típico verano Córdoba (PDF) para validación end-to-end

### Cambiado
- v0.2.0 → v0.3.0: versión mayor porFeatures completas del modelo (física, MC, Márkov, UI, CLI, tests)

## [0.2.0] - 2026-10-15

### Añadido — Baseline (commit e591a64)
- Estructura base del proyecto: `src/`, `app/`, `scripts/`, `tests/`, `config.yaml`
- `pyproject.toml` con ruff, mypy, pytest, dependencias
- `requirements.txt` (runtime)
- `.streamlit/config.toml` (tema, servidor)
- `AGENTS.md` (memoria del proyecto, modelo físico, decisiones, mapa de propiedad)
- `README.md` (instalación, uso, estructura, capturas lógicas)
- `.gitignore` (Python, data/*.db, Streamlit secrets, cachés)

### Cambiado
- Configuración inicial de calidad (ruff line-length=100, mypy progresivo, pytest markers)

---

## Convenciones de versiones

- **MAJOR** (X.0.0): cambios incompatibles en API pública, modelo o esquema DB
- **MINOR** (0.X.0): nuevas funcionalidades compatibles (nueva sección UI, nuevo script, nueva métrica)
- **PATCH** (0.0.X): correcciones de bugs, ajustes de calibración, docs, CI, deps

## Referencias

- Commit baseline v0.2.0: `e591a64`
- Commit Ola 1 completa v0.3.0: `584ec79`
- Modelo físico de referencia: `Modelo flor de sal.pdf` (10 págs)
- Memoria técnica: `AGENTS.md`