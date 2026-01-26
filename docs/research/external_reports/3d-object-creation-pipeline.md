# 3D Object Creation Pipeline Technical Report

**Date:** 2026-01-23
**Pipeline Components:** Z-Image Turbo (ComfyUI) + TRELLIS.2
**Infrastructure:** Docker with NVIDIA GPU support

## Overview

This report documents the local 3D object creation pipeline that generates 3D meshes from text prompts. The pipeline consists of two Docker services:

1. **diffusion-gen** (ComfyUI + Z-Image Turbo): Text-to-image generation
2. **image-to-3d** (TRELLIS.2): Image-to-3D mesh conversion

The entire pipeline runs locally on consumer hardware with a 24GB+ NVIDIA GPU.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Text Prompt                                   │
│              "corroded shipping container, rust damage"             │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    diffusion-gen (Port 8188)                        │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  ComfyUI + Z-Image Turbo                                     │   │
│  │  - UNET: z_image_turbo_bf16.safetensors (12.3GB)            │   │
│  │  - CLIP: qwen_3_4b.safetensors (8GB)                        │   │
│  │  - VAE: ae.safetensors (335MB)                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
                    Generated Image (1024x1024)
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    image-to-3d (Port 8000)                          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  TRELLIS.2-4B Pipeline                                       │   │
│  │  - Background removal: camenduru/RMBG-2.0 (ungated mirror)  │   │
│  │  - 3D generation: microsoft/TRELLIS.2-4B                    │   │
│  │  - Output: GLB mesh with PBR textures                       │   │
│  └─────────────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
                    3D Mesh (.glb)
                    - Vertices: ~24K
                    - Faces: ~47K
                    - PBR textures: 2048x2048
```

---

## Critical Fix: RMBG-2.0 Gated Model Workaround

### The Problem

TRELLIS.2 uses `briaai/RMBG-2.0` for background removal before 3D generation. This model is **gated** on HuggingFace, requiring:
1. User acceptance of license terms
2. HuggingFace authentication token
3. Manual approval process

This breaks automated Docker builds and headless operation.

### The Solution

We use `camenduru/RMBG-2.0`, an **ungated mirror** of the same model weights, combined with runtime monkey-patching to handle API compatibility issues with the latest `transformers` library.

### Technical Details

The fix involves three layers of patching in `server.py`:

#### 1. Model Source Replacement
Replace the gated model with the ungated mirror:
```python
def patched_birefnet_init(self, model_name: str = "camenduru/RMBG-2.0"):
    self.model = AutoModelForImageSegmentation.from_pretrained(
        "camenduru/RMBG-2.0",  # Ungated mirror instead of briaai/RMBG-2.0
        trust_remote_code=True,
        device_map=None,
        low_cpu_mem_usage=False,
    )
```

#### 2. Meta Tensor Fix
The transformers main branch has an issue with `torch.linspace` creating tensors on meta device:
```python
original_linspace = torch.linspace
def patched_linspace(*args, **kwargs):
    kwargs['device'] = 'cpu'  # Force CPU to avoid meta tensor issues
    return original_linspace(*args, **kwargs)

torch.linspace = patched_linspace
# ... load model ...
torch.linspace = original_linspace
```

#### 3. PreTrainedModel API Compatibility
The breaking change in transformers main tries to access `all_tied_weights_keys` as both a property and an attribute:
```python
from transformers import PreTrainedModel

# Patch mark_tied_weights_as_initialized
original_mark_tied = PreTrainedModel.mark_tied_weights_as_initialized
def patched_mark_tied_weights(self):
    if not hasattr(self, '_all_tied_weights_keys'):
        object.__setattr__(self, '_all_tied_weights_keys', {})
    return original_mark_tied(self)
PreTrainedModel.mark_tied_weights_as_initialized = patched_mark_tied_weights

# Patch post_init to handle attribute setting
original_post_init = PreTrainedModel.post_init
def patched_post_init(model_self):
    if not hasattr(model_self, '_all_tied_weights_keys'):
        object.__setattr__(model_self, '_all_tied_weights_keys', {})
    if not hasattr(model_self, '_tied_weights_keys'):
        object.__setattr__(model_self, '_tied_weights_keys', [])
    # Temporarily override __setattr__ to intercept all_tied_weights_keys
    original_setattr = type(model_self).__setattr__
    def safe_setattr(self, name, value):
        if name == 'all_tied_weights_keys':
            object.__setattr__(self, '_all_tied_weights_keys', value)
        else:
            original_setattr(self, name, value)
    type(model_self).__setattr__ = safe_setattr
    try:
        original_post_init(model_self)
    finally:
        type(model_self).__setattr__ = original_setattr
