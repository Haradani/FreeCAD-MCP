# TRELLIS.2 Docker for Image-to-3D Generation
# Based on Microsoft TRELLIS.2: https://github.com/microsoft/TRELLIS.2

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
