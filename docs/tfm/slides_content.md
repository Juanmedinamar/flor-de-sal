# 🧂 Flor de Sal — TFM Big School (mouredev)

## Contenido para Slides (copia/pega a Google Slides / Canva / PowerPoint)

---

### Slide 1: Portada
**Título:** Flor de Sal — Predictor probabilístico de recolección óptima
**Subtítulo:** TFM — Máster Desarrollo de Software con IA (Big School / mouredev)
**Autor:** Juan Medina
**Fecha:** 2026
**Enlace repo:** `https://github.com/TU_USUARIO/flor-de-sal`
**Despliegue:** `https://salina.tudominio.com`

---

### Slide 2: Problema real
**Contexto:** Salinas de interior (Córdoba) — flor de sal = capa fina en superficie
- **Valor:** 10-20× sal común
- **Problema:** Ventana de recolección = 2-4 h/día, depende de Tª, HR, viento, radiación
- **Riesgo:** Viento > 5,5 m/s → hunde la película; HR > 65 % → rehidratación
- **Actual:** Decisión empírica ("ojímetro") → pérdidas por cosecha temprana/tardía

---

### Slide 3: Solución propuesta
**App web (Streamlit) que predice con probabilidad la ventana óptima**
- **Entrada 1:** Previsión Open-Meteo (gratis, sin API key, horaria 7 días)
- **Entrada 2:** Lecturas reales de campo (Tª calentador/cristalizador, conc. g/l, T/HR/V medidos)
- **Motor:** Modelo físico + Monte Carlo (1000 escenarios) + Markov + Asimilación (bias correction)
- **Salida:** Semáforo, ventana probable, hora óptima ± IC95%, prob. ventana/riesgo, alertas

---

### Slide 4: Modelo físico (resumen)
- **Evaporación:** Ley de Dalton modificada `E = (a + b·V) · VPD` (kPa) / 24
- **Tª agua:** `T_agua = T_aire + coef_solar·(rad/1000) + extra_mañana`
- **Concentración:** Balance de masa `C_t = C0 / (1 - ΣE/h)` (h = profundidad mm)
- **Umbral:** `Umbral = 318 + 0.5·(T_agua - 25)` [g/l] (rango 315-320)
- **Fases:** 0 Inactividad → 1 Nucleación → 2 Ventana → 3 Cierre/Riesgo
- **Cierre:** Viento > 5.5 m/s ∨ HR > 65% ∨ repunte HR > 45% tras mínimo

---

### Slide 5: Monte Carlo vectorizado (1000 escenarios < 0.1 s)
- **Muestreo:** T ~ N(T_prev, σ_T), HR ~ N(HR_prev, σ_HR) trunc [5,99], V ~ N(V_prev, σ_V) trunc [0,∞)
- **Física vectorizada:** NumPy broadcasting (sin bucles Python) → T_agua, VPD, E, C_t, Umbral
- **Fases por escenario:** Nucleación → Ventana (min_crecimiento) → Cierre
- **Hora óptima/escenario:** Centro de la ventana (apertura + 0.5·duración)
- **Agregación:** Mediana + IC 95% (P5/P95), Prob(ventana), Prob(riesgo), Semáforo Markov

---

### Slide 6: Asimilación de datos (Bias Correction)
- **Problema:** Pronóstico ≠ Realidad (sesgo sistemático)
- **Solución:** Rolling bias sobre últimas N horas con lecturas reales
  ```
  bias_T = mean(T_real - T_previsto) últimas N hrs
  bias_HR = mean(HR_real - HR_previsto)
  bias_V  = mean(V_real - V_previsto)
  ```
- **Aplicación:** Pronóstico corregido = Pronóstico + bias → Monte Carlo sobre corregido
- **Resultado:** Campana se estrecha, IC95% se reduce, veredicto más fiable
- **Configurable:** `assimilation.max_hours_back` (default 6h)

---

### Slide 7: Cadena de Markov (semáforo probabilístico)
- **5 estados:** Inactivo, Concentración crítica (<15 g/l del umbral), Nucleación, Ventana, Degradación
- **Matriz de transición:** Estimada por frecuencias del ensemble Monte Carlo (coherente por construcción)
- **Propagación:** π(h+1) = π(h) · T(h) → curva P(estado | hora) instantánea
- **Visualización:** Áreas apiladas hora a hora (06-21h), línea vertical "ahora", guía "¿a qué hora ir?"

---

### Slide 8: Arquitectura software (Clean Architecture)
```
┌─────────────────────────────────────────────────────┐
│                    UI (Streamlit)                   │
│  Hoy | Temporada | Sidebar | Calibración | Slides  │
├─────────────────────────────────────────────────────┤
│                 Pipeline (caso de uso)              │
│  run_daily() → veredicto + curva Markov + hist      │
├─────────────────────────────────────────────────────┤
│  Dominio (sin deps externas)                        │
│  Physics | MonteCarlo | Markov | Assimilation      │
│  Alerts  | Config (Protocol) | Errors               │
├─────────────────────────────────────────────────────┤
│              Infraestructura                        │
│  Weather (Open-Meteo) | Historical (ERA5)           │
│  DB (SQLite WAL) | Logging JSON | Scheduler        │
└─────────────────────────────────────────────────────┘
```

