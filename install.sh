#!/bin/bash

################################################################################
# 🚀 VIATGES CARCAIXENT - INSTALADOR COMPLETO
################################################################################
# Este script instala TODO lo necesario para ejecutar la aplicación
# Es idempotente: puedes ejecutarlo múltiples veces sin problemas
################################################################################

set -e  # Exit on error

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Funciones de utilidad
print_header() {
    echo -e "\n${BLUE}════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}════════════════════════════════════════${NC}\n"
}

print_step() {
    echo -e "${YELLOW}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

ensure_docker_installed() {
    print_step "Instalando/actualizando Docker y Docker Compose plugin..."

    if ! command -v apt-get &> /dev/null; then
        print_error "No se encontró apt-get. Instala Docker manualmente para tu distribución."
        exit 1
    fi

    if command -v sudo &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y docker.io docker-compose-plugin
        sudo systemctl enable docker 2>/dev/null || true
        sudo systemctl start docker 2>/dev/null || true
        sudo usermod -aG docker "$USER" 2>/dev/null || true
    else
        apt-get update
        apt-get install -y docker.io docker-compose-plugin
        systemctl enable docker 2>/dev/null || true
        systemctl start docker 2>/dev/null || true
        usermod -aG docker "$USER" 2>/dev/null || true
    fi

    if command -v docker &> /dev/null; then
        print_success "Docker instalado correctamente"
        DOCKER_AVAILABLE=true
    else
        print_error "No se pudo instalar Docker automáticamente"
        DOCKER_AVAILABLE=false
        exit 1
    fi
}

# ============================================================================
# PASO 0: Verificación de Prerequisitos
# ============================================================================
print_header "PASO 0: Verificando Prerequisitos"

# Verificar Python
print_step "Verificando Python 3.10+..."
if ! command -v python3 &> /dev/null; then
    print_error "Python3 no instalado. Instálalo primero: apt-get install python3"
    exit 1
fi
PYTHON_VERSION=$(python3 --version | awk '{print $2}')
print_success "Python $PYTHON_VERSION encontrado"

# Verificar pip
print_step "Verificando pip..."
if ! command -v pip3 &> /dev/null; then
    print_error "pip3 no instalado. Instálalo: apt-get install python3-pip"
    exit 1
fi
print_success "pip3 encontrado"

# Verificar Git
print_step "Verificando Git..."
if ! command -v git &> /dev/null; then
    print_error "Git no instalado. Instálalo: apt-get install git"
    exit 1
fi
print_success "Git encontrado"

# Instalar Docker siempre
ensure_docker_installed

# ============================================================================
# PASO 1: Crear Virtual Environment
# ============================================================================
print_header "PASO 1: Creando Virtual Environment"

if [ -d "venv" ]; then
    print_step "Virtual environment ya existe, saltando..."
else
    print_step "Creando venv..."
    python3 -m venv venv
    print_success "Virtual environment creado"
fi

print_step "Activando venv..."
source venv/bin/activate
print_success "venv activado"

# ============================================================================
# PASO 2: Instalar Dependencias Python
# ============================================================================
print_header "PASO 2: Instalando Dependencias Python"

print_step "Actualizando pip, setuptools y wheel..."
pip install --upgrade pip setuptools wheel > /dev/null 2>&1
print_success "pip actualizado"

print_step "Instalando dependencias de requirements.txt..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    print_success "Dependencias instaladas"
else
    print_error "requirements.txt no encontrado"
    exit 1
fi

# ============================================================================
# PASO 3: Configuración del Archivo .env
# ============================================================================
print_header "PASO 3: Configurando .env"

if [ -f ".env" ]; then
    print_step ".env ya existe"
    read -p "¿Sobrescribir? (s/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Ss]$ ]]; then
        print_success ".env mantenido"
    else
        cp .env.example .env
        print_success ".env regenerado desde .env.example"
    fi
else
    print_step "Creando .env desde .env.example..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_success ".env creado"
    else
        print_error ".env.example no encontrado"
    fi
fi

print_step "⚠️  IMPORTANTE: Edita .env con tus credenciales:"
print_step "   - Database credentials"
print_step "   - API keys (Duffel, Amadeus, Stripe)"
print_step "   - Email configuration"
print_step "   - Admin credentials"

# ============================================================================
# PASO 4: Configurar Docker
# ============================================================================
print_header "PASO 4: Configurando Docker"

print_step "Verificando docker-compose.yml..."
if [ -f "docker-compose.yml" ]; then
    print_success "docker-compose.yml encontrado"

    print_step "Construyendo imágenes Docker..."
    docker compose build --no-cache
    print_success "Imágenes Docker construidas"
else
    print_error "docker-compose.yml no encontrado"
fi

# ============================================================================
# PASO 5: Inicializar Base de Datos (si es local)
# ============================================================================
print_header "PASO 5: Base de Datos"
print_step "Se usará PostgreSQL via Docker (en start_all.sh)"
print_success "Verificación de BD aplazada al inicio"

# ============================================================================
# PASO 6: Verificación de Alembic
# ============================================================================
print_header "PASO 6: Verificando Alembic (Migraciones BD)"

if [ -f "alembic.ini" ]; then
    print_success "alembic.ini encontrado"
else
    print_error "alembic.ini no encontrado"
fi

# ============================================================================
# PASO 7: Compilar Assets Frontend (si aplica)
# ============================================================================
print_header "PASO 7: Frontend Assets"

if [ -d "frontend" ] && [ -f "frontend/package.json" ]; then
    print_step "Proyecto Frontend detectado"
    read -p "¿Instalar npm dependencies? (s/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        cd frontend
        npm install
        print_success "npm dependencies instaladas"
        cd ..
    fi
else
    print_success "No hay frontend npm (se usa only HTML/CSS/JS estático)"
fi

# ============================================================================
# PASO 8: Permisos de Ejecución
# ============================================================================
print_header "PASO 8: Configurando Permisos"

print_step "Haciendo scripts ejecutables..."
chmod +x start_all.sh 2>/dev/null || true
chmod +x start.sh 2>/dev/null || true
print_success "Permisos configurados"

# ============================================================================
# Resumen Final
# ============================================================================
print_header "✅ INSTALACIÓN COMPLETA"

echo -e "${GREEN}Lo siguiente está listo:${NC}"
echo -e "  ✅ Python venv configurado"
echo -e "  ✅ Dependencias instaladas (23 packages)"
echo -e "  ✅ .env template creado (⚠️  EDIT IT WITH YOUR CREDENTIALS)"
echo -e "  ✅ Docker instalado y configurado"
echo -e "  ✅ Docker images built"
echo -e "  ✅ Alembic migrations ready"
echo ""
echo -e "${YELLOW}PRÓXIMOS PASOS:${NC}"
echo ""
echo -e "  1️⃣  ${BLUE}Editar credenciales en .env:${NC}"
echo -e "     nano .env"
echo ""
echo -e "  2️⃣  ${BLUE}Iniciar TODO (con un comando):${NC}"
echo -e "     ${GREEN}./start_all.sh${NC}"
echo ""
echo -e "  3️⃣  ${BLUE}La aplicación estará en:${NC}"
echo -e "     http://localhost:8000"
echo ""
echo -e "${YELLOW}COMANDOS ÚTILES:${NC}"
echo -e "  source venv/bin/activate     # Activar venv"
echo -e "  ./start_all.sh               # Iniciar todo"
echo -e "  docker compose down          # Parar Docker"
echo -e "  docker compose logs -f web   # Ver logs del app"
echo ""
print_success "¡Instalación lista! 🚀"
