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
- ✅ Soporte para Cloudflare Tunnel (aplicación web + base de datos)

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

# 2Captcha API Key (requerido para consultas de lugar de votación)
# Obtén tu API key en: https://2captcha.com/
# Esta clave se usa para resolver reCAPTCHA al consultar lugares de votación
TWOCAPTCHA_API_KEY=tu-api-key-de-2captcha-aqui
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

# 2Captcha API Key (requerido para consultas de lugar de votación)
# Obtén tu API key en: https://2captcha.com/
# Esta clave se usa para resolver reCAPTCHA al consultar lugares de votación
TWOCAPTCHA_API_KEY=tu-api-key-de-2captcha-aqui
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

**Configuración básica (solo aplicación web):**

```yaml
tunnel: <tu-tunnel-id>
credentials-file: /home/ubuntu/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: soynadia.tu-dominio.com
    service: http://localhost:80
  - service: http_status:404
```

**Configuración completa (aplicación web + PostgreSQL):**

```yaml
tunnel: <tu-tunnel-id>
credentials-file: /home/ubuntu/.cloudflared/<tunnel-id>.json

ingress:
  # Aplicación web Django
  - hostname: soynadia.tu-dominio.com
    service: http://localhost:80
  
  # Base de datos PostgreSQL (opcional, solo si necesitas acceso externo)
  - hostname: db-soynadia.tu-dominio.com
    service: tcp://localhost:5432
    originRequest:
      noHappyEyeballs: true
      tcpKeepAlive: 30s
      connectTimeout: 30s
  
  # Catch-all rule (debe ser el último)
  - service: http_status:404
```

**Nota**: Para PostgreSQL necesitas crear un subdominio adicional en Cloudflare DNS (por ejemplo: `db-soynadia.tu-dominio.com`) que apunte al mismo tunnel.

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

#### 6. Configurar DNS en Cloudflare

Para que el tunnel funcione, necesitas crear registros DNS en Cloudflare:

1. **Para la aplicación web:**
   - Tipo: `CNAME`
   - Nombre: `soynadia` (o el subdominio que prefieras)
   - Contenido: `<tu-tunnel-id>.cfargotunnel.com`
   - Proxy: Activado (nube naranja)

2. **Para PostgreSQL (si lo expones):**
   - Tipo: `CNAME`
   - Nombre: `db-soynadia` (o el subdominio que prefieras)
   - Contenido: `<tu-tunnel-id>.cfargotunnel.com`
   - Proxy: Activado (nube naranja)

**Nota**: El `<tu-tunnel-id>` lo obtienes cuando ejecutas `cloudflared tunnel create soynadia`.

#### 7. Exponer Base de Datos a través de Cloudflare Tunnel

Si necesitas acceso externo a PostgreSQL a través de Cloudflare Tunnel:

**✅ Configuración de Docker (ya está lista):**

El archivo `docker-compose.yml` ya está configurado correctamente:
- PostgreSQL escucha en todas las interfaces (`listen_addresses='*'`)
- El puerto 5432 está mapeado al host (`localhost:5432`)
- No necesitas crear un Dockerfile personalizado para PostgreSQL
- La imagen oficial `postgres:15-alpine` funciona perfectamente

**Configuración en `.env`:**

```env
# No necesitas exponer el puerto directamente si usas Cloudflare Tunnel
# El tunnel manejará la conexión de forma segura
DB_EXTERNAL_PORT=5432  # Solo para referencia, no se expone directamente
```

**Nota sobre Dockerfile:**
- ❌ **NO necesitas** crear un Dockerfile personalizado para PostgreSQL
- ✅ La configuración en `docker-compose.yml` es suficiente
- ✅ PostgreSQL ya está configurado para escuchar en todas las interfaces
- ✅ El mapeo de puertos ya está configurado

**⚠️ IMPORTANTE - Seguridad de PostgreSQL:**

1. **Contraseñas fuertes**: Usa contraseñas muy seguras en `POSTGRES_PASSWORD`
2. **No exponer puerto directamente**: Con Cloudflare Tunnel, NO necesitas abrir el puerto 5432 en el Security Group
3. **Autenticación adicional**: Considera usar Cloudflare Access para agregar autenticación adicional
4. **SSL/TLS**: Cloudflare Tunnel encripta automáticamente la conexión
5. **Restricción de acceso**: Puedes usar Cloudflare Access para limitar quién puede conectarse

