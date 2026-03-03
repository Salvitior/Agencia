# ⚡ Quick Start Guide - Viatges Carcaixent

Instalación y ejecución completa en 3 pasos.

---

## 🎯 Para Usuarios Linux/WSL

### Paso 1: Instalador
```bash
chmod +x install.sh
./install.sh
```
Esto instala:
- ✅ Python venv
- ✅ Todas las dependencias (requirements.txt)
- ✅ Docker images
- ✅ Base de datos Docker
- ✅ Configuración inicial

**Tiempo**: ~2-3 minutos

### Paso 2: Configurar Credenciales
```bash
nano .env
```
Edita con tus valores:
- Database (postgres)
- API Keys (Duffel, Amadeus, Stripe)
- Email credentials
- Admin credentials

### Paso 3: Iniciar TODO
```bash
chmod +x start_all.sh
./start_all.sh
```

Esto levanta:
- ✅ PostgreSQL en puerto 5433
- ✅ Redis en puerto 6379
- ✅ Prometheus en puerto 9090
- ✅ Grafana en puerto 3000
- ✅ PgAdmin en puerto 5050
- ✅ Flask API en puerto 8000
- ✅ Aplica migraciones DB
- ✅ Inicia la aplicación

**Resultado**:
```
🔗 http://localhost:8000
🔗 http://localhost
🔑 Admin: http://localhost:8000/admin
```

---

## 🎯 Para Usuarios Windows (PowerShell)

### Paso 1: Instalador
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\install.ps1
```

### Paso 2: Configurar Credenciales
```powershell
notepad .env
```

### Paso 3: Iniciar TODO
```powershell
.\start_all.ps1
```

---

## 📊 Scripts Explicados

### `install.sh` / `install.ps1`
**Qué hace**:
1. Verifica Python 3.10+, Git, Docker
2. Crea virtual environment (`venv/`)
3. Instala todas las dependencias de `requirements.txt`
4. Crea `.env` desde `.env.example`
5. Descarga imágenes Docker

**Cuándo usarlo**: Primera vez que clonas el repo, o cuando cambies de máquina

**Tiempo**: 2-5 minutos (depende de internet)

---

### `start_all.sh` / `start_all.ps1`
**Qué hace**:
1. Verifica que `.env` existe
2. Detiene servicios anteriores
3. Levanta Docker Compose (PostgreSQL, Redis, etc.)
4. Espera a que PostgreSQL esté listo
5. Aplica migraciones de base de datos
6. Inicia la aplicación Flask
7. Verifica health endpoint
8. Muestra URLs de acceso

**Cuándo usarlo**: Cada vez que quieras iniciar la aplicación

**Tiempo**: 30-60 segundos (después del primer inicio)

---

## 🔧 Qué hace Docker Compose

El archivo `docker-compose.yml` inicia:

| Servicio | Puerto | Descripción |
|----------|--------|-------------|
| **PostgreSQL** | 5433 | Base de datos principal |
| **Redis** | 6379 | Cache (opcional) |
| **Prometheus** | 9090 | Métricas |
| **Grafana** | 3000 | Dashboards |
| **PgAdmin** | 5050 | Gestión visual de PostgreSQL |

---

## 📋 Checklist de Configuración

### Antes de `start_all.sh`:

- [ ] Has ejecutado `install.sh` o `install.ps1`
- [ ] Editaste `.env` con tus:
  - [ ] Database credentials
  - [ ] API keys (Duffel, Stripe, Amadeus)
  - [ ] Email SMTP settings
  - [ ] Admin username/password
- [ ] Docker está corriendo
- [ ] Puertos 80, 5433, 6379, 8000 están libres

### Después de `start_all.sh`:

- [ ] Acceso a http://localhost:8000 funciona
- [ ] Admin login funciona
- [  ] Puedes buscar vuelos
- [ ] Puedes procesar pagos

---

## 🐛 Solucionar Problemas

### "Docker no está instalado"
```bash
# Linux
sudo apt-get install docker.io docker-compose-plugin

# Mac
brew install docker

# Windows
Descarga Docker Desktop desde: https://www.docker.com/products/docker-desktop
```

### "Permission denied: ./install.sh"
```bash
chmod +x install.sh
chmod +x start_all.sh
```

### "PostgreSQL tardó demasiado"
```bash
# Ver qué está pasando
docker compose logs postgres

# Reiniciar
docker compose down
docker compose up -d
```

### "Puerto 8000 ya está en uso"
```bash
# Encuentra qué está usando el puerto
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Mata el proceso
kill -9 <PID>  # macOS/Linux
taskkill /PID <PID> /F  # Windows
```

### "La aplicación inicia pero da error"
```bash
# Ver errores
tail -f /tmp/agencia_app.log  # Linux/macOS
type $env:TEMP\agencia_app.log  # Windows

# O en Docker
docker compose logs -f
```

---

## 📚 Comandos Útiles

### Ver Logs
```bash
# Flask
tail -f /tmp/agencia_app.log

# Docker
docker compose logs -f

# PostgreSQL
docker compose logs postgres

# Nginx
docker compose logs
```

### Parar Todo
```bash
docker compose down
```

### Reiniciar Aplicación
```bash
# Linux/macOS
pkill -f "python.*app.py"
sleep 1
python3 app.py

# Windows
Stop-Process -Name python -Force
python app.py
```

### Acceder a PostgreSQL
```bash
psql -h localhost -p 5433 -U agencia_user -d agencia_db
```

### Ver Status de Contenedores
```bash
docker compose ps
```

### Ejecutar Migraciones Manualmente
```bash
python -m alembic upgrade head
```

---

## 🚀 Próximos Pasos

1. **Desarrollo**:
   - Edita `app.py` y templates
   - Reinicia con `pkill -f "python.*app.py"`

2. **Deploy**:
   - Sigue `README.md` para deployment
   - Usa Docker en producción

3. **Git**:
   - Haz cambios en una rama: `git checkout -b feature/mi-feature`
   - Pushea: `git push origin feature/mi-feature`
   - Abre Pull Request en GitHub

---

## 📞 Ayuda

Si algo no funciona:

1. Revisa los logs: `docker compose logs`
2. Consulta `.env` y `docker-compose.yml`
3. Lee [README.md](README.md) para más detalles

---

**¡Happy coding! 🎉**
