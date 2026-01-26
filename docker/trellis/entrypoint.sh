#!/bin/bash
set -e

# Ensure storage directories exist
mkdir -p /storage/inputs /storage/outputs /storage/models/huggingface

echo "TRELLIS.2 Image-to-3D Server"
echo "============================"
echo "GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'Not available')"
echo "CUDA: ${CUDA_HOME}"
echo ""

# Pre-download model weights if not present
if [ ! -d "/storage/models/huggingface/hub/models--microsoft--TRELLIS.2-4B" ]; then
    echo "Downloading TRELLIS.2-4B model weights (first run only)..."
    python -c "from huggingface_hub import snapshot_download; snapshot_download('microsoft/TRELLIS.2-4B')" || true
fi

echo "Starting server..."
exec python /app/server.py "$@"
