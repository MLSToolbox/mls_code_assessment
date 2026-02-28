#!/bin/bash

# Script unificado para construir y ejecutar el contenedor Docker del code assessment
# Usa docker compose con bind mount de ./src para evitar rebuilds por cambios de código

set -e

ENVIRONMENT="local"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

show_help() {
    cat << EOF
Uso: ./docker_run.sh [OPTIONS]

Construye y ejecuta el contenedor Docker del code assessment usando docker compose.
El código fuente se monta vía volumen: los cambios en ./src se reflejan automáticamente.

Opciones:
    --env=ENVIRONMENT    Ambiente a usar: local, development, production (default: local)
    --build              Forzar reconstrucción de la imagen (solo necesario si cambian dependencias)
    --restart            Reiniciar el contenedor (útil tras git pull en producción)
    --down               Detener y eliminar el contenedor
    --logs               Ver logs del contenedor
    -h, --help           Muestra esta ayuda

Ejemplos:
    ./docker_run.sh                          # Levanta en ambiente local
    ./docker_run.sh --env=development        # Levanta en desarrollo
    ./docker_run.sh --env=production         # Levanta en producción
    ./docker_run.sh --env=production --build # Reconstruye imagen (si cambiaron dependencias)
    ./docker_run.sh --env=production --restart  # Reinicia tras actualizar código
    ./docker_run.sh --down                   # Detiene el contenedor

Flujo típico en EC2:
    1. Primera vez:  ./docker_run.sh --env=production --build
    2. Actualizar:   git pull && ./docker_run.sh --env=production --restart
    3. Si cambian dependencias: ./docker_run.sh --env=production --build
EOF
}

ACTION="up"
BUILD_FLAG=""
for arg in "$@"; do
    case $arg in
        --env=*)
            ENVIRONMENT="${arg#*=}"
            shift
            ;;
        --build)
            BUILD_FLAG="--build"
            shift
            ;;
        --restart)
            ACTION="restart"
            shift
            ;;
        --down)
            ACTION="down"
            shift
            ;;
        --logs)
            ACTION="logs"
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Error: Argumento desconocido '$arg'"
            show_help
            exit 1
            ;;
    esac
done

if [[ ! "$ENVIRONMENT" =~ ^(local|development|production)$ ]]; then
    echo "Error: Ambiente '$ENVIRONMENT' no válido. Usa: local, development, o production"
    exit 1
fi

ENV_FILE="$SCRIPT_DIR/.env.$ENVIRONMENT"
if [ ! -f "$ENV_FILE" ]; then
    echo "Advertencia: Archivo $ENV_FILE no encontrado."
    echo "Copiando desde .env.$ENVIRONMENT.example..."
    if [ -f "$SCRIPT_DIR/.env.$ENVIRONMENT.example" ]; then
        cp "$SCRIPT_DIR/.env.$ENVIRONMENT.example" "$ENV_FILE"
    else
        echo "Error: No se encuentra .env.$ENVIRONMENT.example"
        exit 1
    fi
fi

echo "=========================================="
echo "Code Assessment - Ambiente: $ENVIRONMENT"
echo "=========================================="

cd "$SCRIPT_DIR"

case $ACTION in
    up)
        echo ""
        echo "Levantando servicio con docker compose..."
        echo "Código fuente montado desde: ./src"
        echo "=========================================="
        docker compose --env-file "$ENV_FILE" up -d $BUILD_FLAG
        echo ""
        echo "=========================================="
        echo "Contenedor corriendo"
        echo "=========================================="
        echo "Ambiente: $ENVIRONMENT"
        echo ""
        echo "Para ver logs:       ./docker_run.sh --env=$ENVIRONMENT --logs"
        echo "Para reiniciar:      ./docker_run.sh --env=$ENVIRONMENT --restart"
        echo "Para detener:        ./docker_run.sh --env=$ENVIRONMENT --down"
        echo "=========================================="
        ;;
    restart)
        echo ""
        echo "Reiniciando contenedor (el código actualizado se recarga)..."
        docker compose --env-file "$ENV_FILE" restart
        echo "Contenedor reiniciado."
        ;;
    down)
        echo ""
        echo "Deteniendo contenedor..."
        docker compose --env-file "$ENV_FILE" down
        echo "Contenedor detenido."
        ;;
    logs)
        docker compose --env-file "$ENV_FILE" logs -f
        ;;
esac
