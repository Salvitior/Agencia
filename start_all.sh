#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

APP_LOG="/tmp/agencia_app.log"
STRIPE_LOG="/tmp/agencia_stripe.log"
APP_PID_FILE="/tmp/agencia_app.pid"
STRIPE_PID_FILE="/tmp/agencia_stripe.pid"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
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

require_file() {
    [[ -f "$1" ]] || fail "No existe $1"
}

read_env() {
    local key="$1"
    python <<PY
from dotenv import dotenv_values
value = dotenv_values(".env").get("$key", "")
print(value if value is not None else "")
PY
}

ensure_runtime_prereqs() {
    require_file "$ROOT_DIR/.env"
    require_file "$ROOT_DIR/app.py"
    [[ -d "$ROOT_DIR/venv" ]] || fail "No existe venv. Ejecuta ./install.sh primero"
    have_cmd docker || fail "Docker no está instalado"
    docker compose version >/dev/null 2>&1 || fail "Docker Compose no está disponible"
}

activate_venv() {
    # shellcheck disable=SC1091
    source "$ROOT_DIR/venv/bin/activate"
}

ensure_python_dependencies() {
    if python - <<'PY'
import importlib
modules = ["flask", "dotenv", "sqlalchemy", "alembic", "redis"]
missing = []
for module in modules:
    try:
        importlib.import_module(module)
    except Exception:
        missing.append(module)
if missing:
    print(",".join(missing))
    raise SystemExit(1)
PY
    then
        ok "Dependencias Python listas"
        return 0
    fi

    warn "Faltan dependencias Python en el venv; reinstalando requirements.txt"
    python -m pip install -r "$ROOT_DIR/requirements.txt"
}

populate_runtime_env() {
    export DB_HOST="${DB_HOST:-$(read_env DB_HOST)}"
    export DB_PORT="${DB_PORT:-$(read_env DB_PORT)}"
    export DB_USER="${DB_USER:-$(read_env DB_USER)}"
    export DB_PASSWORD="${DB_PASSWORD:-$(read_env DB_PASSWORD)}"
    export DB_NAME="${DB_NAME:-$(read_env DB_NAME)}"
    export APP_URL="${APP_URL:-$(read_env APP_URL)}"
    export FLASK_ENV="${FLASK_ENV:-$(read_env FLASK_ENV)}"
    export REDIS_HOST="${REDIS_HOST:-$(read_env REDIS_HOST)}"
    export REDIS_PORT="${REDIS_PORT:-$(read_env REDIS_PORT)}"
    export REDIS_DB="${REDIS_DB:-$(read_env REDIS_DB)}"
    export REDIS_URL="${REDIS_URL:-$(read_env REDIS_URL)}"
    export START_STRIPE_LISTENER="${START_STRIPE_LISTENER:-$(read_env START_STRIPE_LISTENER)}"

    [[ -n "$DB_PASSWORD" ]] || fail "DB_PASSWORD no está configurada en .env"
    [[ -n "$DB_PORT" ]] || export DB_PORT="5433"
    [[ -n "$REDIS_HOST" ]] || export REDIS_HOST="localhost"
    [[ -n "$REDIS_PORT" ]] || export REDIS_PORT="6379"
    [[ -n "$REDIS_DB" ]] || export REDIS_DB="0"
    [[ -n "$REDIS_URL" ]] || export REDIS_URL="redis://localhost:6379/0"
    [[ -n "$APP_URL" ]] || export APP_URL="http://localhost:8000"
    [[ -n "$START_STRIPE_LISTENER" ]] || export START_STRIPE_LISTENER="false"
}

stop_previous_app() {
    if [[ -f "$APP_PID_FILE" ]]; then
        local pid
        pid="$(cat "$APP_PID_FILE" 2>/dev/null || true)"
        if [[ -n "${pid:-}" ]] && kill -0 "$pid" >/dev/null 2>&1; then
            log "Deteniendo app previa (PID $pid)"
            kill "$pid" >/dev/null 2>&1 || true
            sleep 1
        fi
        rm -f "$APP_PID_FILE"
    fi

    pkill -f "python.*app.py" >/dev/null 2>&1 || true
    pkill -f "gunicorn.*app:app" >/dev/null 2>&1 || true

    if have_cmd fuser; then
        fuser -k 8000/tcp >/dev/null 2>&1 || true
    fi
}

