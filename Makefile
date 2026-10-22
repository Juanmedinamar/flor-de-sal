# Flor de Sal — Makefile
# Targets de desarrollo, testing, calidad, Docker y operativa.
# Uso: make <target>

.PHONY: init test test-all cov lint fmt type run season ingest db-init health backup \
        docker-build docker-up docker-down docker-logs help

# Variables
PY := python3
PIP := $(PY) -m pip
POETRY := poetry
STREAMLIT := streamlit
PYTEST := pytest
RUFF := ruff
MYPY := mypy

# ----------------------------------------------------------------------
# Instalación y entorno
# ----------------------------------------------------------------------
init: ## Instala el paquete en modo editable con dependencias de desarrollo
	$(PIP) install -e ".[dev]"

# ----------------------------------------------------------------------
# Testing y cobertura
# ----------------------------------------------------------------------
test: ## Tests rápidos (excluye integración)
	$(PYTEST) -m "not integration" -q

test-all: ## Todos los tests (incluye integración)
	$(PYTEST) -q

cov: ## Cobertura (excluye integración) con reporte de líneas faltantes
	$(PYTEST) --cov=src --cov-report=term-missing -m "not integration"

# ----------------------------------------------------------------------
# Calidad de código
# ----------------------------------------------------------------------
lint: ## Lint estático con ruff (src/, tests/, scripts/, app/)
	$(RUFF) check src/ tests/ scripts/ app/

fmt: ## Formatea y corrige con ruff (fix + unsafe-fixes)
	$(RUFF) check --fix --unsafe-fixes src/ tests/ scripts/ app/

type: ## Comprobación de tipos con mypy (src/)
	$(MYPY) src/

# ----------------------------------------------------------------------
# Ejecución de la app y scripts CLI
# ----------------------------------------------------------------------
run: ## Lanza la app Streamlit en modo desarrollo
	$(STREAMLIT) run app/streamlit_app.py

season: ## Simula la temporada histórica (opcional: START, END, ITERS, WORKERS)
	$(PY) scripts/season_simulation.py $(if $(START),--start $(START)) $(if $(END),--end $(END)) $(if $(ITERS),--iters $(ITERS)) $(if $(WORKERS),--workers $(WORKERS))

ingest: ## Descarga y guarda la previsión del día (opcional: DATE=YYYY-MM-DD)
	$(PY) scripts/ingest_forecast.py $(if $(DATE),$(DATE))

db-init: ## Inicializa el esquema de la base de datos
	$(PY) scripts/init_db.py

health: ## Healthcheck de la app (HTTP GET /_stcore/health)
	$(PY) scripts/healthcheck.py

backup: ## Backup de la BD (opcional: KEEP=N para conservar solo N backups)
	$(PY) scripts/backup_db.py $(if $(KEEP),--keep $(KEEP))

# ----------------------------------------------------------------------
# Docker
# ----------------------------------------------------------------------
docker-build: ## Construye la imagen Docker (multi-stage)
	docker build -t flor-de-sal .

docker-up: ## Levanta la app con docker-compose (dev + prod override)
	docker compose up -d

docker-down: ## Para y elimina contenedores docker-compose
	docker compose down

docker-logs: ## Sigue los logs del contenedor app
	docker compose logs -f app

# ----------------------------------------------------------------------
# Ayuda
# ----------------------------------------------------------------------
help: ## Muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

# Default
.DEFAULT_GOAL := help