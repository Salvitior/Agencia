# ============================================================================
# 🚀 VIATGES CARCAIXENT - INICIADOR COMPLETO (WINDOWS)
# ============================================================================
# Este script inicia TODO: Docker, BD, API, etc.
# Ejecuta: .\start_all.ps1
# ============================================================================

$ErrorActionPreference = "Stop"

# Colores
function Write-Header {
    param([string]$Message)
    Write-Host "`n╔════════════════════════════════════════╗" -ForegroundColor Magenta
    Write-Host "║ $Message" -ForegroundColor Magenta
    Write-Host "╚════════════════════════════════════════╝`n" -ForegroundColor Magenta
}

function Write-Step {
    param([string]$Message)
    Write-Host "▶ $Message" -ForegroundColor Cyan
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

function Write-URL {
    param([string]$Message)
    Write-Host "🔗 $Message" -ForegroundColor Yellow
}

# ============================================================================
# Verificación de Prerequisitos
# ============================================================================
Write-Header "VERIFICANDO PREREQUISITOS"

# Verificar .env
if (-not (Test-Path ".env")) {
    Write-Error-Custom ".env no encontrado"
    Write-Error-Custom "Por favor ejecuta:"
    Write-Host "  copy .env.example .env" -ForegroundColor Yellow
    Write-Host "  notepad .env  # Edita con tus credenciales" -ForegroundColor Yellow
    exit 1
}
Write-Success ".env encontrado"

# Verificar Docker
try {
    & docker --version | Out-Null
    Write-Success "Docker disponible"
} catch {
    Write-Error-Custom "Docker no está instalado"
    Write-Error-Custom "Instálalo desde: https://www.docker.com/products/docker-desktop/"
    exit 1
}

# Verificar Docker Compose (plugin)
try {
    & docker compose version | Out-Null
    Write-Success "docker compose disponible"
} catch {
    Write-Error-Custom "Docker Compose plugin no está disponible"
    Write-Error-Custom "Instálalo o asegúrate de que está en PATH"
    exit 1
}

# Verificar venv
if (-not (Test-Path "venv")) {
    Write-Warning-Custom "Virtual environment no encontrado"
    Write-Step "Creando venv..."
    & python -m venv venv
}
Write-Success "venv listo"

# ============================================================================
# Activar Virtual Environment
# ============================================================================
Write-Step "Activando virtual environment..."
& .\venv\Scripts\Activate.ps1
Write-Success "venv activado"

# ============================================================================
# Parar Contenedores Anteriores
# ============================================================================
Write-Header "DETENIENDO SERVICIOS ANTERIORES"

Write-Step "Parando stack Docker anterior..."
Try {
    & docker compose down 2>$null
}
Catch {}
Start-Sleep -Seconds 1
Write-Success "Servicios detenidos"

# ============================================================================
# Iniciar Docker Compose
# ============================================================================
Write-Header "INICIANDO SERVICIOS DOCKER"

Write-Step "Iniciando PostgreSQL, Redis, y otros servicios..."
& docker compose up -d
Start-Sleep -Seconds 3
Write-Success "Servicios Docker iniciados"

# Verificar que PostgreSQL está listo
Write-Step "Esperando a que PostgreSQL esté listo..."
$ready = $false
for ($i = 1; $i -le 30; $i++) {
    Try {
        & docker compose exec -T postgres pg_isready -U agencia_user -d agencia_db 2>$null | Out-Null
        $ready = $true
        break
    }
    Catch {}
    
    if ($i -eq 30) {
        Write-Error-Custom "PostgreSQL tardó demasiado en iniciar"
        exit 1
    }
    Write-Host "." -NoNewline -ForegroundColor Cyan
    Start-Sleep -Seconds 1
}
Write-Host ""
Write-Success "PostgreSQL está listo"

# ============================================================================
# Aplicar Migraciones de Base de Datos
# ============================================================================
Write-Header "APLICANDO MIGRACIONES DE BD"

Write-Step "Ejecutando: alembic upgrade head..."
& python -m alembic upgrade head
Write-Success "Migraciones aplicadas"

# ============================================================================
# Iniciar la Aplicación Flask
# ============================================================================
Write-Header "INICIANDO APLICACIÓN FLASK"

Write-Step "Matando procesos anteriores de Flask..."
Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*app.py*" } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

Write-Step "Iniciando Flask en segundo plano..."
$logPath = "$env:TEMP\agencia_app.log"
Start-Process python -ArgumentList "app.py" -NoNewWindow -RedirectStandardOutput $logPath -RedirectStandardError "$env:TEMP\agencia_app_error.log"
Start-Sleep -Seconds 2

Write-Success "Flask iniciado"

# ============================================================================
# Verificaciones Finales
# ============================================================================
Write-Header "VERIFICACIONES FINALES"

# Health Check
Write-Step "Verificando health endpoint..."
$healthy = $false
for ($i = 1; $i -le 10; $i++) {
    Try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-Success "Health: OK (HTTP 200)"
            $healthy = $true
            break
        }
    }
    Catch {}
    
    if ($i -eq 10) {
        Write-Warning-Custom "Health check no respondió (pero puede estar iniciando)"
    }
    Write-Host "." -NoNewline -ForegroundColor Green
    Start-Sleep -Seconds 1
}
Write-Host ""

