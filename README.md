# SoyNadia - Sistema de Gestión de Prospectos

Sistema completo de gestión de prospectos con Django, PostgreSQL, API REST y despliegue en AWS EC2 con Docker.

## 🚀 Características

- ✅ Autenticación con email (sin username)
- ✅ Gestión completa de prospectos (CRUD)
- ✅ API REST con autenticación por API Key
- ✅ Interfaz moderna con Tailwind CSS
- ✅ Búsqueda por número de identificación
- ✅ Contraseñas robustas con Argon2
- ✅ Docker y Docker Compose
- ✅ Nginx como proxy reverso
- ✅ PostgreSQL como base de datos
- ✅ Listo para producción en AWS EC2

## 📋 Requisitos

- Docker 20.10+ (incluye Docker Compose V2 integrado)
- Git

## 🏗️ Arquitectura

```
┌─────────────┐
│   Usuario   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Nginx:80   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Gunicorn  │
│   Django    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ PostgreSQL  │
└─────────────┘
```

## 🔧 Instalación Local

### 1. Clonar el repositorio

```bash
git clone <tu-repositorio>
cd soynadia
```

### 2. Configurar variables de entorno

Copia el archivo de ejemplo y edita según tus necesidades:

```bash
cp .env.example .env
nano .env
```

Variables importantes:

```env
# Django
SECRET_KEY=tu-secret-key-super-segura-aqui
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,tu-dominio.com

# Base de datos
POSTGRES_DB=soynadia
POSTGRES_USER=postgres
POSTGRES_PASSWORD=tu-password-seguro
DB_EXTERNAL_PORT=5432

# Superusuario (creado automáticamente)
ADMIN_EMAIL=admin@tudominio.com
ADMIN_PASSWORD=tu-password-super-seguro
ADMIN_FIRST_NAME=Admin
ADMIN_LAST_NAME=User

# Seguridad
SECURE_SSL_REDIRECT=False

# CSRF Trusted Origins (requerido para Cloudflare Tunnel)
# Formato: https://tu-dominio.com,https://otro-dominio.com
CSRF_TRUSTED_ORIGINS=https://tu-dominio.com
```

### 3. Construir y ejecutar con Docker Compose

```bash
# Construir las imágenes
docker compose build

# Iniciar los servicios
docker compose up -d

# Ver los logs
docker compose logs -f web
```

### 4. Acceder a la aplicación

- **Interfaz Web**: http://localhost
- **Admin Django**: http://localhost/admin
- **API REST**: http://localhost/api/prospects/

**Credenciales por defecto** (si no configuras las variables de entorno):
- Email: `admin@admin.com`
- Password: `changeme123456`

⚠️ **IMPORTANTE**: Configura `ADMIN_EMAIL` y `ADMIN_PASSWORD` en tu archivo `.env` antes de desplegar en producción.

## 🌐 Despliegue en AWS EC2

### Paso 1: Configurar la instancia EC2

1. Lanzar una instancia EC2 (recomendado: Ubuntu 22.04 LTS, t3.small o superior)
2. Configurar el Security Group:
   - Puerto 22 (SSH) - Solo tu IP
   - Puerto 80 (HTTP) - Abierto (0.0.0.0/0)
   - Puerto 443 (HTTPS) - Abierto (0.0.0.0/0) si usas SSL

### Paso 2: Conectar y preparar el servidor

```bash
# Conectar por SSH
ssh -i tu-clave.pem ubuntu@tu-ip-ec2

# Actualizar el sistema
sudo apt update && sudo apt upgrade -y

# Instalar Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu

# Docker Compose V2 viene integrado con Docker (no necesita instalación separada)
# Verificar instalación
docker --version
docker compose version

# Cerrar sesión y volver a conectar para aplicar cambios de grupo
exit
```

### Paso 3: Clonar y configurar el proyecto

```bash
# Reconectar por SSH
ssh -i tu-clave.pem ubuntu@tu-ip-ec2

# Clonar el proyecto
git clone <tu-repositorio>
cd soynadia

# Crear y configurar .env
nano .env
```

