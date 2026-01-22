#!/bin/bash

# Script para configurar el auto-inicio de Docker Compose
# Uso: ./SETUP_AUTO_START.sh

set -e

echo "🚀 Configurando auto-inicio de SoyNadia Docker Compose..."

# Obtener la ruta actual del proyecto
PROJECT_DIR=$(pwd)
SERVICE_FILE="soynadia-docker.service"
SYSTEMD_PATH="/etc/systemd/system/soynadia-docker.service"

# Verificar que estamos en el directorio correcto
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Error: No se encontró docker-compose.yml"
    echo "   Asegúrate de ejecutar este script desde el directorio del proyecto"
    exit 1
fi

# Verificar que el archivo de servicio existe
if [ ! -f "$SERVICE_FILE" ]; then
    echo "❌ Error: No se encontró $SERVICE_FILE"
    exit 1
fi

# Copiar el archivo de servicio
echo "📋 Copiando archivo de servicio systemd..."
sudo cp "$SERVICE_FILE" "$SYSTEMD_PATH"

# Actualizar la ruta en el archivo de servicio
echo "🔧 Configurando ruta del proyecto: $PROJECT_DIR"
sudo sed -i "s|WorkingDirectory=.*|WorkingDirectory=$PROJECT_DIR|g" "$SYSTEMD_PATH"

# Verificar que docker está instalado
if ! command -v docker &> /dev/null; then
    echo "❌ Error: docker no está instalado"
    exit 1
fi

# Verificar que docker compose está disponible
if ! docker compose version &> /dev/null; then
    echo "❌ Error: docker compose no está disponible"
    echo "   Asegúrate de tener Docker Compose V2 instalado"
    exit 1
fi

DOCKER_PATH=$(which docker)
echo "🔧 Configurando ruta de docker: $DOCKER_PATH"
sudo sed -i "s|ExecStart=.*|ExecStart=$DOCKER_PATH compose up -d|g" "$SYSTEMD_PATH"
sudo sed -i "s|ExecStop=.*|ExecStop=$DOCKER_PATH compose down|g" "$SYSTEMD_PATH"

# Obtener el usuario actual
CURRENT_USER=$(whoami)
echo "🔧 Configurando usuario: $CURRENT_USER"
sudo sed -i "s|User=.*|User=$CURRENT_USER|g" "$SYSTEMD_PATH"

# Recargar systemd
echo "🔄 Recargando systemd..."
sudo systemctl daemon-reload

# Habilitar el servicio
echo "✅ Habilitando servicio para auto-inicio..."
sudo systemctl enable soynadia-docker.service

# Iniciar el servicio
echo "🚀 Iniciando servicio..."
sudo systemctl start soynadia-docker.service

# Verificar estado
echo ""
echo "📊 Estado del servicio:"
sudo systemctl status soynadia-docker.service --no-pager -l

echo ""
echo "✅ ¡Configuración completada!"
echo ""
echo "📝 Comandos útiles:"
echo "   Ver estado:     sudo systemctl status soynadia-docker.service"
echo "   Ver logs:       sudo journalctl -u soynadia-docker.service -f"
echo "   Reiniciar:      sudo systemctl restart soynadia-docker.service"
echo "   Detener:        sudo systemctl stop soynadia-docker.service"
echo "   Deshabilitar:   sudo systemctl disable soynadia-docker.service"
echo ""
echo "🧪 Para probar, reinicia el servidor:"
echo "   sudo reboot"
echo "   # Después de reiniciar, verifica con: docker compose ps"
