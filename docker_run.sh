#!/bin/bash

# Script unificado para construir y ejecutar el contenedor Docker del code assessment
# Soporta múltiples ambientes: local, development, production

set -e

# Valores por defecto
ENVIRONMENT="local"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Función de ayuda
show_help() {
    cat << EOF
Uso: ./docker_run.sh [OPTIONS]

Construye y ejecuta el contenedor Docker del code assessment para el ambiente especificado.

Opciones:
    --env=ENVIRONMENT    Ambiente a usar: local, development, production (default: local)
    --skip-build        Omitir la construcción de la imagen
    -h, --help          Muestra esta ayuda

Ejemplos:
    ./docker_run.sh                      # Construye y ejecuta en ambiente local
    ./docker_run.sh --env=development    # Construye y ejecuta en desarrollo
    ./docker_run.sh --env=production     # Construye y ejecuta en producción
    ./docker_run.sh --skip-build         # Solo ejecuta sin construir
EOF
}

# Parsear argumentos
SKIP_BUILD=false
for arg in "$@"; do
    case $arg in
        --env=*)
            ENVIRONMENT="${arg#*=}"
            shift
            ;;
        --skip-build)
            SKIP_BUILD=true
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

# Validar ambiente
if [[ ! "$ENVIRONMENT" =~ ^(local|development|production)$ ]]; then
    echo "Error: Ambiente '$ENVIRONMENT' no válido. Usa: local, development, o production"
    exit 1
fi

# Cargar variables de entorno desde la carpeta del proyecto
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

# Cargar variables
source "$ENV_FILE"

echo "=========================================="
echo "Code Assessment - Ambiente: $ENVIRONMENT"
echo "=========================================="

# PASO 1: Construir imagen
if [ "$SKIP_BUILD" = false ]; then
    echo ""
    echo "📦 PASO 1/2: Construyendo imagen..."
    echo "Imagen: $IMAGE_TAG"
    echo "=========================================="
    
    docker build \
        --build-arg ENVIRONMENT="$ENVIRONMENT" \
        -t "$IMAGE_TAG" \
        .
    
    echo "✓ Imagen construida exitosamente"
else
    echo "⏭️  Omitiendo construcción de imagen"
fi

# PASO 2: Ejecutar contenedor
echo ""
echo "🚀 PASO 2/2: Ejecutando contenedor..."
echo "Contenedor: $CONTAINER_NAME"
echo "Puerto interno: $PORT"
[ -n "$EXTERNAL_PORT" ] && echo "Puerto externo: $EXTERNAL_PORT"
echo "Red: $DOCKER_NETWORK"
echo "Debug: $DEBUG"
echo "=========================================="

# Verificar si la red existe, si no, crearla
if ! docker network inspect "$DOCKER_NETWORK" &> /dev/null; then
    echo "Creando red Docker: $DOCKER_NETWORK"
    docker network create "$DOCKER_NETWORK"
fi

# Detener y eliminar contenedor existente si existe
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Deteniendo contenedor existente..."
    docker stop "$CONTAINER_NAME" || true
    docker rm "$CONTAINER_NAME" || true
fi

# Solo exponer puerto si EXTERNAL_PORT está definido
if [ -n "$EXTERNAL_PORT" ]; then
    PORT_ARG="-p ${EXTERNAL_PORT}:${PORT}"
else
    PORT_ARG=""
fi

# Ejecutar contenedor
docker run -d \
    $PORT_ARG \
    --network "$DOCKER_NETWORK" \
    --name "$CONTAINER_NAME" \
    -e HOST="$HOST" \
    -e PORT="$PORT" \
    -e DEBUG="$DEBUG" \
    -e SESSION_BASE_PATH="$SESSION_BASE_PATH" \
    -e SESSION_TTL_MINUTES="$SESSION_TTL_MINUTES" \
    -e CLEANUP_INTERVAL_MINUTES="$CLEANUP_INTERVAL_MINUTES" \
    -e CORS_ORIGINS="$CORS_ORIGINS" \
    "$IMAGE_TAG"

echo ""
echo "=========================================="
echo "✅ COMPLETADO - Code Assessment corriendo"
echo "=========================================="
echo "Ambiente: $ENVIRONMENT"
[ -n "$EXTERNAL_PORT" ] && echo "Acceso: http://localhost:$EXTERNAL_PORT"
echo "Contenedor: $CONTAINER_NAME"
echo "=========================================="