Configuración de producción para `.env`:

```env
# Django
SECRET_KEY=genera-una-key-super-segura-aqui-con-50-caracteres
DEBUG=False
ALLOWED_HOSTS=tu-ip-ec2,tu-dominio.com

# Base de datos
POSTGRES_DB=soynadia_prod
POSTGRES_USER=soynadia_user
POSTGRES_PASSWORD=password-super-seguro-cambiar
DB_EXTERNAL_PORT=5432

# Superusuario (CAMBIAR ESTOS VALORES)
ADMIN_EMAIL=admin@tuempresa.com
ADMIN_PASSWORD=UnPasswordMuySeguro123!@#
ADMIN_FIRST_NAME=Administrador
ADMIN_LAST_NAME=Principal

# Seguridad
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

# CSRF Trusted Origins (CRÍTICO para Cloudflare Tunnel)
# Usa tu dominio de Cloudflare con https://
CSRF_TRUSTED_ORIGINS=https://soynadia.tu-dominio.com
```

**Generar SECRET_KEY**:
```bash
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### Paso 4: Desplegar la aplicación

```bash
# Construir e iniciar
docker compose up -d --build

# Ver el estado
docker compose ps

# Ver logs
docker compose logs -f web
```

### Paso 5: Verificar el despliegue

Visita: `http://tu-ip-ec2` o `http://tu-dominio.com`

### Paso 6: Configurar Auto-inicio al Reiniciar (Opcional pero Recomendado)

Para que los contenedores se inicien automáticamente cuando se reinicie el servidor:

**Método 1: Script Automático (Recomendado)**

```bash
# Ejecutar el script de configuración automática
./SETUP_AUTO_START.sh
```

El script automáticamente:
- Detecta la ruta del proyecto
- Configura el usuario actual
- Encuentra docker compose
- Crea y habilita el servicio systemd

**Método 2: Configuración Manual**

```bash
# Copiar el archivo de servicio systemd
sudo cp soynadia-docker.service /etc/systemd/system/

# Ajustar la ruta si es necesario (editar el archivo)
sudo nano /etc/systemd/system/soynadia-docker.service
# Asegúrate de que WorkingDirectory apunte a la ruta correcta de tu proyecto
# Ejemplo: WorkingDirectory=/home/ubuntu/soynadia

# Recargar systemd
sudo systemctl daemon-reload

# Habilitar el servicio para que inicie automáticamente
sudo systemctl enable soynadia-docker.service

# Iniciar el servicio ahora
sudo systemctl start soynadia-docker.service

# Verificar el estado
sudo systemctl status soynadia-docker.service

# Ver los logs del servicio
sudo journalctl -u soynadia-docker.service -f
```

**Verificar que funciona:**
```bash
# Reiniciar el servidor
sudo reboot

# Después de reiniciar, verificar que los contenedores están corriendo
docker compose ps
```

**Comandos útiles del servicio:**
```bash
# Detener los contenedores
sudo systemctl stop soynadia-docker.service

# Iniciar los contenedores
sudo systemctl start soynadia-docker.service

# Reiniciar los contenedores
sudo systemctl restart soynadia-docker.service

# Deshabilitar auto-inicio (si ya no lo necesitas)
sudo systemctl disable soynadia-docker.service

# Ver estado del servicio
sudo systemctl status soynadia-docker.service
```

## ☁️ Despliegue con Cloudflare Tunnel

Cloudflare Tunnel permite exponer tu aplicación de forma segura sin abrir puertos en el firewall.

### Configuración para Cloudflare Tunnel

#### 1. Instalar Cloudflare Tunnel

```bash
# En tu servidor EC2
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb
```

#### 2. Autenticar Cloudflare Tunnel

```bash
cloudflared tunnel login
```

Esto abrirá tu navegador para autenticarte con Cloudflare.

#### 3. Crear un Tunnel

