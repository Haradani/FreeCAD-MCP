#!/bin/bash
set -e

# Ensure model directories exist
mkdir -p /app/ComfyUI/models/checkpoints
mkdir -p /app/ComfyUI/models/loras
mkdir -p /app/ComfyUI/models/vae
mkdir -p /app/ComfyUI/models/clip
mkdir -p /app/ComfyUI/models/controlnet
mkdir -p /app/ComfyUI/models/embeddings
mkdir -p /app/ComfyUI/models/diffusion_models
mkdir -p /app/ComfyUI/models/text_encoders

# Link storage directories if they exist and have content
if [ -d "/storage/models/checkpoints" ]; then
    for f in /storage/models/checkpoints/*; do
        [ -e "$f" ] && ln -sf "$f" /app/ComfyUI/models/checkpoints/ 2>/dev/null || true
    done
fi

if [ -d "/storage/models/loras" ]; then
    for f in /storage/models/loras/*; do
        [ -e "$f" ] && ln -sf "$f" /app/ComfyUI/models/loras/ 2>/dev/null || true
    done
fi

if [ -d "/storage/models/vae" ]; then
    for f in /storage/models/vae/*; do
        [ -e "$f" ] && ln -sf "$f" /app/ComfyUI/models/vae/ 2>/dev/null || true
    done
fi

if [ -d "/storage/models/unet" ]; then
    for f in /storage/models/unet/*; do
        [ -e "$f" ] && ln -sf "$f" /app/ComfyUI/models/diffusion_models/ 2>/dev/null || true
    done
fi

if [ -d "/storage/models/clip" ]; then
    for f in /storage/models/clip/*; do
        [ -e "$f" ] && ln -sf "$f" /app/ComfyUI/models/text_encoders/ 2>/dev/null || true
    done
fi

# Link output directory
if [ -d "/storage/outputs" ]; then
    rm -rf /app/ComfyUI/output
    ln -sf /storage/outputs /app/ComfyUI/output
fi

# Link input directory
if [ -d "/storage/inputs" ]; then
    rm -rf /app/ComfyUI/input
    ln -sf /storage/inputs /app/ComfyUI/input
fi

echo "ComfyUI Diffusion Server"
echo "========================"
echo "GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'Not available')"
echo ""

echo "Starting ComfyUI..."
exec python main.py "$@"
