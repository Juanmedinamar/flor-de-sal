# ✅ Checklist Final TFM Big School (mouredev)

**Fecha límite:** 23/02 (consultar temario exacto)
**Entrega:** Formulario en lección "Proyecto Final" → Nombre, Email, URL código, URL despliegue, URL slides

---

## 📦 Código (obligatorio)
- [ ] **Repo público GitHub** (mejor valorado) → `https://github.com/TU_USUARIO/flor-de-sal`
  - [ ] Repo público (no privado)
  - [ ] `README.md` completo en raíz
  - [ ] Código en `main` branch
  - [ ] `.gitignore` correcto (excluye `data/`, `backups/`, `__pycache__`, `.env`, `*.db`)
  - [ ] Licencia MIT (`LICENSE` en raíz)
  - [ ] `.env.example` documentado
  - [ ] `deploy.sh` ejecutable
- [ ] **Commits** con historial limpio (convencional commits si es posible)
- [ ] **Tag** `v1.0.0-tfm` en el commit de entrega

---

## 📖 Documentación (README.md)
- [ ] **Descripción general** del proyecto (qué hace, para quién, valor)
- [ ] **Stack tecnológico** (tabla clara: frontend, backend, DB, ML, DevOps, etc.)
- [ ] **Instalación** (pasos claros: `pip install`, `init_db`, `streamlit run`)
- [ ] **Estructura del proyecto** (árbol de directorios comentado)
- [ ] **Funcionalidades principales** (Hoy, Temporada, calibración, cosecha, bias, etc.)
- [ ] **Despliegue** (Docker, VPS, nginx, HTTPS, URL pública real)
- [ ] **Capturas / ASCII art** del UI (panel Hoy, Temporada, formulario)
- [ ] **Licencia** (MIT) + autor + email
- [ ] **Badges** actualizados (CI, coverage 95%, Python 3.13, MIT, Docker, Streamlit)

---

## 🌐 Despliegue funcionando (recomendado siempre)
- [ ] **URL pública HTTPS** → `https://salina.tudominio.com`
- [ ] **Healthcheck** responde 200: `curl -I https://salina.tudominio.com/_stcore/health`
- [ ] **HTTPS válido** (Let's Encrypt, certificado vigente)
- [ ] **App carga** en móvil y desktop (responsive)
- [ ] **Funcionalidad completa:** Hoy (veredicto, campana, semáforo, formulario), Temporada (KPIs, mapa, gráficas), Calibración, Cosecha
- [ ] **Logs** visibles (`docker compose logs -f app`)
- [ ] **Backup** funcionando (`python3 scripts/backup_db.py --keep 10`)

---

## 🎞 Slides (presentación)
- [ ] **16 slides** (portada, problema, solución, modelo, MC, bias, Markov, arquitectura, testing, despliegue, validación, estación real, multi-zona, métricas, conclusiones, cierre)
- [ ] Formato: **Google Slides** (compartir enlace editable) / **Canva** / **PowerPoint** / PDF
- [ ] **Enlace accesible** (cualquiera con enlace puede ver)
- [ ] En el formulario de entrega → pegar **URL slides**

---

## 🧪 Tests y Calidad (para ti, no se entregan pero evalúan)
- [ ] `make test` → 179 tests pass (sin integración)
- [ ] `make cov` → coverage ≥ 95% src/
- [ ] `make type` → mypy strict 0 errores en src/
- [ ] `make lint` → ruff 0 warnings
- [ ] `make fmt` → idempotente (2 pasadas sin cambios)
- [ ] `python3 -m pytest tests/test_app.py` → AppTest Hoy + Temporada sin excepciones

---

## 📦 Entrega en formulario (23/02)
Campos a rellenar:
- [ ] **Nombre completo** (igual que matrícula)
- [ ] **Email** (el de inscripción al máster)
- [ ] **URL al código** → `https://github.com/TU_USUARIO/flor-de-sal`
- [ ] **URL despliegue** → `https://salina.tudominio.com`
- [ ] **URL slides** → `https://docs.google.com/presentation/d/...` (o Canva/PPT)

---

## 📋 Última revisión antes de enviar
- [ ] Repo público clonado en máquina limpia → `make init && make test` → todo verde
- [ ] Despliegue en VPS limpio → `./deploy.sh` → `https://salina.tudominio.com` carga
- [ ] README.md se ve bien en GitHub (renderizado, badges, imágenes)
- [ ] Slides se ven bien en Google Slides (fuentes, colores, capturas legibles)
- [ ] Formulario rellenado y enviado antes de 23/02 23:59
- [ ] Confirmación de envío guardada (captura pantalla / email)

---

## 📞 Contacto / Soporte
- **Email entrega:** el de inscripción al máster
- **Tutor:** (si tienes asignado, pon su nombre)
- **Dudas técnicas:** juanmedina@users.noreply.github.com

---

> **Nota:** Big School valora **proyecto real, código limpio, despliegue real, buena documentación**. Tu proyecto ya tiene todo: modelo físico riguroso, Monte Carlo + Markov + bias correction, arquitectura limpia, testing exhaustivo, CI/CD, Docker, logging, backup, multi-zona preparado. Solo falta: **subir a GitHub público, desplegar en VPS real, hacer slides, enviar formulario**.

¡Mucho ánimo! 🚀