```bash
cloudflared tunnel create soynadia
```

Esto creará un archivo de configuración en `~/.cloudflared/config.yml`.

#### 4. Configurar el Tunnel

Edita `~/.cloudflared/config.yml`:

```yaml
tunnel: <tu-tunnel-id>
credentials-file: /home/ubuntu/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: soynadia.tu-dominio.com
    service: http://localhost:80
  - service: http_status:404
```

#### 5. Configurar Variables de Entorno

Actualiza tu archivo `.env` con las configuraciones para Cloudflare:

```env
# Django
SECRET_KEY=tu-secret-key-super-segura
DEBUG=False
ALLOWED_HOSTS=soynadia.tu-dominio.com,localhost,127.0.0.1

# CSRF Trusted Origins (CRÍTICO para Cloudflare Tunnel)
# Usa el dominio de Cloudflare, no la IP
CSRF_TRUSTED_ORIGINS=https://soynadia.tu-dominio.com

# Seguridad (Cloudflare maneja SSL, pero Django debe saberlo)
SECURE_SSL_REDIRECT=False  # Cloudflare maneja SSL
SECURE_PROXY_SSL_HEADER=HTTP_CF_VISITOR,{"scheme":"https"}
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

#### 6. Exponer Base de Datos (Opcional)

Si necesitas acceso externo a PostgreSQL, configura el puerto en `.env`:

```env
# Puerto externo para PostgreSQL (ajusta según necesites)
DB_EXTERNAL_PORT=5432
```

Y en `docker compose.yml` ya está configurado para exponer el puerto.

**⚠️ IMPORTANTE**: Si expones PostgreSQL, asegúrate de:
- Usar contraseñas fuertes
- Restringir acceso por IP en el Security Group de AWS
- Considerar usar Cloudflare Tunnel también para la base de datos

#### 7. Iniciar el Tunnel

```bash
# Ejecutar como servicio
sudo cloudflared service install
sudo systemctl start cloudflared
sudo systemctl enable cloudflared
```

#### 8. Verificar el Despliegue

Visita: `https://soynadia.tu-dominio.com`

### Configuración de Nginx para Cloudflare

El archivo `nginx.conf` ya está configurado para trabajar con proxies reversos. Cloudflare enviará headers especiales que Django debe reconocer.

### Headers de Cloudflare

Cloudflare envía estos headers que Django puede usar:
- `CF-Visitor`: Indica si la conexión original era HTTPS
- `X-Forwarded-For`: IP del cliente original
- `X-Forwarded-Proto`: Protocolo original (https)

### Troubleshooting Cloudflare Tunnel

1. **Error CSRF**: Asegúrate de que `CSRF_TRUSTED_ORIGINS` incluya tu dominio de Cloudflare con `https://`
2. **Sesiones no funcionan**: Verifica que `SESSION_COOKIE_SECURE=True` y `CSRF_COOKIE_SECURE=True`
3. **Base de datos no accesible**: Verifica que el puerto esté expuesto y el Security Group permita conexiones

### Ventajas de Cloudflare Tunnel

- ✅ No necesitas abrir puertos en el firewall
- ✅ SSL/TLS automático
- ✅ Protección DDoS incluida
- ✅ CDN global
- ✅ Acceso seguro sin VPN
- ✅ Fácil de configurar

## 👤 Gestión de Usuarios

### Crear un superusuario adicional

```bash
docker compose exec web python manage.py createsuperuser
```

### Cambiar contraseña de usuario

```bash
docker compose exec web python manage.py changepassword admin@soynadia.com
```

## 🔑 Gestión de API Keys

### Crear una API Key

1. **Método 1: Desde Django Admin**
   - Accede a http://tu-dominio.com/admin
   - Ve a "API Keys"
   - Click en "Agregar API Key"
   - Selecciona el usuario y dale un nombre
   - Guarda y copia la key generada

2. **Método 2: Desde la consola**

```bash
docker compose exec web python manage.py shell
```

