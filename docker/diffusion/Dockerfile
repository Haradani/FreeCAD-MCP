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

# Install aiohttp for API access
RUN pip install aiohttp websocket-client

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Copy workflows
COPY workflows /app/workflows

EXPOSE 8188

WORKDIR /app/ComfyUI

ENTRYPOINT ["/entrypoint.sh"]
CMD ["--listen", "0.0.0.0", "--port", "8188"]