PreTrainedModel.post_init = patched_post_init

# Patch __getattr__ for property access
def patched_getattr(self, name):
    if name == 'all_tied_weights_keys':
        return getattr(self, '_all_tied_weights_keys', {})
    raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
PreTrainedModel.__getattr__ = patched_getattr
```

---

## Dockerfiles

### diffusion-gen (ComfyUI)

```dockerfile
# ComfyUI Docker for Diffusion Image Generation
# Based on patterns from https://github.com/YanWenKun/ComfyUI-Docker

FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3-pip \
    git \
    wget \
    curl \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Set Python 3.11 as default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Upgrade pip
RUN python -m pip install --upgrade pip setuptools wheel

# Install PyTorch with CUDA 12.4
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# Create directories
WORKDIR /app
RUN mkdir -p /app/ComfyUI /storage/models /storage/outputs /storage/inputs

# Clone ComfyUI (latest stable release)
RUN git clone https://github.com/comfyanonymous/ComfyUI.git /app/ComfyUI && \
    cd /app/ComfyUI && \
    git fetch --tags && \
    git checkout "$(git tag | grep -e '^v' | sort -V | tail -1)"

# Install ComfyUI dependencies
RUN pip install -r /app/ComfyUI/requirements.txt

# Install ComfyUI-Manager for easy node installation
RUN git clone https://github.com/ltdrdata/ComfyUI-Manager.git /app/ComfyUI/custom_nodes/ComfyUI-Manager && \
    pip install -r /app/ComfyUI/custom_nodes/ComfyUI-Manager/requirements.txt || true

# Install ComfyUI-GGUF for Z-Image Turbo workflow (GGUF model support)
RUN git clone https://github.com/city96/ComfyUI-GGUF.git /app/ComfyUI/custom_nodes/ComfyUI-GGUF && \
    pip install gguf || true

# Create model directory symlinks for easier access
RUN ln -sf /storage/models/checkpoints /app/ComfyUI/models/checkpoints 2>/dev/null || true && \
    ln -sf /storage/models/loras /app/ComfyUI/models/loras 2>/dev/null || true && \
    ln -sf /storage/models/vae /app/ComfyUI/models/vae 2>/dev/null || true

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8188

WORKDIR /app/ComfyUI

ENTRYPOINT ["/entrypoint.sh"]
CMD ["--listen", "0.0.0.0", "--port", "8188"]
```

### image-to-3d (TRELLIS.2)

```dockerfile
# TRELLIS.2 Docker for Image-to-3D Generation
# Based on Microsoft TRELLIS.2: https://github.com/microsoft/TRELLIS.2
# Adapted from HuggingFace transformers Docker patterns

FROM nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV CUDA_HOME=/usr/local/cuda
ENV TORCH_CUDA_ARCH_LIST="7.5;8.0;8.6;8.9;9.0"

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3.10-venv \
    python3.10-dev \
    python3-pip \
    git \
    wget \
    curl \
    ninja-build \
    build-essential \
    cmake \
    libjpeg-dev \
    libpng-dev \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Set Python 3.10 as default (TRELLIS.2 uses 3.10)
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1

# Upgrade pip
RUN python -m pip install --upgrade pip setuptools wheel

# Install PyTorch 2.6.0 with CUDA 12.4 (TRELLIS.2 requirement)
RUN pip install torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124

# Install transformers from main branch (required for DINOv3ViTModel used by TRELLIS.2)
# Note: The camenduru/RMBG-2.0 model compatibility is handled via monkey-patch in server.py
RUN pip install git+https://github.com/huggingface/transformers.git@main

# Install core dependencies
RUN pip install \
    imageio \
    imageio-ffmpeg \
    tqdm \
    easydict \
    opencv-python-headless \
    ninja \
    trimesh \
    gradio==6.0.1 \
    tensorboard \
    pandas \
    lpips \
    zstandard \
    kornia \
    timm \
    pillow-simd \
    huggingface_hub

# Install flash-attn dependencies (psutil required for build)
RUN pip install psutil packaging

# Install flash-attn (required for TRELLIS.2)
RUN pip install flash-attn==2.7.3 --no-build-isolation

# Install utils3d
RUN pip install git+https://github.com/EasternJournalist/utils3d.git

WORKDIR /app