stop_previous_stripe_listener() {
    if [[ -f "$STRIPE_PID_FILE" ]]; then
        local pid
        pid="$(cat "$STRIPE_PID_FILE" 2>/dev/null || true)"
        if [[ -n "${pid:-}" ]] && kill -0 "$pid" >/dev/null 2>&1; then
            log "Deteniendo Stripe listener previo (PID $pid)"
            kill "$pid" >/dev/null 2>&1 || true
            sleep 1
        fi
        rm -f "$STRIPE_PID_FILE"
    fi
}

start_docker_stack() {
    log "Levantando PostgreSQL, Redis, Prometheus, Grafana y PgAdmin"
    docker compose up -d postgres redis prometheus grafana pgadmin
}

wait_for_postgres() {
    local tries=60
    local i
    for ((i=1; i<=tries; i++)); do
        if docker compose exec -T postgres pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then
            ok "PostgreSQL listo"
            return 0
        fi
        sleep 1
    done

    docker compose logs --tail=100 postgres || true
    fail "PostgreSQL no respondió a tiempo"
}

wait_for_redis() {
    if docker compose exec -T redis redis-cli ping >/dev/null 2>&1; then
        ok "Redis listo"
        return 0
    fi
    warn "Redis no respondió al ping inicial; la app seguirá arrancando"
}

run_migrations() {
    log "Aplicando migraciones Alembic"
    python -m alembic upgrade head
    ok "Migraciones aplicadas"
}

start_application() {
    log "Arrancando Flask"
    nohup python app.py >"$APP_LOG" 2>&1 &
    echo $! >"$APP_PID_FILE"
    sleep 3

    local pid
    pid="$(cat "$APP_PID_FILE")"
    kill -0 "$pid" >/dev/null 2>&1 || {
        tail -n 50 "$APP_LOG" || true
        fail "La app no consiguió arrancar"
    }
    ok "App arrancada (PID $pid)"
}

wait_for_healthcheck() {
    local tries=30
    local i
    for ((i=1; i<=tries; i++)); do
        if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
            ok "Healthcheck OK en /health"
            return 0
        fi
        sleep 1
    done

    tail -n 50 "$APP_LOG" || true
    fail "La app no respondió en http://localhost:8000/health"
}

report_stripe_status() {
    local stripe_public stripe_secret stripe_webhook
    stripe_public="$(read_env STRIPE_PUBLIC_KEY)"
    stripe_secret="$(read_env STRIPE_SECRET_KEY)"
    stripe_webhook="$(read_env STRIPE_WEBHOOK_SECRET)"

    if [[ -n "$stripe_public" && -n "$stripe_secret" && -n "$stripe_webhook" ]]; then
        ok "Stripe configurado en .env"
    else
        warn "Stripe no está completamente configurado todavía"
        warn "Faltan una o más de estas variables: STRIPE_PUBLIC_KEY, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET"
    fi

    if [[ "${START_STRIPE_LISTENER:-false}" == "true" ]]; then
        if have_cmd stripe; then
            log "Iniciando stripe listen en segundo plano"
            nohup stripe listen --forward-to localhost:8000/webhook/stripe >"$STRIPE_LOG" 2>&1 &
            echo $! >"$STRIPE_PID_FILE"
            ok "Stripe listener arrancado. Logs en $STRIPE_LOG"
        else
            warn "START_STRIPE_LISTENER=true pero el CLI de Stripe no está instalado"
        fi
    fi
}

print_summary() {
    cat <<EOF

Servicios activos:
  App:        http://localhost:8000
  Health:     http://localhost:8000/health
  Webhook:    http://localhost:8000/webhook/stripe
  PostgreSQL: localhost:${DB_PORT}
  Redis:      localhost:${REDIS_PORT}
  Grafana:    http://localhost:3000
  Prometheus: http://localhost:9090
  PgAdmin:    http://localhost:5050

Logs:
  App:        $APP_LOG
  Docker:     docker compose logs -f
EOF

    if [[ -f "$STRIPE_PID_FILE" ]]; then
        printf '  Stripe:     %s\n' "$STRIPE_LOG"
    fi
}

main() {
    ensure_runtime_prereqs
    activate_venv
    ensure_python_dependencies
    populate_runtime_env
    stop_previous_app
    stop_previous_stripe_listener
    start_docker_stack
    wait_for_postgres
    wait_for_redis
    run_migrations
    start_application
    wait_for_healthcheck
    report_stripe_status
    print_summary
}

main "$@"
