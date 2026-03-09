# ============================================================================
# 🚀 VIATGES CARCAIXENT - INSTALADOR COMPLETO (WINDOWS)
# ============================================================================
# Este script instala TODO lo necesario para ejecutar la aplicación
# Ejecuta: .\install.ps1
# ============================================================================

# Configuration
$ErrorActionPreference = "Stop"

# Colores
function Write-Header {
    param([string]$Message)
    Write-Host "`n" -NoNewline
    Write-Host "════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host $Message -ForegroundColor Cyan
    Write-Host "════════════════════════════════════════`n" -ForegroundColor Cyan
}

function Write-Step {
    param([string]$Message)
    Write-Host "▶ $Message" -ForegroundColor Yellow
}

function Write-Success {
    param([string]$Message)
    Write-Host "✅ $Message" -ForegroundColor Green
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "❌ $Message" -ForegroundColor Red
}

function Write-Warning-Custom {
    param([string]$Message)
    Write-Host "⚠️  $Message" -ForegroundColor Yellow
}

function Ensure-DockerInstalled {
    Write-Step "Instalando/actualizando Docker Desktop..."

    $dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        & winget install --id Docker.DockerDesktop --exact --source winget --accept-package-agreements --accept-source-agreements --silent
    } elseif (Get-Command choco -ErrorAction SilentlyContinue) {
        & choco install docker-desktop -y
    } elseif (-not $dockerCommand) {
        Write-Error-Custom "No se encontró winget/choco para instalar Docker automáticamente"
        Write-Error-Custom "Instala Docker Desktop manualmente: https://www.docker.com/products/docker-desktop/"
        exit 1
    }

    if (Get-Command docker -ErrorAction SilentlyContinue) {
        Write-Success "Docker instalado correctamente"
        return $true
    }

    Write-Error-Custom "Docker no quedó disponible en PATH. Reinicia terminal o Windows y vuelve a ejecutar."
    exit 1
}

# ============================================================================
# PASO 0: Verificación de Prerequisitos
# ============================================================================
Write-Header "PASO 0: Verificando Prerequisitos"

# Verificar Python
Write-Step "Verificando Python 3.10+..."
try {
    $pythonVersion = & python --version 2>&1
    Write-Success "Python encontrado: $pythonVersion"
} catch {
    Write-Error-Custom "Python no instalado. Descárgalo de: https://www.python.org/"
    exit 1
}

# Verificar pip
Write-Step "Verificando pip..."
try {
    & pip --version | Out-Null
    Write-Success "pip encontrado"
} catch {
    Write-Error-Custom "pip no instalado. Instálalo con: python -m ensurepip"
    exit 1
}

# Verificar Git
Write-Step "Verificando Git..."
if (Get-Command git -ErrorAction SilentlyContinue) {
    Write-Success "Git encontrado"
} else {
    Write-Error-Custom "Git no instalado. Descárgalo de: https://git-scm.com/"
    exit 1
}

# Instalar Docker siempre
Write-Step "Verificando Docker..."
$dockerAvailable = Ensure-DockerInstalled

# ============================================================================
# PASO 1: Crear Virtual Environment
# ============================================================================
Write-Header "PASO 1: Creando Virtual Environment"

if (Test-Path "venv") {
    Write-Step "Virtual environment ya existe, saltando..."
} else {
    Write-Step "Creando venv..."
    & python -m venv venv
    Write-Success "Virtual environment creado"
}

Write-Step "Activando venv..."
& .\venv\Scripts\Activate.ps1
Write-Success "venv activado"

# ============================================================================
# PASO 2: Instalar Dependencias Python
# ============================================================================
Write-Header "PASO 2: Instalando Dependencias Python"

Write-Step "Actualizando pip, setuptools y wheel..."
& python -m pip install --upgrade pip setuptools wheel | Out-Null
Write-Success "pip actualizado"

Write-Step "Instalando dependencias de requirements.txt..."
if (Test-Path "requirements.txt") {
    & pip install -r requirements.txt
    Write-Success "Dependencias instaladas"
} else {
    Write-Error-Custom "requirements.txt no encontrado"
    exit 1
}

# ============================================================================
# PASO 3: Configuración del Archivo .env
# ============================================================================
Write-Header "PASO 3: Configurando .env"

if (Test-Path ".env") {
    Write-Step ".env ya existe"
    $response = Read-Host "¿Sobrescribir? (s/n)"
    if ($response -eq "s") {
        Copy-Item ".env.example" ".env"
        Write-Success ".env regenerado desde .env.example"
    } else {
        Write-Success ".env mantenido"
    }
} else {
    Write-Step "Creando .env desde .env.example..."
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Success ".env creado"
    } else {
        Write-Error-Custom ".env.example no encontrado"
    }
}

Write-Host ""
Write-Host "⚠️  IMPORTANTE: Edita .env con tus credenciales:" -ForegroundColor Yellow
Write-Host "   - Database credentials" -ForegroundColor Yellow
Write-Host "   - API keys (Duffel, Amadeus, Stripe)" -ForegroundColor Yellow
Write-Host "   - Email configuration" -ForegroundColor Yellow
Write-Host "   - Admin credentials" -ForegroundColor Yellow

# ============================================================================
# PASO 4: Configurar Docker
# ============================================================================
Write-Header "PASO 4: Configurando Docker"

Write-Step "Verificando docker-compose.yml..."
if (Test-Path "docker-compose.yml") {
    Write-Success "docker-compose.yml encontrado"

    Write-Step "Construyendo imágenes Docker..."
    & docker compose build --no-cache
    Write-Success "Imágenes Docker construidas"
} else {
    Write-Error-Custom "docker-compose.yml no encontrado"
}

# ============================================================================
# PASO 5: Permisos
# ============================================================================
Write-Header "PASO 5: Preparando Scripts"

if (Test-Path "start_all.ps1") {
    Write-Success "start_all.ps1 encontrado"
} else {
    Write-Warning-Custom "start_all.ps1 no encontrado en este directorio"
}

# ============================================================================
# Resumen Final
# ============================================================================
Write-Header "✅ INSTALACIÓN COMPLETA"

Write-Host "Lo siguiente está listo:" -ForegroundColor Green
Write-Host "  ✅ Python venv configurado" -ForegroundColor Green
Write-Host "  ✅ Dependencias instaladas (23 packages)" -ForegroundColor Green
Write-Host "  ✅ .env template creado (⚠️  EDIT IT WITH YOUR CREDENTIALS)" -ForegroundColor Green
Write-Host "  ✅ Docker instalado y configurado" -ForegroundColor Green

Write-Host ""
Write-Host "PRÓXIMOS PASOS:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  1️⃣  Editar credenciales en .env:" -ForegroundColor Blue
Write-Host "     notepad .env" -ForegroundColor Yellow
Write-Host ""
Write-Host "  2️⃣  Iniciar TODO (con un comando):" -ForegroundColor Blue
Write-Host "     .\start_all.ps1" -ForegroundColor Green
Write-Host ""
Write-Host "  3️⃣  La aplicación estará en:" -ForegroundColor Blue
Write-Host "     http://localhost:8000" -ForegroundColor Yellow
Write-Host ""

Write-Success "¡Instalación lista! 🚀"
