#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

BLUE='\033[0;34m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() {
    printf '%b\n' "${CYAN}[$(date +%H:%M:%S)]${NC} $*"
}

ok() {
    printf '%b\n' "${GREEN}OK${NC} $*"
}

warn() {
    printf '%b\n' "${YELLOW}WARN${NC} $*"
}

fail() {
    printf '%b\n' "${RED}ERROR${NC} $*" >&2
    exit 1
}

have_cmd() {
    command -v "$1" >/dev/null 2>&1
}

run_privileged() {
    if [[ "${EUID}" -eq 0 ]]; then
        "$@"
    elif have_cmd sudo; then
        sudo "$@"
    else
        fail "Hace falta privilegio de administrador para ejecutar: $*"
    fi
}

apt_install_if_missing() {
    local missing=()
    local package
    for package in "$@"; do
        if ! dpkg -s "$package" >/dev/null 2>&1; then
            missing+=("$package")
        fi
    done

    if ((${#missing[@]} == 0)); then
        return 0
    fi

    log "Instalando paquetes del sistema: ${missing[*]}"
    run_privileged apt-get update
    DEBIAN_FRONTEND=noninteractive run_privileged apt-get install -y "${missing[@]}"
}

ensure_node_dependencies() {
    if [[ ! -f "$ROOT_DIR/frontend/package.json" ]]; then
        return 0
    fi

    if ! have_cmd node || ! have_cmd npm; then
        log "Instalando Node.js y npm para el frontend"
        apt_install_if_missing nodejs npm
    fi

    log "Instalando dependencias npm del frontend"
    (
        cd "$ROOT_DIR/frontend"
        npm install
    )
    ok "Dependencias del frontend listas"
}

ensure_docker_available() {
    if have_cmd docker && docker compose version >/dev/null 2>&1; then
        ok "Docker y Docker Compose ya están disponibles"
        return 0
    fi

    if ! have_cmd apt-get; then
        fail "No se puede instalar Docker automáticamente en esta distribución"
    fi

    log "Instalando Docker"
    apt_install_if_missing docker.io

    if ! docker compose version >/dev/null 2>&1; then
        if apt-cache show docker-compose-v2 >/dev/null 2>&1; then
            apt_install_if_missing docker-compose-v2
        else
            apt_install_if_missing docker-compose-plugin
        fi
    fi

    run_privileged usermod -aG docker "$USER" || true

    if have_cmd systemctl; then
        run_privileged systemctl enable docker >/dev/null 2>&1 || true
        run_privileged systemctl start docker >/dev/null 2>&1 || true
    fi

    have_cmd docker || fail "Docker no quedó instalado correctamente"
    docker compose version >/dev/null 2>&1 || fail "Docker Compose no quedó instalado correctamente"
    ok "Docker listo"
}

ensure_python_environment() {
    log "Verificando dependencias base de Python"
    apt_install_if_missing python3 python3-venv python3-pip python3-dev build-essential libpq-dev git curl ca-certificates

    if [[ ! -d "$ROOT_DIR/venv" ]]; then
        log "Creando entorno virtual"
        python3 -m venv "$ROOT_DIR/venv"
    else
        ok "El entorno virtual ya existe"
    fi

    # shellcheck disable=SC1091
    source "$ROOT_DIR/venv/bin/activate"

    log "Actualizando pip/setuptools/wheel"
    python -m pip install --upgrade pip setuptools wheel

    log "Instalando dependencias Python"
    python -m pip install -r "$ROOT_DIR/requirements.txt"
    ok "Dependencias Python instaladas"
}

ensure_env_file() {
    if [[ ! -f "$ROOT_DIR/.env" ]]; then
        log "Creando .env desde .env.example"
        cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
    else
        ok "Se conserva el .env existente"
    fi

    python3 <<'PY'
from pathlib import Path
import base64
import secrets

env_path = Path(".env")
lines = env_path.read_text(encoding="utf-8").splitlines()
entries = {}
order = []

for line in lines:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    key = key.strip()
    entries[key] = value.strip()
    order.append(key)

def random_token(n=32):
    return secrets.token_hex(n)

def random_base64():
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")

defaults = {
    "DB_HOST": "localhost",
    "DB_PORT": "5433",
    "DB_USER": "agencia_user",
    "DB_PASSWORD": random_token(16),
    "DB_NAME": "agencia_db",
    "SECRET_KEY": random_token(32),
    "ENCRYPTION_KEY": random_base64(),
    "ADMIN_USER": "admin",
    "ADMIN_PASSWORD": random_token(12),
    "DNI_HASH_SALT": random_token(16),
    "DERIVED_KEY_SALT": random_token(16),
    "CORS_ORIGINS": "http://localhost:8000",
    "APP_URL": "http://localhost:8000",
    "FLASK_ENV": "development",
    "FLASK_DEBUG": "False",
    "REDIS_HOST": "localhost",
    "REDIS_PORT": "6379",
    "REDIS_DB": "0",
    "REDIS_URL": "redis://localhost:6379/0",
    "PGADMIN_EMAIL": "admin@agencia.local",
    "PGADMIN_PASSWORD": random_token(12),
    "GRAFANA_ADMIN_PASSWORD": random_token(12),
    "MAIL_PORT": "587",
    "MAIL_USE_TLS": "True",
    "AMADEUS_ENABLED": "false",
    "AMADEUS_DEFAULT_CURRENCY": "EUR",
    "AMADEUS_MAX_RESULTS": "40",
    "DUFFEL_PRIORITY_DELTA_PERCENT": "5",
    "AGENCY_MARKUP_PERCENT": "5.0",
    "SEARCH_RESULTS_LIMIT": "10",
    "CALENDAR_PRICE_CACHE_TTL_SECONDS": "86400",
    "CALENDAR_ENABLE_DAILY_REFRESH": "true",
    "CALENDAR_REFRESH_HOUR_UTC": "3",
    "CALENDAR_REFRESH_MINUTE_UTC": "15",
    "CALENDAR_PREWARM_TOP_ROUTES_LIMIT": "40",
    "CHECKOUT_MULTI_STEP_ENABLED": "true",
    "CHECKOUT_MULTI_STEP_ROLLOUT_PERCENT": "100",
}

for key, default in defaults.items():
    if not entries.get(key, "").strip():
        entries[key] = default

rendered = []
seen = set()
for line in lines:
    stripped = line.strip()
    if stripped and not stripped.startswith("#") and "=" in line:
        key = line.split("=", 1)[0].strip()
        if key in entries:
            rendered.append(f"{key}={entries[key]}")
            seen.add(key)
        else:
            rendered.append(line)
    else:
        rendered.append(line)

for key in defaults:
    if key not in seen and key not in order:
        rendered.append(f"{key}={entries[key]}")

env_path.write_text("\n".join(rendered).rstrip() + "\n", encoding="utf-8")
PY

    ok ".env preparado"
}

validate_compose() {
    log "Validando docker-compose.yml"
    docker compose config >/dev/null
    ok "docker-compose.yml válido"
}

find_latest_backup() {
    find "$ROOT_DIR/backups" -maxdepth 1 -type f \
        \( -name 'agencia_*.sql' -o -name 'agencia_*.sql.gz' \) \
        -size +0c \
        ! -name 'agencia_.sql' \
        -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n1 | cut -d' ' -f2-
}

wait_for_postgres_ready() {
    local db_user db_name
    db_user="$(sed -n 's/^DB_USER=//p' "$ROOT_DIR/.env" | head -n1)"
    db_name="$(sed -n 's/^DB_NAME=//p' "$ROOT_DIR/.env" | head -n1)"

    [[ -n "$db_user" ]] || fail "DB_USER no está definido en .env"
    [[ -n "$db_name" ]] || fail "DB_NAME no está definido en .env"

    for _ in $(seq 1 60); do
        if docker compose exec -T postgres pg_isready -U "$db_user" -d "$db_name" >/dev/null 2>&1; then
            ok "PostgreSQL listo para importar datos"
            return 0
        fi
        sleep 1
    done

    docker compose logs --tail=100 postgres || true
    fail "PostgreSQL no estuvo listo a tiempo durante la instalación"
}

restore_seed_database_if_available() {
    local latest_backup tour_count restored_count
    latest_backup="$(find_latest_backup)"

    if [[ -z "$latest_backup" ]]; then
        warn "No se encontró dump en backups/. La instalación seguirá con base vacía"
        return 0
    fi

    log "Dump detectado: $latest_backup"
    log "Levantando PostgreSQL para precargar la base"
    docker compose up -d postgres
    wait_for_postgres_ready

    tour_count="$(docker compose exec -T postgres psql -U "$(sed -n 's/^DB_USER=//p' .env | head -n1)" -d "$(sed -n 's/^DB_NAME=//p' .env | head -n1)" -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'tours';" | tr -d '[:space:]')"

    if [[ "$tour_count" == "1" && "${FORCE_RESTORE_BACKUP:-false}" != "true" ]]; then
        local existing_tours
        existing_tours="$(docker compose exec -T postgres psql -U "$(sed -n 's/^DB_USER=//p' .env | head -n1)" -d "$(sed -n 's/^DB_NAME=//p' .env | head -n1)" -tAc "SELECT COUNT(*) FROM tours;" | tr -d '[:space:]')"
        if [[ "${existing_tours:-0}" != "0" ]]; then
            warn "La base ya tiene datos (${existing_tours} tours). No se sobrescribe"
            warn "Si quieres forzar la restauración, ejecuta: FORCE_RESTORE_BACKUP=true ./install.sh"
            return 0
        fi
    fi

    log "Importando dump en PostgreSQL"
    restored_count="$(./scripts/import_db_dump.sh "$latest_backup")"
    ok "Base precargada correctamente (${restored_count} tours)"
}

main() {
    printf '%b\n' "${BLUE}Instalación completa de Agencia${NC}"
    ensure_docker_available
    ensure_python_environment
    ensure_node_dependencies
    ensure_env_file
    validate_compose
    chmod +x "$ROOT_DIR/scripts/export_db_dump.sh" "$ROOT_DIR/scripts/import_db_dump.sh" || true
    restore_seed_database_if_available

    chmod +x "$ROOT_DIR/start.sh" "$ROOT_DIR/start_all.sh" "$ROOT_DIR/install.sh" || true

    cat <<'EOF'

Instalación terminada.

Siguiente paso:
  ./start_all.sh

La app arrancará en:
  http://localhost:8000

Si hay un dump válido en backups/, el instalador deja la base restaurada automáticamente.

Para Stripe en local:
  - añade STRIPE_PUBLIC_KEY y STRIPE_SECRET_KEY en .env
  - añade STRIPE_WEBHOOK_SECRET en .env
  - usa /webhook/stripe como endpoint de webhook
EOF

    if ! groups "$USER" | grep -qw docker; then
        warn "Puede que necesites cerrar y abrir sesión para usar Docker sin sudo"
    fi
}

main "$@"