# Clone TRELLIS.2 repository
RUN git clone -b main https://github.com/microsoft/TRELLIS.2.git --recursive /app/trellis2

WORKDIR /app/trellis2

# Install nvdiffrast
RUN pip install git+https://github.com/NVlabs/nvdiffrast.git@v0.4.0 --no-build-isolation

# Install nvdiffrec (renderutils)
RUN pip install git+https://github.com/NVlabs/nvdiffrec.git@renderutils --no-build-isolation || \
    echo "nvdiffrec optional, continuing..."

# Install CuMesh
RUN pip install git+https://github.com/EasternJournalist/cumesh.git --no-build-isolation || \
    echo "cumesh optional, continuing..."

# Install o-voxel from local TRELLIS.2 repo
RUN pip install ./o-voxel --no-build-isolation || \
    echo "o-voxel optional, continuing..."

# Install FlexGEMM (performance optimization)
RUN pip install git+https://github.com/yifan-lu001/FlexGEMM.git --no-build-isolation || \
    echo "flexgemm optional, continuing..."

# TRELLIS.2 is not pip-installable, add to PYTHONPATH instead
ENV PYTHONPATH="/app/trellis2:${PYTHONPATH}"

# Note: The gated briaai/RMBG-2.0 model is replaced with camenduru/RMBG-2.0 at runtime
# See server.py load_pipeline() for the monkey-patch

# Create directories for I/O
RUN mkdir -p /storage/inputs /storage/outputs /storage/models

# Copy server and entrypoint scripts
COPY server.py /app/server.py
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# HuggingFace cache directory
ENV HF_HOME=/storage/models/huggingface
ENV TRANSFORMERS_CACHE=/storage/models/huggingface

EXPOSE 8000

WORKDIR /app

ENTRYPOINT ["/entrypoint.sh"]
CMD ["--host", "0.0.0.0", "--port", "8000"]
```

---

## Server Implementation (server.py)

The complete TRELLIS.2 HTTP server with all patches:

```python
"""
TRELLIS.2 Image-to-3D HTTP Server

Provides REST API for converting images to 3D meshes using Microsoft TRELLIS.2-4B.

Endpoints:
    POST /generate - Convert image to 3D mesh
    GET /health - Health check
    GET /status - Model status and GPU info
"""

import argparse
import io
import json
import logging
import os
import tempfile
import time
import traceback
from pathlib import Path

import torch
from PIL import Image

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Lazy import TRELLIS.2 to avoid loading until needed
pipeline = None


