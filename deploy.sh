#!/usr/bin/env bash
# deploy.sh — Despliegue automático Flor de Sal en VPS (Ubuntu 24.04)
# Uso: ./deploy.sh   (ejecuta como root o con sudo)

set -euo pipefail

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() { echo -e "${GREEN}[DEPLOY]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ─── Comprobaciones previas ───
[[ $EUID -eq 0 ]] || err "Ejecuta como root (sudo ./deploy.sh)"

# ─── Variables (edita si cambias) ───
REPO_URL="https://github.com/TU_USUARIO/flor-de-sal.git"
APP_DIR="/opt/flor-de-sal"
DOMAIN="${DOMAIN:-salina.tudominio.com}"
EMAIL_LETSENCRYPT="${EMAIL_LETSENCRYPT:-admin@tudominio.com}"

log "=== Flor de Sal — Despliegue automático ==="
log "Directorio: $APP_DIR"
log "Dominio: $DOMAIN"

# ─── 1. Actualiza sistema e instala dependencias base ───
log "Actualizando sistema e instalando Docker..."
apt-get update -qq
apt-get install -y -qq ca-certificates curl gnupg lsb-release git

# ─── 2. Instala Docker (oficial) ───
if ! command -v docker &>/dev/null; then
    log "Instalando Docker Engine..."
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
else
    log "Docker ya instalado"
fi

# ─── 3. Clona/actualiza repo ───
if [[ -d "$APP_DIR/.git" ]]; then
    log "Repo ya existe → pull"
    cd "$APP_DIR"
    git pull --ff-only
else
    log "Clonando repo..."
    git clone "$REPO_URL" "$APP_DIR"
    cd "$APP_DIR"
fi

# ─── 4. Configura .env ───
if [[ ! -f .env ]]; then
    log "Creando .env desde .env.example..."
    cp .env.example .env
    # Sustituye placeholders si hay variables de entorno
    sed -i "s|salina.tudominio.com|$DOMAIN|g" .env
    sed -i "s|tu-email@tudominio.com|$EMAIL_LETSENCRYPT|g" .env
    warn "Revisa .env y ajusta DOMAIN/EMAIL_LETSENCRYPT si hace falta"
else
    log ".env ya existe"
fi

# ─── 5. Crea directorios de datos/backups/logs ───
mkdir -p data backups logs
chown -R 1000:1000 data backups logs  # usuario no-root en contenedor (uid 1000)

# ─── 6. Genera docker-compose.override.yml para producción ───
cat > docker-compose.override.yml <<'EOF'
services:
  app:
    build:
      context: .
      target: runtime
    env_file: .env
    volumes:
      - ./data:/app/data
      - ./backups:/app/backups
      - ./logs:/app/logs
    environment:
      - FLOR_DESAL_DB=/app/data/flor_desal.db
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python3", "scripts/healthcheck.py"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx:/etc/nginx/conf.d:ro
      - ./certbot/conf:/etc/letsencrypt:ro
      - ./certbot/www:/var/www/certbot:ro
    depends_on:
      - app
    restart: unless-stopped

  certbot:
    image: certbot/certbot
    volumes:
      - ./certbot/conf:/etc/letsencrypt
      - ./certbot/www:/var/www/certbot
    entrypoint: "/bin/sh -c 'trap exit TERM; while :; do certbot renew --quiet --nginx; sleep 12h & wait $${!}; done'"
EOF

# ─── 7. Configura nginx (snippet para streamlit + websocket) ───
mkdir -p nginx certbot/conf certbot/www
cat > nginx/flor-de-sal.conf <<'EOF'
server {
    listen 80;
    server_name ${DOMAIN};
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name ${DOMAIN};

    ssl_certificate /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;

    # Seguridad
    add_header X-Frame-Options "SAMEORIGIN";
    add_header X-Content-Type-Options "nosniff";
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://app:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
        proxy_buffering off;
    }
}
EOF

# Sustituye ${DOMAIN} en la config de nginx
sed -i "s/\${DOMAIN}/$DOMAIN/g" nginx/flor-de-sal.conf

# ─── 8. Pide certificado Let's Encrypt (solo primera vez) ───
if [[ ! -d "certbot/conf/live/$DOMAIN" ]]; then
    log "Solicitando certificado Let's Encrypt para $DOMAIN..."
    docker compose run --rm certbot certonly --webroot -w /var/www/certbot \
        --email "$EMAIL_LETSENCRYPT" --agree-tos --no-eff-email -d "$DOMAIN"
else
    log "Certificado ya existe"
fi

# ─── 9. Levanta servicios ───
log "Levantando contenedores..."
docker compose up -d --build

# ─── 10. Inicializa BD (si no existe) ───
log "Inicializando base de datos..."
docker compose exec -T app python3 scripts/init_db.py || true

# ─── 11. Verificación final ───
sleep 5
if curl -sf "http://localhost/_stcore/health" >/dev/null; then
    log "✅ Healthcheck OK (HTTP)"
else
    warn "Healthcheck HTTP falló (puede tardar unos segundos más)"
fi

if curl -sf "https://$DOMAIN/_stcore/health" >/dev/null 2>&1; then
    log "✅ HTTPS OK en https://$DOMAIN"
else
    warn "HTTPS aún no responde (DNS/propagación/certificado). Revisa:"
    warn "  - DNS A $DOMAIN → IP de este VPS"
    warn "  - Puertos 80/443 abiertos en firewall/cloud"
    warn "  - Logs: docker compose logs nginx certbot"
fi

log "=== Despliegue completado ==="
log "App: https://$DOMAIN"
log "Logs: docker compose logs -f app"
log "Backup: ./backup.sh (o cron)"
log "Actualizar: cd $APP_DIR && git pull && ./deploy.sh"