```python
from voters.models import ApiKey
from users.models import CustomUser

# Obtener o crear usuario
user = CustomUser.objects.get(email='admin@soynadia.com')

# Crear API key
api_key = ApiKey.objects.create(
    user=user,
    name='API Principal'
)

print(f'API Key creada: {api_key.key}')
exit()
```

## 📡 Uso de la API REST

### Autenticación

Todas las peticiones a la API requieren un header de autorización:

```
Authorization: Api-Key tu-api-key-aqui
```

### Endpoints Disponibles

#### 1. Listar Prospectos

```bash
curl -X GET http://tu-dominio.com/api/prospects/ \
  -H "Authorization: Api-Key tu-api-key-aqui"
```

#### 2. Buscar Prospecto por Identificación

```bash
curl -X GET "http://tu-dominio.com/api/prospects/?identification_number=123456" \
  -H "Authorization: Api-Key tu-api-key-aqui"
```

#### 3. Crear Prospecto

```bash
curl -X POST http://tu-dominio.com/api/prospects/ \
  -H "Authorization: Api-Key tu-api-key-aqui" \
  -H "Content-Type: application/json" \
  -d '{
    "identification_number": "1234567890",
    "first_name": "Juan",
    "last_name": "Pérez",
    "phone_number": "3001234567"
  }'
```

#### 4. Obtener Detalle de Prospecto

```bash
curl -X GET http://tu-dominio.com/api/prospects/1/ \
  -H "Authorization: Api-Key tu-api-key-aqui"
```

#### 5. Actualizar Prospecto

```bash
curl -X PUT http://tu-dominio.com/api/prospects/1/ \
  -H "Authorization: Api-Key tu-api-key-aqui" \
  -H "Content-Type: application/json" \
  -d '{
    "identification_number": "1234567890",
    "first_name": "Juan Carlos",
    "last_name": "Pérez García",
    "phone_number": "3009876543"
  }'
```

#### 6. Eliminar Prospecto

```bash
curl -X DELETE http://tu-dominio.com/api/prospects/1/ \
  -H "Authorization: Api-Key tu-api-key-aqui"
```

### Respuestas de la API

#### Éxito (201 Created)

```json
{
  "message": "Prospecto creado exitosamente",
  "data": {
    "id": 1,
    "identification_number": "1234567890",
    "first_name": "Juan",
    "last_name": "Pérez",
    "full_name": "Juan Pérez",
    "phone_number": "3001234567",
    "created_at": "2026-01-21T10:30:00Z",
    "updated_at": "2026-01-21T10:30:00Z",
    "created_by_email": "admin@soynadia.com"
  }
}
```

#### Error (401 Unauthorized)

```json
{
  "detail": "API Key inválida o inactiva"
}
```

#### Error (400 Bad Request)

```json
{
  "identification_number": [
    "Ya existe un prospecto con este número de identificación."
  ]
}
```

## 🛠️ Comandos Útiles

### Docker Compose

```bash
# Ver logs en tiempo real
docker compose logs -f web

# Reiniciar servicios
docker compose restart

# Detener servicios
docker compose down

# Detener y eliminar volúmenes (⚠️ elimina la base de datos)
docker compose down -v

# Ver estado de servicios
docker compose ps

# Reconstruir contenedores
docker compose up -d --build
```

### Django Management

```bash
# Ejecutar migraciones
docker compose exec web python manage.py migrate

# Crear superusuario
docker compose exec web python manage.py createsuperuser

# Colectar archivos estáticos
docker compose exec web python manage.py collectstatic --noinput

# Abrir shell de Django
docker compose exec web python manage.py shell

# Acceder a la base de datos
docker compose exec db psql -U postgres -d soynadia
```

### Backup de Base de Datos

```bash
# Crear backup
docker compose exec db pg_dump -U postgres soynadia > backup_$(date +%Y%m%d_%H%M%S).sql

# Restaurar backup
docker compose exec -T db psql -U postgres soynadia < backup_20260121_103000.sql
```