**Conectarse a PostgreSQL a través de Cloudflare Tunnel:**

Desde tu máquina local, necesitas usar `cloudflared` como proxy:

```bash
# Instalar cloudflared en tu máquina local (si no lo tienes)
# macOS: brew install cloudflared
# Linux: descargar desde https://github.com/cloudflare/cloudflared/releases
# Windows: descargar desde https://github.com/cloudflare/cloudflared/releases

# Opción 1: Con Cloudflare Access (recomendado, más seguro)
# Esto abrirá tu navegador para autenticarte
cloudflared access tcp --hostname db-soynadia.tu-dominio.com --url localhost:5432

# Opción 2: Sin Cloudflare Access (solo tunnel)
cloudflared tunnel --url tcp://db-soynadia.tu-dominio.com:5432

# En otra terminal, conectarse a PostgreSQL
psql -h localhost -p 5432 -U postgres -d soynadia
```

**Usar un cliente gráfico (DBeaver, pgAdmin, TablePlus, etc.):**

1. **Con Cloudflare Access:**
   ```bash
   # Terminal 1: Iniciar proxy con autenticación
   cloudflared access tcp --hostname db-soynadia.tu-dominio.com --url localhost:5432
   ```
   
   En tu cliente gráfico:
   - Host: `localhost`
   - Puerto: `5432`
   - Usuario: `postgres` (o el que configuraste)
   - Contraseña: La de tu `.env`
   - Base de datos: `soynadia`

2. **Sin Cloudflare Access:**
   ```bash
   # Terminal 1: Iniciar proxy simple
   cloudflared tunnel --url tcp://db-soynadia.tu-dominio.com:5432
   ```
   
   Luego conecta igual que arriba.

**Nota**: El proxy debe estar corriendo mientras uses la conexión a la base de datos.

#### 8. Iniciar el Tunnel

```bash
# Ejecutar como servicio
sudo cloudflared service install
sudo systemctl start cloudflared
sudo systemctl enable cloudflared

# Verificar que el servicio está corriendo
sudo systemctl status cloudflared

# Ver logs del tunnel
sudo journalctl -u cloudflared -f
```

#### 9. Verificar el Despliegue

**Aplicación Web:**
Visita: `https://soynadia.tu-dominio.com`

**Base de Datos (si la expusiste):**
```bash
# Desde tu máquina local, prueba la conexión
cloudflared access tcp --hostname db-soynadia.tu-dominio.com --url localhost:5432
```

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
3. **Base de datos no accesible**:
   - Verifica que el tunnel esté corriendo: `sudo systemctl status cloudflared`
   - Verifica los logs: `sudo journalctl -u cloudflared -f`
   - Asegúrate de que el DNS esté configurado correctamente en Cloudflare
   - Verifica que el servicio PostgreSQL esté corriendo: `docker compose ps db`
4. **Tunnel no inicia**: Verifica que el archivo de credenciales existe y tiene permisos correctos
5. **Error de conexión a PostgreSQL**: Asegúrate de usar `cloudflared access tcp` como proxy local

### Proteger PostgreSQL con Cloudflare Access (Recomendado)

Para agregar una capa adicional de seguridad a PostgreSQL, puedes usar Cloudflare Access:

1. **Instalar Cloudflare Access en tu máquina local:**
   ```bash
   # macOS
   brew install cloudflared
   
   # Linux
   # Descargar desde https://github.com/cloudflare/cloudflared/releases
   ```

2. **Configurar Cloudflare Access en el Dashboard:**
   - Ve a Cloudflare Dashboard → Zero Trust → Access → Applications
   - Crea una nueva aplicación para `db-soynadia.tu-dominio.com`
   - Configura políticas de acceso (email, IP, etc.)
   - Guarda la configuración

