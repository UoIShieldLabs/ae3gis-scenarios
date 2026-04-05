#!/bin/bash
# ============================================================
# AE3GIS Container Build Script
# ============================================================
# Usage:
#   ./build.sh                    # Build all images locally
#   ./build.sh --push <username>  # Build and push to DockerHub
#
# Automatically detects if you're on Apple Silicon and builds
# for linux/amd64 so images run on your Linux AE3GIS host.
# ============================================================

set -e

PUSH=false
DOCKERHUB_USER=""

if [ "$1" = "--push" ]; then
    PUSH=true
    DOCKERHUB_USER="${2:?Usage: ./build.sh --push <dockerhub-username>}"
fi

IMAGES=(
    "aegis-workstation:workstation"
    "aegis-webserver:webserver"
    "aegis-dns:dns"
    "aegis-ftp:ftp"
    "aegis-database:database"
    "aegis-zeek:zeek"
)

# ---- Detect architecture ----
HOST_ARCH="$(uname -m)"
TARGET_PLATFORM="linux/amd64"

if [ "$HOST_ARCH" = "arm64" ] || [ "$HOST_ARCH" = "aarch64" ]; then
    echo "Detected ARM architecture ($HOST_ARCH)."
    echo "Will cross-build for $TARGET_PLATFORM."
    CROSS_BUILD=true

    # Ensure buildx builder exists
    if ! docker buildx inspect aegis-builder > /dev/null 2>&1; then
        echo "Creating buildx builder 'aegis-builder'..."
        docker buildx create --name aegis-builder --use
        docker buildx inspect --bootstrap
    else
        docker buildx use aegis-builder
    fi
else
    echo "Detected x86_64 architecture. Building natively."
    CROSS_BUILD=false
fi

echo ""
echo "=========================================="
echo " AE3GIS Container Build"
echo " Target platform: $TARGET_PLATFORM"
echo "=========================================="

for entry in "${IMAGES[@]}"; do
    IMAGE_NAME="${entry%%:*}"
    BUILD_DIR="${entry##*:}"

    echo ""
    echo "--- Building $IMAGE_NAME from ./$BUILD_DIR ---"

    if [ "$PUSH" = true ]; then
        FULL_TAG="${DOCKERHUB_USER}/${IMAGE_NAME}:latest"

        if [ "$CROSS_BUILD" = true ]; then
            # buildx: build + push in one step (required for cross-platform)
            docker buildx build \
                --platform "$TARGET_PLATFORM" \
                -t "$FULL_TAG" \
                --push \
                "./$BUILD_DIR"
        else
            docker build -t "$IMAGE_NAME" "./$BUILD_DIR"
            docker tag "$IMAGE_NAME" "$FULL_TAG"
            docker push "$FULL_TAG"
        fi

        echo "--- Pushed $FULL_TAG ---"
    else
        if [ "$CROSS_BUILD" = true ]; then
            # buildx: build and load into local Docker (--load)
            docker buildx build \
                --platform "$TARGET_PLATFORM" \
                -t "$IMAGE_NAME" \
                --load \
                "./$BUILD_DIR"
        else
            docker build -t "$IMAGE_NAME" "./$BUILD_DIR"
        fi
    fi
done

echo ""
echo "=========================================="
echo " Build complete!"
echo "=========================================="

if [ "$PUSH" = true ]; then
    echo ""
    echo "Images pushed to DockerHub under '$DOCKERHUB_USER':"
    for entry in "${IMAGES[@]}"; do
        IMAGE_NAME="${entry%%:*}"
        echo "  ${DOCKERHUB_USER}/${IMAGE_NAME}:latest"
    done
    echo ""
    echo "Use these image names in AE3GIS container properties."
else
    echo ""
    echo "Images built locally:"
    for entry in "${IMAGES[@]}"; do
        IMAGE_NAME="${entry%%:*}"
        echo "  $IMAGE_NAME"
    done
    echo ""
    echo "To push to DockerHub: ./build.sh --push <your-dockerhub-username>"

    if [ "$CROSS_BUILD" = true ]; then
        echo ""
        echo "NOTE: These are linux/amd64 images. They'll run on your Linux"
        echo "host but may be slow under emulation on this Mac."
    fi
fi