def load_pipeline():
    """Load TRELLIS.2 pipeline (lazy loading)."""
    global pipeline
    if pipeline is None:
        logger.info("Loading TRELLIS.2-4B pipeline...")
        start = time.time()
        try:
            from trellis2.pipelines import Trellis2ImageTo3DPipeline
            from trellis2.pipelines import rembg
            from transformers import AutoModelForImageSegmentation
            import torch

            # Patch: Use ungated camenduru/RMBG-2.0 instead of gated briaai/RMBG-2.0
            # Fix meta tensor issue by patching torch.linspace during model init
            # Fix transformers API compatibility by patching the model class BEFORE loading

            # Patch PreTrainedModel to handle the all_tied_weights_keys getter/setter issue
            # The breaking change in transformers main tries to:
            # 1. SET all_tied_weights_keys in post_init (but it's a property)
            # 2. GET all_tied_weights_keys.keys() in mark_tied_weights_as_initialized
            from transformers import PreTrainedModel

            # Create a patched version of mark_tied_weights_as_initialized
            original_mark_tied = PreTrainedModel.mark_tied_weights_as_initialized
            def patched_mark_tied_weights(self):
                # Ensure _all_tied_weights_keys exists as a dict
                if not hasattr(self, '_all_tied_weights_keys'):
                    object.__setattr__(self, '_all_tied_weights_keys', {})
                return original_mark_tied(self)
            PreTrainedModel.mark_tied_weights_as_initialized = patched_mark_tied_weights

            # Patch post_init to set up _all_tied_weights_keys properly
            original_post_init = PreTrainedModel.post_init
            def patched_post_init(model_self):
                # Pre-initialize the attribute that will be set
                if not hasattr(model_self, '_all_tied_weights_keys'):
                    object.__setattr__(model_self, '_all_tied_weights_keys', {})
                if not hasattr(model_self, '_tied_weights_keys'):
                    object.__setattr__(model_self, '_tied_weights_keys', [])
                # Call original with patched __setattr__
                original_setattr = type(model_self).__setattr__
                def safe_setattr(self, name, value):
                    if name == 'all_tied_weights_keys':
                        object.__setattr__(self, '_all_tied_weights_keys', value)
                    else:
                        original_setattr(self, name, value)
                type(model_self).__setattr__ = safe_setattr
                try:
                    original_post_init(model_self)
                finally:
                    type(model_self).__setattr__ = original_setattr
            PreTrainedModel.post_init = patched_post_init

            # Patch __getattr__ to return _all_tied_weights_keys when all_tied_weights_keys is accessed
            original_getattr = PreTrainedModel.__getattr__ if hasattr(PreTrainedModel, '__getattr__') else None
            def patched_getattr(self, name):
                if name == 'all_tied_weights_keys':
                    return getattr(self, '_all_tied_weights_keys', {})
                if original_getattr:
                    return original_getattr(self, name)
                raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
            PreTrainedModel.__getattr__ = patched_getattr

            def patched_birefnet_init(self, model_name: str = "camenduru/RMBG-2.0"):
                from torchvision import transforms
                logger.info(f"Loading RMBG model: camenduru/RMBG-2.0 (fixing meta tensor + API issues)")

                # Patch torch.linspace to force CPU during model init (fixes meta tensor issue)
                original_linspace = torch.linspace
                def patched_linspace(*args, **kwargs):
                    # Force CPU device to avoid meta tensor issues
                    kwargs['device'] = 'cpu'
                    return original_linspace(*args, **kwargs)

                try:
                    torch.linspace = patched_linspace
                    self.model = AutoModelForImageSegmentation.from_pretrained(
                        "camenduru/RMBG-2.0",
                        trust_remote_code=True,
                        device_map=None,  # Don't use device_map
                        low_cpu_mem_usage=False,  # Load all weights to CPU
                    )
                finally:
                    torch.linspace = original_linspace

                self.model.eval()
                self.transform_image = transforms.Compose([
                    transforms.Resize((1024, 1024)),
                    transforms.ToTensor(),
                    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
                ])
            rembg.BiRefNet.__init__ = patched_birefnet_init

            pipeline = Trellis2ImageTo3DPipeline.from_pretrained("microsoft/TRELLIS.2-4B")
            pipeline.cuda()
            logger.info(f"Pipeline loaded in {time.time() - start:.1f}s")
        except Exception as e:
            logger.error(f"Failed to load pipeline: {e}")
            raise
    return pipeline


def generate_3d(
    image: Image.Image,
    resolution: int = 512,
    output_format: str = "glb",
    output_dir: str = "/storage/outputs"
) -> dict:
    """
    Generate 3D mesh from image using TRELLIS.2.

    Args:
        image: PIL Image to convert
        resolution: Output resolution (512, 1024, or 1536)
        output_format: Output format (glb, obj, ply)
        output_dir: Directory to save output files

    Returns:
        dict with mesh_path, vertices, faces count, and timing info
    """
    pipe = load_pipeline()

    start = time.time()

    # Run inference
    logger.info(f"Generating 3D mesh at {resolution}^3 resolution...")

    # TRELLIS.2 expects specific image preprocessing
    if image.mode != "RGB":
        image = image.convert("RGB")

    # Generate mesh
    outputs = pipe.run(
        image,
        seed=42,
    )

    mesh = outputs[0]  # First output is the mesh

    generation_time = time.time() - start
    logger.info(f"Generation completed in {generation_time:.1f}s")

    # Save mesh
    os.makedirs(output_dir, exist_ok=True)
    timestamp = int(time.time() * 1000)

    # TRELLIS.2 MeshWithVoxel needs to be converted to GLB using o_voxel.postprocess
    import o_voxel

    # Simplify mesh to nvdiffrast limit
    mesh.simplify(16777216)

    # Convert to GLB with texture baking
    output_path = os.path.join(output_dir, f"mesh_{timestamp}.glb")
    glb = o_voxel.postprocess.to_glb(
        vertices=mesh.vertices,
        faces=mesh.faces,
        attr_volume=mesh.attrs,
        coords=mesh.coords,
        attr_layout=mesh.layout,
        voxel_size=mesh.voxel_size,
        aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
        decimation_target=500000,
        texture_size=2048,
        remesh=False,
        verbose=True
    )
    # Use extension_webp=False to avoid pillow-simd compatibility issue
    glb.export(output_path, extension_webp=False)

    # Get mesh stats
    try:
        vertices = len(mesh.vertices) if hasattr(mesh, 'vertices') else 0
        faces = len(mesh.faces) if hasattr(mesh, 'faces') else 0
    except:
        vertices = 0
        faces = 0

    return {
        "success": True,
        "mesh_path": output_path,
        "format": output_format,
        "resolution": resolution,
        "vertices": vertices,
        "faces": faces,
        "generation_time_seconds": round(generation_time, 2)
    }