3. **Conectarse con autenticación:**
   ```bash
   # Esto abrirá tu navegador para autenticarte
   cloudflared access tcp --hostname db-soynadia.tu-dominio.com --url localhost:5432
   
   # Luego conecta normalmente
   psql -h localhost -p 5432 -U postgres -d soynadia
   ```

### Ventajas de Cloudflare Tunnel

- ✅ No necesitas abrir puertos en el firewall
- ✅ SSL/TLS automático para aplicación web y base de datos
- ✅ Protección DDoS incluida
- ✅ CDN global para la aplicación web
- ✅ Acceso seguro sin VPN
- ✅ Fácil de configurar
- ✅ Base de datos accesible de forma segura sin exponer puertos
- ✅ Opción de Cloudflare Access para autenticación adicional

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

## 📱 Webhook WhatsApp Opt-in desde Twilio

### Configuración del Webhook

El sistema incluye un endpoint webhook para recibir mensajes de WhatsApp desde Twilio y gestionar el opt-in mediante plantillas interactivas.

#### 1. Configurar Variables de Entorno

Agrega estas variables al archivo `.env`:

```env
# Autenticación y validación
TWILIO_AUTH_TOKEN=your-twilio-auth-token-here
TWILIO_ACCOUNT_SID=your-twilio-account-sid-here
TWILIO_WHATSAPP_NUMBER=whatsapp:+573001234567

# URL del webhook (obligatoria cuando usas Cloudflare Tunnel)
TWILIO_WEBHOOK_URL=https://tu-dominio.com/webhooks/twilio/whatsapp/

# Plantillas de Twilio para opt-in
TWILIO_OPTIN_TEMPLATE_SID=HXc3259a2a93ad765cb532b2919bc2b1dd
TWILIO_OPTIN_CONFIRMED_TEMPLATE_SID=HXf790520f9af4858389bec0ac00cf0b87
```

