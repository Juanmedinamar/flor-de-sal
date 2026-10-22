# Flor de Sal — Dockerfile multi-stage (builder → runtime)
# Build:     docker build -t flor-de-sal .
# Run:       docker run -d -p 8501:8501 -v ./data:/app/data --env-file .env flor-de-sal

# ----------------------------------------------------------------------
# Stage 1: Builder — instala dependencias en entorno aislado
# ----------------------------------------------------------------------
FROM python:3.13-slim AS builder

# Evita prompts interactivos y bytecode .pyc
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Dependencias de sistema para compilar (si las hubiera) + tzdata para ZoneInfo
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Directorio de trabajo
WORKDIR /app

# Copia solo archivos de dependencias para aprovechar caché de capas
COPY pyproject.toml requirements.txt ./

# Instala el paquete en modo editable (incluye deps de runtime)
# --no-deps porque ya están en requirements.txt; -e para que el código sea importable
RUN pip install --no-cache-dir -e .

# ----------------------------------------------------------------------
# Stage 2: Runtime — imagen mínima para producción
# ----------------------------------------------------------------------
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Streamlit config por variables de entorno
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Dependencias de runtime: sqlite3 (ya en base), tzdata (ZoneInfo), ca-certificates
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Usuario no-root para seguridad
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# Copia paquetes instalados desde builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copia código de la aplicación
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser scripts/ ./scripts/
COPY --chown=appuser:appuser config.yaml ./
COPY --chown=appuser:appuser pyproject.toml ./

# Crea directorio de datos y backups con permisos correctos
RUN mkdir -p /app/data /app/backups && chown -R appuser:appuser /app/data /app/backups

# Cambia a usuario no-root
USER appuser

# Expone el puerto de Streamlit
EXPOSE 8501

# Healthcheck: usa el script de healthcheck (HTTP GET /_stcore/health)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python3 scripts/healthcheck.py

# Comando por defecto: lanza Streamlit en modo headless
CMD ["streamlit", "run", "app/streamlit_app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]