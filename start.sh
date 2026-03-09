#!/bin/bash

# 🚀 Script de Inicio Automático - Viatges Carcaixent
# Ejecuta Docker PostgreSQL + Migración + Flask

set -e  # Salir si hay error

echo "🚀 Iniciando Viatges Carcaixent..."
echo "=================================="

# ✅ 1. Verificar que estamos en el directorio correcto
if [ ! -f "app.py" ]; then
    echo "❌ Error: No se encuentra app.py"
    echo "   Ejecuta este script desde /var/www/agencia"
    exit 1
fi

# ✅ 2. Verificar si Docker está corriendo
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker no está corriendo. Iniciando Docker..."
    sudo systemctl start docker
    sleep 3
fi

# ✅ 3. Iniciar PostgreSQL con Docker (si existe docker-compose.yml)
if [ -f "docker-compose.yml" ]; then
    echo "📦 Iniciando PostgreSQL con docker compose..."
    docker compose up -d postgres
    echo "⏳ Esperando a que PostgreSQL esté listo (10s)..."
    sleep 10
else
    echo "⚠️ No se encontró docker-compose.yml"
    echo "   Asegúrate de que PostgreSQL esté corriendo manualmente"
fi

# ✅ 4. Activar entorno virtual
if [ -d "venv" ]; then
    echo "🐍 Activando entorno virtual..."
    source venv/bin/activate
else
    echo "⚠️ No se encontró venv, usando Python global"
fi

# ✅ 5. Ejecutar migración de full-text search (solo si existe)
if [ -f "scripts/migrate_fulltext_search.py" ]; then
    echo "🔧 Ejecutando migración de full-text search..."
    python scripts/migrate_fulltext_search.py || {
        echo "⚠️ La migración falló, pero continuando..."
    }
else
    echo "ℹ️ No se encontró script de migración"
fi

# ✅ 6. Iniciar Flask en puerto 8000
echo "🌐 Iniciando Flask en puerto 8000..."
echo "=================================="
echo "✅ La aplicación estará disponible en:"
echo "   👉 http://localhost:8000"
echo ""
echo "Presiona Ctrl+C para detener"
echo ""

# Ejecutar Flask en puerto 8000
export FLASK_APP=app.py
export FLASK_ENV=production
python app.py --host=0.0.0.0 --port=8000