---

### Slide 9: Calidad y Testing (pirámide)
- **Unit tests:** 179 tests (física, MC, Markov, DB, pipeline, asimilación)
- **Property-based (Hypothesis):** 21 tests invariantes físicas (psat>0, VPD≥0, C≥C0, umbral≈318+0.5ΔT)
- **Architecture tests (AST):** 18 tests → Dominio NO importa Infra (Weather, DB, Streamlit)
- **UI tests (AppTest):** 3 tests → Hoy + Temporada + Calibración sin excepciones
- **Coverage:** 95% src/ (meta ≥80%)
- **Lint/Type:** ruff (strict), mypy strict (src/), pre-commit hooks
- **CI/CD:** GitHub Actions (lint, type, test cov≥80%, app-smoke 30s)

---

### Slide 10: Despliegue y Operativa (DevOps)
- **Docker multi-stage:** builder → runtime (non-root, 8501, healthcheck)
- **Reverse proxy:** nginx + Let's Encrypt (HTTPS automático, renovación auto)
- **Docker Compose:** dev + prod override, volúmenes data/backups
- **Logging:** JSON lines (stdout + RotatingFileHandler 5MB/3)
- **Healthcheck:** `GET /_stcore/health` (Docker + k8s ready)
- **Backup:** `sqlite3 backup` online → backups/flor_desal_YYYYMMDD_HHMMSS.db (cron --keep N)
- **CI/CD:** GitHub Actions (lint, type, test cov≥80%, app-smoke 30s, artifacts)
- **Dependabot:** Weekly pip + github-actions

---

### Slide 11: Validación y Resultados (Temporada 2026)
- **Simulación histórica:** 198 días (2026-04-01 → 2026-10-15), ERA5, 300 it/día
- **Resultados:** 92% días con ventana, hora óptima mediana 19:00
- **Distribución óptima:** 16h:5 / 17h:11 / 18h:36 / 19h:89 / 20h:42
- **Coherencia MC↔Markov:** desviación 1.6e-10 (idéntico por construcción)
- **Validación día típico PDF:** 06h:18°C/85%/0.5 → 14h nucleación → ventana 16-20h → óptima 17:45 (PDF: cosecha 16-19h)

---

### Slide 12: Integración estación meteorológica real
- **Hardware:** Davis Vantage Vue + Meteobridge Pro2 (a 500 m)
- **Datos automáticos:** HTTP POST cada 5 min → endpoint FastAPI → BD
- **Variables:** Tª aire, HR, viento, radiación, lluvia
- **Lecturas manuales:** Formulario en app (Tª calentador/cristalizador, conc. g/l)
- **Bias correction:** Combina auto (estación) + manual (proceso) → veredicto calibrado

---

### Slide 13: Multi-zona (escalabilidad futura)
- **Actual:** 1 zona (Córdoba), 1 balsa + 13 cristalizadores
- **Próximo:** Zona B (nueva balsa + N cristalizadores)
- **Arquitectura preparada:** `zone_id` en BD, config por zona, selector UI
- **Escalable:** `crystallizers` table (hereda de zona, overrides puntuales)

---

### Slide 14: Métricas de calidad (resumen)
| Métrica | Valor |
|---------|-------|
| **Tests totales** | 179 (unit + property + arch + UI) |
| **Cobertura src/** | 95% (meta ≥80%) |
| **mypy strict (src/)** | 0 errores |
| **ruff** | 0 warnings |
| **Tiempo MC (1000 it)** | < 0.1 s |
| **Simulación temporada (198 días)** | ~15 s (paralelo forkserver) |
| **Tamaño imagen Docker** | ~200 MB (multi-stage) |
| **Healthcheck** | < 10 s |

---

### Slide 15: Conclusiones y Trabajo Futuro
**Logros:**
- App real, desplegada, probada, documentada
- Modelo físico fiel al PDF + estocástico riguroso
- Arquitectura limpia, testeable, desplegable
- Calidad profesional (CI/CD, lint, type, coverage, logging, backup)

**Trabajo futuro:**
- Multi-zona / multi-cristalizador (selector UI, herencia params)
- ML para calibración automática de coeficientes (Bayesian optimization)
- App móvil nativa (PWA / React Native) + push notifications
- Integración LoRaWAN para sensores remotos en cristalizadores
- Exportación PDF/Excel de informes diarios/temporada

---

### Slide 16: Cierre / Contacto
**Flor de Sal — Predictor probabilístico de recolección óptima**

**Repo:** `https://github.com/TU_USUARIO/flor-de-sal`  
**Despliegue:** `https://salina.tudominio.com`  
**Email:** juanmedina@users.noreply.github.com  
**TFM — Máster Desarrollo de Software con IA (Big School / mouredev)**

---

## Instrucciones rápidas para Slides
1. Abre **Google Slides** (gratis) / **Canva** / **PowerPoint**
2. Crea 16 slides en blanco
3. Copia cada bloque "### Slide X" → una slide
3. Ajusta fuentes, colores (teal #00695C), añade capturas de pantalla de la app
4. En Slide 1: pon tu nombre, email, enlace repo real, URL despliegue real
5. Exporta a PDF para entrega + comparte enlace editable si piden