# Simple HTTP server using built-in http.server
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse


class Trellis2Handler(BaseHTTPRequestHandler):
    """HTTP request handler for TRELLIS.2 API."""

    def _send_json(self, data: dict, status: int = 200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _send_error(self, message: str, status: int = 500):
        """Send error response."""
        self._send_json({"success": False, "error": message}, status)

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/health':
            self._send_json({"status": "healthy"})
        elif self.path == '/status':
            gpu_info = {}
            try:
                if torch.cuda.is_available():
                    gpu_info = {
                        "cuda_available": True,
                        "device_name": torch.cuda.get_device_name(0),
                        "memory_total_gb": round(torch.cuda.get_device_properties(0).total_memory / 1e9, 2),
                        "memory_allocated_gb": round(torch.cuda.memory_allocated(0) / 1e9, 2),
                    }
                else:
                    gpu_info = {"cuda_available": False}
            except Exception as e:
                gpu_info = {"error": str(e)}

            self._send_json({
                "model": "TRELLIS.2-4B",
                "model_loaded": pipeline is not None,
                "gpu": gpu_info
            })
        else:
            self._send_error("Not found", 404)

    def do_POST(self):
        """Handle POST requests."""
        if self.path == '/generate':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                content_type = self.headers.get('Content-Type', '')

                if 'multipart/form-data' in content_type:
                    import cgi
                    form = cgi.FieldStorage(
                        fp=self.rfile,
                        headers=self.headers,
                        environ={'REQUEST_METHOD': 'POST',
                                'CONTENT_TYPE': content_type}
                    )

                    if 'image' not in form:
                        self._send_error("No image provided", 400)
                        return

                    image_data = form['image'].file.read()
                    image = Image.open(io.BytesIO(image_data))

                    resolution = int(form.getvalue('resolution', '512'))
                    output_format = form.getvalue('format', 'glb')

                elif 'application/json' in content_type:
                    body = self.rfile.read(content_length)
                    data = json.loads(body)

                    if 'image_path' in data:
                        image = Image.open(data['image_path'])
                    elif 'image_base64' in data:
                        import base64
                        image_data = base64.b64decode(data['image_base64'])
                        image = Image.open(io.BytesIO(image_data))
                    else:
                        self._send_error("No image provided (use image_path or image_base64)", 400)
                        return

                    resolution = data.get('resolution', 512)
                    output_format = data.get('format', 'glb')
                else:
                    self._send_error("Unsupported content type", 400)
                    return

                result = generate_3d(
                    image=image,
                    resolution=resolution,
                    output_format=output_format
                )

                self._send_json(result)

            except Exception as e:
                logger.error(f"Generation error: {traceback.format_exc()}")
                self._send_error(str(e), 500)

        elif self.path == '/load':
            try:
                load_pipeline()
                self._send_json({"success": True, "message": "Model loaded"})
            except Exception as e:
                self._send_error(f"Failed to load model: {e}", 500)

        else:
            self._send_error("Not found", 404)


def main():
    parser = argparse.ArgumentParser(description="TRELLIS.2 Image-to-3D Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument("--preload", action="store_true", help="Preload model on startup")
    args = parser.parse_args()

    if args.preload:
        logger.info("Preloading model...")
        load_pipeline()

    server = HTTPServer((args.host, args.port), Trellis2Handler)
    logger.info(f"Starting TRELLIS.2 server on {args.host}:{args.port}")
    logger.info("Endpoints:")
    logger.info("  GET  /health  - Health check")
    logger.info("  GET  /status  - Model and GPU status")
    logger.info("  POST /generate - Generate 3D mesh from image")
    logger.info("  POST /load    - Explicitly load model")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
```

---

## Entrypoint Scripts

### diffusion-gen/entrypoint.sh

```bash
#!/bin/bash
set -e

# Ensure model directories exist
mkdir -p /app/ComfyUI/models/checkpoints
mkdir -p /app/ComfyUI/models/loras
mkdir -p /app/ComfyUI/models/vae
mkdir -p /app/ComfyUI/models/clip
mkdir -p /app/ComfyUI/models/controlnet
mkdir -p /app/ComfyUI/models/embeddings

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

echo "Starting ComfyUI..."
exec python main.py "$@"
```

### image-to-3d/entrypoint.sh

```bash
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
```

---

## Docker Compose Configuration

```yaml
services:
  # ComfyUI for diffusion-based image generation
  diffusion-gen:
    container_name: diffusion-gen
    build:
      context: ./components/diffusion-gen
      dockerfile: Dockerfile
    image: diffusion-gen:latest
    profiles:
      - synthetic
      - all
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - NVIDIA_DRIVER_CAPABILITIES=compute,utility
    ports:
      - "8188:8188"
    volumes:
      - ./storage/models/checkpoints:/app/ComfyUI/models/checkpoints:rw
      - ./storage/models/unet:/app/ComfyUI/models/diffusion_models:rw
      - ./storage/models/loras:/app/ComfyUI/models/loras:rw
      - ./storage/models/vae:/app/ComfyUI/models/vae:rw
      - ./storage/models/clip:/app/ComfyUI/models/text_encoders:rw
      - ./storage/inputs:/storage/inputs:rw
      - ./storage/outputs:/storage/outputs:rw
      - /tmp/pipeline_output:/tmp/pipeline_output:rw
    command: ["--listen", "0.0.0.0", "--port", "8188"]

  # TRELLIS.2 for image-to-3D mesh generation
  image-to-3d:
    container_name: image-to-3d
    build:
      context: ./components/image-to-3d
      dockerfile: Dockerfile
    image: image-to-3d:latest
    profiles:
      - synthetic
      - all
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - NVIDIA_DRIVER_CAPABILITIES=compute,utility
      - HF_HOME=/storage/models/huggingface
      - TRANSFORMERS_CACHE=/storage/models/huggingface
      - CUDA_HOME=/usr/local/cuda
    ports:
      - "8000:8000"
    volumes:
      - ${HOME}/.cache/huggingface:/storage/models/huggingface:rw
      - ./storage/inputs:/storage/inputs:rw
      - ./storage/outputs:/storage/outputs:rw
      - /tmp/pipeline_output:/tmp/pipeline_output:rw
      - /tmp/isaac_sim_output:/tmp/isaac_sim_output:rw
    command: ["--host", "0.0.0.0", "--port", "8000"]
```

---

## Usage

### Initial Setup

```bash
# 1. Download Z-Image Turbo models (~21GB, first time only)
./scripts/setup_models.sh

# 2. Build and start services
docker compose --profile synthetic up -d --build

# 3. Check service health
curl http://localhost:8188/  # ComfyUI
curl http://localhost:8000/health  # TRELLIS.2
```

### Generate 3D Object from Text

```bash
# Step 1: Generate image with ComfyUI (via API or web UI at localhost:8188)
# The workflow generates a 1024x1024 image from text prompt

# Step 2: Convert image to 3D mesh
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"image_path": "/storage/outputs/generated_image.png"}'

# Response:
# {
#   "success": true,
#   "mesh_path": "/storage/outputs/mesh_1706012345678.glb",
#   "vertices": 24000,
#   "faces": 47000,
#   "generation_time_seconds": 190.5
# }
```

---

## Performance Metrics

| Stage | Time | GPU VRAM |
|-------|------|----------|
| Z-Image Turbo (1024x1024) | ~3s | ~8GB |
| TRELLIS.2 (512³) | ~190s | ~20GB |
| **Total Pipeline** | **~195s** | **~24GB peak** |

---

## Troubleshooting

### "Model requires authentication"
The gated model error is fixed by using `camenduru/RMBG-2.0`. Ensure server.py includes the monkey-patch.

### "Meta tensor" errors
The `torch.linspace` patch in `load_pipeline()` forces CPU device during model initialization.

### "all_tied_weights_keys" AttributeError
The `PreTrainedModel` patches handle the breaking API change in transformers main branch.

### GPU out of memory
- Reduce `decimation_target` in `generate_3d()` (default: 500000)
- Reduce `texture_size` (default: 2048)
- Use 512³ resolution instead of higher

---

## References

- [Microsoft TRELLIS.2](https://github.com/microsoft/TRELLIS.2)
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
- [Z-Image Turbo Models](https://huggingface.co/Comfy-Org/z_image_turbo)
- [camenduru/RMBG-2.0 (ungated mirror)](https://huggingface.co/camenduru/RMBG-2.0)