## 🔒 Seguridad

### Mejores Prácticas Implementadas

1. ✅ Contraseñas hasheadas con Argon2
2. ✅ Validación robusta de contraseñas (mínimo 10 caracteres)
3. ✅ API Key authentication para API REST
4. ✅ CSRF protection en formularios web
5. ✅ Login requerido para todas las vistas de gestión
6. ✅ Números de identificación únicos
7. ✅ Variables de entorno para secretos
8. ✅ HTTPS ready para producción

### Recomendaciones Adicionales para Producción

1. **Configurar HTTPS con Let's Encrypt**:
   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d tu-dominio.com
   ```

2. **Configurar firewall**:
   ```bash
   sudo ufw allow 22/tcp
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw enable
   ```

3. **Backups automáticos**:
   - Configura backups diarios de la base de datos
   - Usa AWS S3 para almacenar backups

4. **Monitoreo**:
   - Configura CloudWatch para monitorear recursos
   - Implementa logs centralizados

## 📁 Estructura del Proyecto

```
soynadia/
├── Dockerfile                      # Configuración de Docker
├── docker compose.yml              # Orquestación de servicios
├── nginx.conf                      # Configuración de Nginx
├── supervisord.conf                # Configuración de Supervisor
├── entrypoint.sh                   # Script de inicialización
├── requirements.txt                # Dependencias Python
├── .env.example                    # Plantilla de variables de entorno
├── .gitignore                      # Archivos ignorados por Git
├── README.md                       # Este archivo
├── manage.py                       # Script de gestión Django
├── soynadia/                       # Proyecto Django
│   ├── settings.py                 # Configuración principal
│   ├── urls.py                     # URLs principales
│   ├── wsgi.py                     # WSGI para Gunicorn
│   └── asgi.py                     # ASGI (futuro)
├── users/                          # App de usuarios
│   ├── models.py                   # CustomUser
│   ├── managers.py                 # CustomUserManager
│   ├── admin.py                    # Admin personalizado
│   ├── forms.py                    # LoginForm
│   ├── views.py                    # Login/Logout
│   └── urls.py                     # URLs de autenticación
├── voters/                         # App de prospectos
│   ├── models.py                   # Prospect, ApiKey
│   ├── admin.py                    # Admin de prospectos
│   ├── forms.py                    # ProspectForm
│   ├── views.py                    # Vistas web CRUD
│   ├── api_views.py                # API ViewSet
│   ├── serializers.py              # DRF Serializers
│   ├── authentication.py           # ApiKeyAuthentication
│   ├── urls.py                     # URLs web
│   └── api_urls.py                 # URLs de API
└── templates/                      # Templates HTML
    ├── base.html                   # Template base
    ├── users/
    │   └── login.html              # Login
    └── voters/
        ├── dashboard.html          # Dashboard
        ├── prospect_list.html      # Lista de prospectos
        ├── prospect_form.html      # Formulario
        ├── prospect_detail.html    # Detalle
        └── prospect_confirm_delete.html  # Confirmación
```

## 🐛 Solución de Problemas

### El contenedor no inicia

```bash
# Ver logs detallados
docker compose logs web

# Verificar configuración de base de datos
docker compose exec db psql -U postgres -c "\l"
```

### Error de permisos en entrypoint.sh

```bash
chmod +x entrypoint.sh
docker compose up -d --build
```

### No se pueden colectar archivos estáticos

```bash
docker compose exec web python manage.py collectstatic --noinput --clear
```

### La base de datos no se conecta

1. Verificar que el servicio de base de datos esté corriendo:
   ```bash
   docker compose ps
   ```

2. Verificar las variables de entorno en `.env`

3. Reiniciar los servicios:
   ```bash
   docker compose restart
   ```

## 📝 Licencia

Este proyecto es privado y confidencial.

## 👥 Soporte

Para soporte, contacta al administrador del sistema.

---

**Desarrollado con ❤️ usando Django, PostgreSQL, Docker y Tailwind CSS**