**Obtener las credenciales:**
1. Accede a [Twilio Console](https://console.twilio.com/)
2. **Auth Token**: Ve a "Settings" → "General" → Copia el "Auth Token"
3. **Account SID**: Visible en el dashboard principal (formato: `ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`)
4. **WhatsApp Number**: Tu número de WhatsApp Business (formato: `whatsapp:+573001234567`)

**TWILIO_WEBHOOK_URL:** Debe ser la URL **exacta** del webhook tal como está en Twilio Console (mismo protocolo, dominio, path y trailing slash). Si usas Cloudflare Tunnel, la validación de firma falla si construyes la URL desde los headers (Nginx recibe HTTP del tunnel); en ese caso **debes** definir `TWILIO_WEBHOOK_URL` en `.env`.

#### 2. Configurar Webhook en Twilio Console

**Para WhatsApp Sandbox (Desarrollo/Pruebas):**

1. Accede a [Twilio Console](https://console.twilio.com/)
2. Ve a **Messaging** → **Try it out** → **Send a WhatsApp message**
3. En la sección **"Sandbox configuration"**, haz clic en **"Configure"**
4. En **"When a message comes in"**, configura:
   - **URL**: `https://tu-dominio.com/webhooks/twilio/whatsapp/`
   - **HTTP Method**: `POST`
5. Guarda los cambios

**Para WhatsApp Business API (Producción):**

1. Accede a [Twilio Console](https://console.twilio.com/)
2. Ve a **Messaging** → **Settings** → **WhatsApp Senders**
3. Selecciona tu número de WhatsApp Business
4. En **"Webhook URL"**, configura:
   - **URL**: `https://tu-dominio.com/webhooks/twilio/whatsapp/`
   - **HTTP Method**: `POST`
5. Guarda los cambios

#### 3. Endpoint del Webhook

El webhook está disponible en:
```
POST https://tu-dominio.com/webhooks/twilio/whatsapp/
```

**Características:**
- Validación de firma de Twilio (requiere `TWILIO_AUTH_TOKEN`)
- Almacenamiento automático de todos los mensajes en `WhatsAppMessage` (relacionados por número de teléfono normalizado)
- Gestión de opt-in/opt-out mediante `WhatsAppAccount` (independiente de Prospect)
- Flujo automático de opt-in con plantillas de Twilio:
  - **Primera vez**: Si un usuario escribe por primera vez (no existe `WhatsAppAccount` para ese número), se envía automáticamente la plantilla de opt-in (`TWILIO_OPTIN_TEMPLATE_SID`)
  - **Respuesta SI**: Si el usuario responde "SI" al quick reply, se marca `optin_whatsapp = True` y se envía la plantilla de confirmación (`TWILIO_OPTIN_CONFIRMED_TEMPLATE_SID`)
  - **Respuesta NO**: Si el usuario responde "NO", se marca `optout_whatsapp = True`
- Extracción del número del remitente: se quita el prefijo `whatsapp:` y el **prefijo de país correspondiente** (+57, +1, +52, etc.), ya que no siempre son números colombianos
- Respuesta TwiML válida para Twilio

#### 4. Flujo de Opt-in con Plantillas

El sistema implementa un flujo automático de opt-in mediante plantillas de Twilio:

1. **Primera vez que un usuario escribe:**
   - El sistema detecta que no existe un `WhatsAppAccount` para ese número de teléfono
   - Se envía automáticamente la plantilla de opt-in (`TWILIO_OPTIN_TEMPLATE_SID`)
   - Esta plantilla debe ser un quick reply con opciones "SI" y "NO"

2. **Usuario responde "SI":**
   - El sistema detecta la respuesta del quick reply (campo `ButtonText` o `ButtonPayload`)
   - Se crea o actualiza el `WhatsAppAccount` con `optin_whatsapp = True` y `optout_whatsapp = False`
   - Se envía automáticamente la plantilla de confirmación (`TWILIO_OPTIN_CONFIRMED_TEMPLATE_SID`)

3. **Usuario responde "NO":**
   - El sistema detecta la respuesta del quick reply
   - Se crea o actualiza el `WhatsAppAccount` con `optin_whatsapp = False` y `optout_whatsapp = True`
   - No se envía ninguna plantilla adicional

**Nota:** El estado de opt-in/opt-out se almacena en `WhatsAppAccount`, que está relacionado **solo por número de teléfono** (no por Prospect). Esto permite gestionar el opt-in incluso si no existe un Prospect para ese número.

#### 5. Tipos de Eventos Detectados

El sistema detecta automáticamente el tipo de evento basado en el contenido del mensaje:

**Opt-in:** Mensajes que contengan: `START`, `SI`, `YES`, `UNIRSE`, `ACTIVAR`, `SUBSCRIBIR`, `SUBSCRIBE`

**Opt-out:** Mensajes que contengan: `STOP`, `NO`, `CANCELAR`, `DESACTIVAR`, `UNSUBSCRIBE`, `SALIR`

**Mensaje:** Cualquier otro contenido

#### 6. Ver Mensajes y Cuentas de WhatsApp

Los mensajes y cuentas se pueden ver y gestionar desde:
- **Django Admin**: 
  - `/admin/voters/whatsappmessage/` - Todos los mensajes recibidos
  - `/admin/voters/whatsappaccount/` - Estados de opt-in/opt-out por número de teléfono
- Los registros incluyen:
  - Número de teléfono normalizado
  - Tipo de evento
  - Estado de opt-in/opt-out (en `WhatsAppAccount`)
  - Datos completos recibidos de Twilio (en `WhatsAppMessage`)

#### 6. Seguridad

- El webhook valida la firma de Twilio usando `RequestValidator`
- Si `TWILIO_AUTH_TOKEN` no está configurado, el webhook funciona pero sin validación de firma (no recomendado para producción)
- Si `TWILIO_WEBHOOK_URL` está definida, se usa tal cual para validar la firma; si no, se construye desde la petición (Host, X-Forwarded-*, path). Con Cloudflare Tunnel, **define `TWILIO_WEBHOOK_URL`** para que la URL coincida con Twilio.
- El endpoint es público pero protegido por validación de firma
- Para debugging temporal, puedes deshabilitar la validación con `TWILIO_SKIP_SIGNATURE_VALIDATION=true` (NO recomendado para producción)

#### 7.1. Troubleshooting Error 403

Si recibes un error 403 al configurar el webhook:

**1. Verificar que el endpoint sea accesible:**
```bash
curl -X POST https://tu-dominio.com/webhooks/twilio/whatsapp/ \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "MessageSid=test&AccountSid=test&From=test"
```

**2. Verificar logs de Django (Gunicorn):**
```bash
docker compose exec web tail -f /var/log/supervisor/gunicorn.log | grep -E '\[Twilio\]|webhook'
```

**3. Si usas Cloudflare Tunnel:**
- Asegúrate de que el dominio esté en `ALLOWED_HOSTS` en `.env`
- Verifica que `CSRF_TRUSTED_ORIGINS` incluya tu dominio con `https://`
- El webhook usa `@csrf_exempt` pero puede haber otros middlewares bloqueando

**4. Validación de firma:**
- Si la validación de firma falla, verifica que `TWILIO_AUTH_TOKEN` sea correcto
- **Con Cloudflare Tunnel:** define `TWILIO_WEBHOOK_URL` en `.env` con la URL exacta de Twilio (ej. `https://app.deikore.com/webhooks/twilio/whatsapp/`). Sin ella, la URL se construye como `http://...` y la validación falla.
- En desarrollo, puedes temporalmente deshabilitar la validación:
  ```env
  TWILIO_SKIP_SIGNATURE_VALIDATION=true
  ```
- Verifica los logs (`docker compose exec web tail -f /var/log/supervisor/gunicorn.log`) para ver la URL usada, "Firma INVÁLIDA", etc.

**5. Verificar configuración en Twilio:**
- Asegúrate de que la URL del webhook en Twilio sea exactamente: `https://tu-dominio.com/webhooks/twilio/whatsapp/`
- Verifica que el método HTTP sea `POST`
- La URL debe ser accesible públicamente (no localhost)

**6. Si usas Cloudflare Tunnel y recibes 403 (página "Attention Required!"):**

El error "Attention Required! | Cloudflare" significa que Cloudflare está bloqueando la petición antes de llegar a Django. Esto es un problema de configuración de Cloudflare, no de Django.

**Solución: Configurar reglas de Firewall en Cloudflare**

1. **Accede a Cloudflare Dashboard:**
   - Ve a tu dominio en [Cloudflare Dashboard](https://dash.cloudflare.com/)
   - Navega a **Security** → **WAF** → **Custom Rules**

2. **Crear una regla para permitir el webhook de Twilio:**
   
   **Opción A: Permitir por User-Agent (Recomendado)**
   - Crea una nueva regla con esta configuración:
     - **Rule name**: `Allow Twilio Webhook`
     - **When incoming requests match**: 
       ```
       (http.request.uri.path eq "/webhooks/twilio/whatsapp/")
       and
       (http.user_agent contains "TwilioProxy")
       ```
     - **Then**: `Skip` → Selecciona todos los security checks
     - **Action**: `Skip` (Bypass)

   **Opción B: Permitir por IPs de Twilio (Más seguro)**
   - Twilio usa estas IPs (pueden cambiar, consulta [Twilio IPs](https://www.twilio.com/docs/ips)):
     ```
     54.172.60.0/22
     54.244.51.0/24
     54.171.127.192/26
     ```
   - Crea una regla:
     - **Rule name**: `Allow Twilio IPs`
     - **When incoming requests match**:
       ```
       (ip.src in {54.172.60.0/22 54.244.51.0/24 54.171.127.192/26})
       and
       (http.request.uri.path eq "/webhooks/twilio/whatsapp/")
       ```
     - **Then**: `Skip` → Selecciona todos los security checks

3. **Deshabilitar Bot Protection para el endpoint (Alternativa):**
   - Ve a **Security** → **Bots**
   - Crea una regla de excepción:
     - **Rule name**: `Bypass Bot Check for Twilio Webhook`
     - **Path**: `/webhooks/twilio/whatsapp/`
     - **Action**: `Allow`

4. **Ajustar Security Level temporalmente (Solo para debugging):**
   - Ve a **Security** → **Settings**
   - Cambia **Security Level** a **Medium** o **Low** temporalmente
   - **Nota**: Esto reduce la seguridad general, úsalo solo para verificar que el problema es Cloudflare

5. **Verificar configuración de Django:**
   - Asegúrate de que el dominio esté en `ALLOWED_HOSTS`:
     ```env
     ALLOWED_HOSTS=tu-dominio.cloudflare.com,tu-dominio.com
     ```
   - Verifica `CSRF_TRUSTED_ORIGINS`:
     ```env
     CSRF_TRUSTED_ORIGINS=https://tu-dominio.cloudflare.com,https://tu-dominio.com
     ```

6. **Probar después de configurar:**
   ```bash
   curl -X POST https://tu-dominio.com/webhooks/twilio/whatsapp/ \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -H "User-Agent: TwilioProxy/1.1" \
     -d "MessageSid=test&AccountSid=test&From=test"
   ```

7. **Revisar logs de Cloudflare:**
   - Ve a **Analytics & Logs** → **Security Events**
   - Busca eventos relacionados con `/webhooks/twilio/whatsapp/`
   - Esto te ayudará a identificar qué regla está bloqueando

**Nota importante:** La página "Attention Required!" es la página de desafío de Cloudflare. Si ves esta página, significa que Cloudflare está bloqueando la petición antes de que llegue a tu servidor Django.

#### 8. Ejemplo de Uso

**Flujo completo de opt-in:**

1. **Usuario escribe por primera vez:**
   - Usuario envía cualquier mensaje a tu número de Twilio
   - Twilio envía una petición POST al webhook
   - El sistema valida la firma
   - Extrae el número del remitente (`From`): quita `whatsapp:` y el prefijo de país correspondiente (+57, +1, +52, etc.)
   - Detecta que no existe `WhatsAppAccount` para ese número → es "primera vez"
   - Envía automáticamente la plantilla de opt-in (`TWILIO_OPTIN_TEMPLATE_SID`)
   - Crea el registro en `WhatsAppMessage` con el número normalizado
   - Retorna respuesta TwiML válida

2. **Usuario responde "SI" al quick reply:**
   - Twilio envía la respuesta del botón al webhook
   - El sistema detecta `ButtonText` o `ButtonPayload` con "SI"
   - Crea o actualiza `WhatsAppAccount` con `optin_whatsapp = True`
   - Envía automáticamente la plantilla de confirmación (`TWILIO_OPTIN_CONFIRMED_TEMPLATE_SID`)
   - Crea el registro en `WhatsAppMessage`
   - Retorna respuesta TwiML válida

3. **Usuario responde "NO" al quick reply:**
   - Twilio envía la respuesta del botón al webhook
   - El sistema detecta `ButtonText` o `ButtonPayload` con "NO"
   - Crea o actualiza `WhatsAppAccount` con `optout_whatsapp = True`
   - Crea el registro en `WhatsAppMessage`
   - Retorna respuesta TwiML válida (sin enviar plantilla adicional)

**Modelos de datos:**
- `WhatsAppAccount`: Almacena el estado de opt-in/opt-out por número de teléfono (independiente de Prospect)
- `WhatsAppMessage`: Almacena todos los mensajes recibidos, relacionados por número de teléfono normalizado

## 📄 Formulario embebible (GoDaddy)

Formulario público para registrar prospectos desde una página externa (p. ej. GoDaddy) mediante iframe. Campos obligatorios: **número de identificación**, **nombres**, **apellidos**, **teléfono**.

### URL del formulario

```
https://<tu-dominio>/embed/prospectos/
```

Sustituye `<tu-dominio>` por tu dominio (ej. `app.deikore.com`). El dominio debe estar en `ALLOWED_HOSTS` en tu `.env`.

### Cómo embeber en GoDaddy

1. En tu página de GoDaddy, añade un bloque **HTML** o **Código personalizado**.
2. Pega un iframe como el siguiente (ajusta la URL y el tamaño):

```html
<iframe
  src="https://tu-dominio.com/embed/prospectos/"
  width="100%"
  height="500"
  frameborder="0"
  title="Formulario de registro">
</iframe>
```

3. Se recomienda un ancho mínimo de **400px** y una altura de **500px** o más para que el formulario se vea completo.

Los datos enviados se guardan como prospectos con origen **embed** y pueden consultarse en el dashboard y en el admin de SoyNadia.

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