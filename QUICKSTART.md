# 🚀 Guía Rápida de Despliegue

## Desarrollo Local (3 pasos)

```bash
# 1. Configurar variables
cp env.example .env

# 2. Iniciar servicios
docker compose up -d --build

# 3. Acceder
# Web: http://localhost
# Usuario: admin@admin.com (o el que configuraste en .env)
# Password: changeme123456 (o el que configuraste en .env)
```

## Producción en AWS EC2 (6 pasos)

```bash
# 1. Preparar servidor
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu
# Docker Compose V2 viene integrado con Docker (no necesita instalación separada)
# Verificar: docker compose version

# 2. Clonar proyecto
git clone <tu-repo>
cd soynadia

# 3. Configurar .env
nano .env
# Cambiar: SECRET_KEY, DEBUG=False, ALLOWED_HOSTS
# IMPORTANTE: ADMIN_EMAIL, ADMIN_PASSWORD, POSTGRES_PASSWORD

# 4. Desplegar
docker compose up -d --build

# 5. Verificar
docker compose ps
docker compose logs -f web

# 6. Cambiar contraseña admin
docker compose exec web python manage.py changepassword admin@soynadia.com

# 7. Configurar auto-inicio (OPCIONAL pero recomendado)
sudo cp soynadia-docker.service /etc/systemd/system/
sudo nano /etc/systemd/system/soynadia-docker.service  # Ajustar ruta si es necesario
sudo systemctl daemon-reload
sudo systemctl enable soynadia-docker.service
sudo systemctl start soynadia-docker.service
```

## Crear API Key

```bash
docker compose exec web python manage.py shell
```

```python
from voters.models import ApiKey
from users.models import CustomUser
user = CustomUser.objects.get(email='admin@soynadia.com')
api_key = ApiKey.objects.create(user=user, name='Mi API Key')
print(f'API Key: {api_key.key}')
```

## Probar API

```bash
curl -X POST http://localhost/api/prospects/ \
  -H "Authorization: Api-Key TU-API-KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "identification_number": "1234567890",
    "full_name": "Juan Pérez",
    "phone_number": "3001234567"
  }'
```

## Cloudflare Tunnel (PostgreSQL)

Para exponer PostgreSQL a través de Cloudflare Tunnel:

```bash
# 1. Editar configuración del tunnel
nano ~/.cloudflared/config.yml

# 2. Agregar entrada para PostgreSQL:
# - hostname: db-soynadia.tu-dominio.com
#   service: tcp://localhost:5432

# 3. Crear DNS en Cloudflare:
# CNAME: db-soynadia -> <tunnel-id>.cfargotunnel.com

# 4. Reiniciar tunnel
sudo systemctl restart cloudflared

# 5. Conectarse desde local (con cloudflared instalado)
cloudflared access tcp --hostname db-soynadia.tu-dominio.com --url localhost:5432
# En otra terminal: psql -h localhost -p 5432 -U postgres -d soynadia
```

## Security Group EC2

**Con Cloudflare Tunnel:**
- Puerto 22 (SSH) - Tu IP
- NO necesitas abrir puertos 80/443 (Cloudflare Tunnel los maneja)

**Sin Cloudflare Tunnel:**
- Puerto 22 (SSH) - Tu IP
- Puerto 80 (HTTP) - 0.0.0.0/0
- Puerto 443 (HTTPS) - 0.0.0.0/0

## Variables Importantes

```env
# Django
SECRET_KEY=generar-con-comando-python
DEBUG=False
ALLOWED_HOSTS=tu-ip-o-dominio.com

# Base de datos
POSTGRES_PASSWORD=cambiar-password-seguro

# Superusuario (IMPORTANTE CAMBIAR)
ADMIN_EMAIL=admin@tuempresa.com
ADMIN_PASSWORD=UnPasswordSeguro123!
ADMIN_FIRST_NAME=Admin
ADMIN_LAST_NAME=User
```

Generar SECRET_KEY:
```bash
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## Comandos Útiles

```bash
# Ver logs
docker compose logs -f web

# Reiniciar
docker compose restart

# Backup DB
docker compose exec db pg_dump -U postgres soynadia > backup.sql

# Restore DB
docker compose exec -T db psql -U postgres soynadia < backup.sql
```

## Troubleshooting

- **Error de permisos**: `chmod +x entrypoint.sh`
- **DB no conecta**: Verificar variables en .env
- **502 Bad Gateway**: Ver logs con `docker compose logs web`

---

Para más detalles, ver [README.md](README.md)
