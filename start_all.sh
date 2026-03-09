#!/bin/bash

################################################################################
# 🚀 VIATGES CARCAIXENT - INICIADOR COMPLETO
################################################################################
# Este script inicia TODO: Docker, BD, API, etc.
# Ejecuta: ./start_all.sh
################################################################################

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Funciones
print_header() {
    echo -e "\n${MAGENTA}╔════════════════════════════════════════╗${NC}"
    echo -e "${MAGENTA}║ $1${NC}"
    echo -e "${MAGENTA}╚════════════════════════════════════════╝${NC}\n"
}

print_step() {
    echo -e "${CYAN}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_url() {
    echo -e "${YELLOW}🔗 $1${NC}"
}

# ============================================================================
# Verificación de Prerequisitos
# ============================================================================
print_header "VERIFICANDO PREREQUISITOS"

# Verificar .env
if [ ! -f ".env" ]; then
    print_error ".env no encontrado"
    print_error "Por favor ejecuta:"
    echo "  cp .env.example .env"
    echo "  nano .env  # Edita con tus credenciales"
    exit 1
fi
print_success ".env encontrado"

# Verificar Docker
if ! command -v docker &> /dev/null; then
    print_error "Docker no está instalado"
    print_error "Instálalo desde: https://docs.docker.com/get-docker/"
    exit 1
fi
print_success "Docker disponible"

# Verificar Docker Compose (plugin)
if ! command -v docker compose &> /dev/null; then
    print_error "Docker Compose plugin no está disponible"
    print_error "Instálalo: sudo apt-get install docker-compose-plugin"
    exit 1
fi
print_success "docker compose disponible"

# Verificar venv
if [ ! -d "venv" ]; then
    print_warning "Virtual environment no encontrado"
    print_step "Creando venv..."
    python3 -m venv venv
fi
print_success "venv listo"

# ============================================================================
# Activar Virtual Environment
# ============================================================================
print_step "Activando virtual environment..."
source venv/bin/activate
print_success "venv activado"

# ============================================================================
# Parar Contenedores Anteriores
# ============================================================================
print_header "DETENIENDO SERVICIOS ANTERIORES"

print_step "Parando stack Docker anterior..."
docker compose down 2>/dev/null || true
sleep 1
print_success "Servicios detenidos"

# ============================================================================
# Iniciar Docker Compose
# ============================================================================
print_header "INICIANDO SERVICIOS DOCKER"

print_step "Iniciando PostgreSQL, Redis, y otros servicios..."
docker compose up -d
sleep 3
print_success "Servicios Docker iniciados"

# Verificar que PostgreSQL está listo
print_step "Esperando a que PostgreSQL esté listo..."
DB_USER_VALUE="${DB_USER:-postgres}"
DB_NAME_VALUE="${DB_NAME:-agencia_db}"
for i in {1..60}; do
    HEALTH_STATUS=$(docker compose inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' postgres 2>/dev/null || echo "unknown")

    if [ "$HEALTH_STATUS" = "healthy" ]; then
        print_success "PostgreSQL está listo (healthy)"
        break
    fi

    if docker compose exec -T postgres pg_isready -U "$DB_USER_VALUE" -d "$DB_NAME_VALUE" &>/dev/null; then
        print_success "PostgreSQL responde a pg_isready"
        break
    fi

    if [ $i -eq 60 ]; then
        print_error "PostgreSQL tardó demasiado en iniciar"
        print_warning "Últimos logs de postgres:"
        docker compose logs --tail=50 postgres || true
        exit 1
    fi

    echo -n "."
    sleep 1
done
echo ""

# ============================================================================
# Aplicar Migraciones de Base de Datos
# ============================================================================
print_header "APLICANDO MIGRACIONES DE BD"

print_step "Ejecutando: alembic upgrade head..."
python3 -m alembic upgrade head
print_success "Migraciones aplicadas"

# ============================================================================
# Iniciar la Aplicación Flask
# ============================================================================
print_header "INICIANDO APLICACIÓN FLASK"

print_step "Matando procesos anteriores de Flask..."
pkill -f "python.*app.py" 2>/dev/null || true
sleep 1

print_step "Iniciando Flask en segundo plano..."
nohup python3 app.py > /tmp/agencia_app.log 2>&1 &
APP_PID=$!
sleep 2

print_success "Flask iniciado (PID: $APP_PID)"

# ============================================================================
# Verificaciones Finales
# ============================================================================
print_header "VERIFICACIONES FINALES"

# Health Check
print_step "Verificando health endpoint..."
for i in {1..10}; do
    if curl -s http://localhost:8000/health &>/dev/null; then
        HEALTH=$(curl -s http://localhost:8000/health)
        print_success "Health: $HEALTH"
        break
    fi
    if [ $i -eq 10 ]; then
        print_warning "Health check no respondió (pero puede estar iniciando)"
    fi
    echo -n "."
    sleep 1
done
echo ""

# Docker Status
print_step "Estado de servicios Docker:"
docker compose ps | tail -n +2 | while read -r line; do
    if echo "$line" | grep -q "Up"; then
        echo -e "${GREEN}✅ $line${NC}"
    else
        echo -e "${YELLOW}⏸️  $line${NC}"
    fi
done

# Flask Log Check
print_step "Últimas líneas del log de Flask:"
tail -n 5 /tmp/agencia_app.log | sed 's/^/  /'

# ============================================================================
# Resumen Final
# ============================================================================
print_header "🚀 ¡TODO INICIADO!"

echo -e "${GREEN}Servicios Activos:${NC}"
echo -e "  ✅ PostgreSQL (puerto 5433)"
echo -e "  ✅ Redis (puerto 6379) [opcional]"
echo -e "  ✅ Prometheus (puerto 9090)"
echo -e "  ✅ Grafana (puerto 3000)"
echo -e "  ✅ PgAdmin (puerto 5050)"
echo -e "  ✅ Flask API (puerto 8000)"
echo ""

echo -e "${YELLOW}ACCESA LA APLICACIÓN:${NC}"
print_url "http://localhost:8000"
print_url "http://localhost"
echo ""

echo -e "${YELLOW}ADMIN PANEL:${NC}"
print_url "http://localhost:8000/admin"
echo ""

echo -e "${YELLOW}COMANDOS ÚTILES:${NC}"
echo -e "  ${CYAN}Ver logs${NC}:"
echo -e "    tail -f /tmp/agencia_app.log"
echo -e "    docker compose logs -f"
echo ""
echo -e "  ${CYAN}Parar todo${NC}:"
echo -e "    docker compose down"
echo ""
echo -e "  ${CYAN}Reiniciar aplicación${NC}:"
echo -e "    pkill -f 'python.*app.py'; sleep 1; python3 app.py"
echo ""
echo -e "  ${CYAN}Base de datos${NC}:"
echo -e "    psql -h localhost -p 5433 -U agencia_user -d agencia_db"
echo ""
echo -e "  ${CYAN}Estado Docker${NC}:"
echo -e "    docker compose ps"
echo ""

# ============================================================================
# Menu Interactivo (opcional)
# ============================================================================
echo -e "${MAGENTA}════════════════════════════════════════${NC}"
read -p "¿Ver logs en tiempo real? (s/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Ss]$ ]]; then
    echo -e "${CYAN}Mostrando logs (Ctrl+C para salir)...${NC}\n"
    tail -f /tmp/agencia_app.log
fi