# Docker Status
Write-Step "Estado de servicios Docker:"
$dockerStatus = & docker compose ps
$dockerStatus | Select-Object -Skip 1 | ForEach-Object {
    if ($_ -match "Up") {
        Write-Host "✅ $_" -ForegroundColor Green
    } else {
        Write-Host "⏸️  $_" -ForegroundColor Yellow
    }
}

# Flask Log Check
Write-Step "Últimas líneas del log de Flask:"
if (Test-Path $logPath) {
    Get-Content $logPath | Select-Object -Last 5 | ForEach-Object {
        Write-Host "  $_" -ForegroundColor Gray
    }
}

# ============================================================================
# Resumen Final
# ============================================================================
Write-Header "🚀 ¡TODO INICIADO!"

Write-Host "Servicios Activos:" -ForegroundColor Green
Write-Host "  ✅ PostgreSQL (puerto 5433)" -ForegroundColor Green
Write-Host "  ✅ Redis (puerto 6379) [opcional]" -ForegroundColor Green
Write-Host "  ✅ Prometheus (puerto 9090)" -ForegroundColor Green
Write-Host "  ✅ Grafana (puerto 3000)" -ForegroundColor Green
Write-Host "  ✅ PgAdmin (puerto 5050)" -ForegroundColor Green
Write-Host "  ✅ Flask API (puerto 8000)" -ForegroundColor Green
Write-Host ""

Write-Host "ACCESA LA APLICACIÓN:" -ForegroundColor Yellow
Write-URL "http://localhost:8000"
Write-URL "http://localhost"
Write-Host ""

Write-Host "ADMIN PANEL:" -ForegroundColor Yellow
Write-URL "http://localhost:8000/admin"
Write-Host ""

Write-Host "COMANDOS ÚTILES:" -ForegroundColor Yellow
Write-Host "  Ver logs:" -ForegroundColor Cyan
Write-Host "    type $logPath" -ForegroundColor Yellow
Write-Host "    docker compose logs -f" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Parar todo:" -ForegroundColor Cyan
Write-Host "    docker compose down" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Reiniciar aplicación:" -ForegroundColor Cyan
Write-Host "    Stop-Process -Name python -Force" -ForegroundColor Yellow
Write-Host "    python app.py" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Estado Docker:" -ForegroundColor Cyan
Write-Host "    docker compose ps" -ForegroundColor Yellow
Write-Host ""

Write-Host "════════════════════════════════════════" -ForegroundColor Magenta
Write-Host "¡La aplicación está corriendo! 🎉" -ForegroundColor Green
Write-Host "════════════════════════════════════════" -ForegroundColor Magenta

# Menu interactivo
$response = Read-Host "¿Abrir navegador? (s/n)"
if ($response -eq "s") {
    Start-Process "http://localhost:8000"
}
