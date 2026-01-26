# Vision AI Inference Container
#
# Provides SAM3 segmentation and Cosmos VLM capabilities
# Optimized for dual 24GB 3090 GPUs with quantization support

FROM nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04

LABEL maintainer="FreeCAD MCP"
LABEL description="Vision AI inference server (SAM3 + VLM)"

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-dev \
    git \
    wget \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel

# Install PyTorch with CUDA support
RUN pip3 install --no-cache-dir \
    torch>=2.5.0 \
    torchvision>=0.20.0 \
    torchaudio>=2.5.0 \
    --index-url https://download.pytorch.org/whl/cu124

# Install ML dependencies
RUN pip3 install --no-cache-dir \
    transformers>=4.45.0 \
    accelerate>=0.34.0 \
    bitsandbytes>=0.44.0 \
    safetensors>=0.4.0 \
    sentencepiece>=0.2.0 \
    protobuf>=4.0.0 \
    einops>=0.7.0 \
    timm>=1.0.0

# Install image processing
RUN pip3 install --no-cache-dir \
    Pillow>=10.0.0 \
    opencv-python-headless>=4.8.0 \
    numpy>=1.24.0

# Install ZMQ for server communication
RUN pip3 install --no-cache-dir pyzmq>=25.0.0

# Create directories
RUN mkdir -p /app /models /data

# Copy inference server
COPY server.py /app/server.py
RUN chmod +x /app/server.py

# Copy model loaders
COPY sam_loader.py /app/sam_loader.py
COPY vlm_loader.py /app/vlm_loader.py

# Environment variables
# Note: CUDA_VISIBLE_DEVICES should NOT be set here - let Docker handle GPU visibility
# Setting it to "all" is invalid and causes PyTorch to report no GPUs
ENV TRANSFORMERS_CACHE=/models/transformers
ENV HF_HOME=/models/huggingface
ENV ZMQ_PORT=5555
ENV ZMQ_HOST=0.0.0.0

# Model configuration
# GPU 0: VLM (Cosmos), GPU 1: SAM3
ENV VLM_DEVICE=cuda:0
ENV SAM_DEVICE=cuda:1
ENV VLM_QUANTIZATION=4bit
ENV SAM_QUANTIZATION=none

# Expose ZMQ port
EXPOSE 5555

# Health check
HEALTHCHECK --interval=60s --timeout=30s --start-period=120s --retries=3 \
    CMD python3 -c "import zmq; c=zmq.Context(); s=c.socket(zmq.REQ); s.connect('tcp://localhost:5555'); s.send_json({'action':'ping'}); print(s.recv_json())" || exit 1

WORKDIR /app

ENTRYPOINT ["python3", "/app/server.py"]
