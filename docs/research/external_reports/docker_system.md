# Docker Container Management System

## Overview

The Docker system manages container lifecycles for the inference services (SAM3 + Cosmos VLM). It provides MCP tools for container start/stop/restart, log retrieval, health checking, and image building.

**Note**: This document focuses on the inference container and general Docker infrastructure. Robotics-specific containers are documented separately.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              MCP Server (Host)                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    Docker Management Tools                           │    │
│  │  inference_container_start │ inference_container_stop │ logs        │    │
│  │  inference_container_restart │ inference_build_image                │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    subprocess + docker CLI                           │    │
│  │  - docker inspect                                                    │    │
│  │  - docker compose up/down                                           │    │
│  │  - docker logs                                                       │    │
│  │  - docker build                                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    Inference Container                               │    │
│  │  - SAM3 + Cosmos VLM                                                │    │
│  │  - ZMQ server on port 5560                                          │    │
│  │  - Health check via ZMQ ping                                        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Container Services

### Inference Container

| Property | Value |
|----------|-------|
| **Container Name** | `inference` |
| **Image** | `inference:latest` |
| **Port** | 5560 (ZMQ) |
| **GPU** | Required (NVIDIA runtime) |
| **Purpose** | SAM3 segmentation + Cosmos VLM inference |

## Docker Compose Configuration

```yaml
# docker-compose.yml (inference service only)

services:
  # Unified inference container for SAM3 + Cosmos VLM
  # Runs with transformers from main branch for SAM3 support
  inference:
    container_name: inference
    build:
      context: ./docker/inference
      dockerfile: Dockerfile
    image: inference:latest
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - NVIDIA_DRIVER_CAPABILITIES=all
      - INFERENCE_PORT=5560
      - HF_HOME=/root/.cache/huggingface
      # Debug interface settings
      - DEBUG_ENABLED=true
      - DEBUG_PORT=7860
      - DEBUG_SHARE=true
    network_mode: host
    volumes:
      # === Shared Directories (accessible from host and container) ===
      # Main output directory for images, videos, masks, camera frames
      - /tmp/isaac_sim_output:/tmp/isaac_sim_output:rw
      # Session storage (debug interface, request history, thumbnails)
      - /tmp/debug_sessions:/tmp/debug_sessions:rw
      # Exports directory (persistent storage for important files)
      - ./exports:/app/exports:rw

      # === Model Cache (shared with host to avoid re-downloading) ===
      # HuggingFace cache for SAM3, Cosmos VLM, Qwen3-VL weights
      - ${HOME}/.cache/huggingface:/root/.cache/huggingface:rw
      # Torch hub cache (for any torch.hub models)
      - ${HOME}/.cache/torch:/root/.cache/torch:rw
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "python3", "-c",
             "import zmq; ctx = zmq.Context(); sock = ctx.socket(zmq.REQ); \
              sock.connect('tcp://localhost:5560'); sock.send_json({'command': 'ping'}); \
              sock.recv_json()"]
      interval: 30s
      timeout: 10s
      start_period: 60s
      retries: 3
    # Start inference server (default)
    command: ["python3", "/app/server.py"]
```

## Inference Container Dockerfile

```dockerfile
# Unified Inference Container for SAM3 + Cosmos VLM
# Based on HuggingFace transformers GPU Dockerfile

FROM nvidia/cuda:12.6.0-cudnn-devel-ubuntu22.04
LABEL maintainer="Isaac Sim NL Interface"

ARG DEBIAN_FRONTEND=noninteractive

# Configurable versions via build args
ARG PYTORCH='2.9.0'
ARG CUDA='cu126'
ARG TRANSFORMERS_VERSION='main'

# Install system dependencies
RUN apt update && apt install -y \
    git \
    libsndfile1-dev \
    python3 \
    python3-pip \
    ffmpeg \
    git-lfs \
    && git lfs install \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN python3 -m pip install --no-cache-dir --upgrade pip

# Install PyTorch with CUDA support
RUN python3 -m pip install --no-cache-dir \
    torch==${PYTORCH} \
    torchvision \
    torchaudio \
    --extra-index-url https://download.pytorch.org/whl/${CUDA}

# Install transformers (from main branch by default for SAM3 support)
RUN if [ "$TRANSFORMERS_VERSION" = "main" ]; then \
        echo "Installing transformers from main branch (SAM3 support)..." && \
        git clone https://github.com/huggingface/transformers /transformers && \
        cd /transformers && \
        python3 -m pip install --no-cache-dir -e .[dev]; \
    else \
        echo "Installing transformers version ${TRANSFORMERS_VERSION}..." && \
        python3 -m pip install --no-cache-dir transformers==${TRANSFORMERS_VERSION}; \
    fi

# Install ML dependencies
RUN python3 -m pip install --no-cache-dir \
    accelerate \
    bitsandbytes \
    timm

# Install Qwen VL utils for Cosmos VLM (Qwen3-VL based)
RUN python3 -m pip install --no-cache-dir qwen_vl_utils

# Install communication and image processing
RUN python3 -m pip install --no-cache-dir \
    pyzmq \
    Pillow \
    numpy

# Install video processing (for VLM video queries)
RUN python3 -m pip install --no-cache-dir av

# Create working directory
WORKDIR /app

# Copy inference server code
COPY server.py /app/server.py

# Create shared directories
RUN mkdir -p /tmp/isaac_sim_output

# Expose ZMQ port
EXPOSE 5560

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python3 -c "import zmq; ctx = zmq.Context(); sock = ctx.socket(zmq.REQ); \
    sock.connect('tcp://localhost:5560'); sock.send_json({'command': 'ping'}); \
    sock.recv_json()" || exit 1

# Default command: run the inference server
CMD ["python3", "/app/server.py"]
```

## MCP Tools

### Inference Container Management

| Tool | Description |
|------|-------------|
| `inference_container_status` | Check if inference container is running |
| `inference_container_start` | Start inference container |
| `inference_container_restart` | Stop and restart inference container |
| `inference_container_stop` | Stop inference container |
| `inference_container_logs` | Get inference container logs |
| `inference_build_image` | Build inference container image |

### Tool Details

#### inference_container_status

```python
@mcp.tool()
def inference_container_status() -> str:
    """Check if the inference container (SAM3 + Cosmos VLM) is running.

    Returns:
        JSON string with container status including:
        - running: Whether container is running
        - container_id: Container ID (if running)
        - status: Container status string
        - image: Container image name
    """
```

**Example Response:**
```json
{
    "running": true,
    "container_id": "abc123def456",
    "status": "running",
    "image": "inference:latest",
    "started_at": "2026-01-23T10:00:00Z"
}
```

#### inference_container_start

```python
@mcp.tool()
def inference_container_start(
    wait_for_ready: bool = True,
    timeout: int = 120,
) -> str:
    """Start the inference container (SAM3 + Cosmos VLM) if not already running.

    Uses docker compose to start the inference service.

    Args:
        wait_for_ready: Wait until the ZMQ server is responding (default: True)
        timeout: Maximum wait time in seconds (default: 120)
    """
```

**Implementation:**
```python
# Start using docker compose
result = subprocess.run(
    ["docker", "compose", "up", "-d", "inference"],
    capture_output=True,
    text=True,
    timeout=300,
    cwd=PROJECT_ROOT,
)

# Wait for ZMQ server to respond
if wait_for_ready:
    client = InferenceClient(timeout=5000)
    for _ in range(timeout):
        if client.ping():
            return {"success": True, "message": "Container ready"}
        time.sleep(1)
```

#### inference_container_restart

```python
@mcp.tool()
def inference_container_restart(
    wait_for_ready: bool = True,
    timeout: int = 120,
) -> str:
    """Stop and restart the inference container (SAM3 + Cosmos VLM).

    This will stop any existing container and start a fresh one.
    Use this after updating server.py or other inference code.
    """
```

**Use Cases:**
- After editing `docker/inference/server.py`
- After updating model code
- To clear container state

#### inference_container_logs

```python
@mcp.tool()
def inference_container_logs(tail: int = 100, since: str = None) -> str:
    """Get logs from the inference container.

    Args:
        tail: Number of lines to show from the end of logs (default: 100)
        since: Show logs since timestamp (e.g., "10m" for last 10 minutes)
    """
```

**Example:**
```python
# Get last 50 lines
inference_container_logs(tail=50)

# Get logs from last 5 minutes
inference_container_logs(since="5m")
```

#### inference_build_image

```python
@mcp.tool()
def inference_build_image(no_cache: bool = False) -> str:
    """Build the inference container image (SAM3 + Cosmos VLM).

    This builds the inference image with transformers from main branch.
    Use no_cache=True to force a full rebuild after Dockerfile changes.

    Args:
        no_cache: If True, build without using cache (forces full rebuild)
    """
```

**Implementation:**
```python
cmd = ["docker", "compose", "build", "inference"]
if no_cache:
    cmd.append("--no-cache")

result = subprocess.run(
    cmd,
    capture_output=True,
    text=True,
    timeout=1800,  # 30 minutes for build
    cwd=PROJECT_ROOT,
)
```

## Volume Mounts

### Shared Directories

| Host Path | Container Path | Purpose |
|-----------|----------------|---------|
| `/tmp/isaac_sim_output` | `/tmp/isaac_sim_output` | Images, videos, masks |
| `/tmp/debug_sessions` | `/tmp/debug_sessions` | Debug interface sessions |
| `./exports` | `/app/exports` | Persistent exports |

### Model Cache

| Host Path | Container Path | Purpose |
|-----------|----------------|---------|
| `~/.cache/huggingface` | `/root/.cache/huggingface` | Model weights |
| `~/.cache/torch` | `/root/.cache/torch` | Torch hub models |

**Benefits of Shared Cache:**
- Models downloaded once, shared across container rebuilds
- No re-downloading after container restart
- Shared with host Python environment

## Health Checking

### Container Health Check

The Docker health check verifies the ZMQ server is responding:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python3 -c "import zmq; ctx = zmq.Context(); \
    sock = ctx.socket(zmq.REQ); sock.connect('tcp://localhost:5560'); \
    sock.send_json({'command': 'ping'}); sock.recv_json()" || exit 1
```

| Parameter | Value | Description |
|-----------|-------|-------------|
| `interval` | 30s | Time between health checks |
| `timeout` | 10s | Timeout for each check |
| `start_period` | 60s | Grace period after container start |
| `retries` | 3 | Failures before marking unhealthy |

### MCP Health Verification

When starting containers, MCP tools verify readiness:

```python
def _wait_for_inference_ready(timeout: int = 120) -> bool:
    """Wait for inference container to be ready."""
    client = InferenceClient(timeout=5000)

    for _ in range(timeout):
        try:
            if client.ping():
                return True
        except Exception:
            pass
        time.sleep(1)

    return False
```

## Network Configuration

### Host Network Mode

Both containers use `network_mode: host` for simplicity:

```yaml
network_mode: host
```

**Benefits:**
- Direct localhost communication
- No port mapping required
- ZMQ connects via `tcp://localhost:5560`

**Ports Used:**

| Port | Service | Protocol |
|------|---------|----------|
| 5560 | Inference ZMQ | TCP |
| 7860 | Debug Interface | HTTP |

## Environment Variables

### Container Environment

| Variable | Value | Description |
|----------|-------|-------------|
| `NVIDIA_VISIBLE_DEVICES` | `all` | GPU visibility |
| `NVIDIA_DRIVER_CAPABILITIES` | `all` | GPU capabilities |
| `INFERENCE_PORT` | `5560` | ZMQ server port |
| `HF_HOME` | `/root/.cache/huggingface` | HuggingFace cache path |
| `DEBUG_ENABLED` | `true` | Enable debug interface |
| `DEBUG_PORT` | `7860` | Debug interface port |
| `DEBUG_SHARE` | `true` | Enable Cloudflare tunnel |

### Host Environment

| Variable | Usage |
|----------|-------|
| `${HOME}` | Expands to user home directory for cache mounts |

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| Container not starting | Missing GPU driver | Check `nvidia-smi` |
| Build failed | Docker not running | Start Docker daemon |
| Timeout on start | Slow model loading | Increase timeout |
| Port already in use | Previous container | Stop with `docker stop inference` |

### Retry Logic

Container start tools include retry logic:

```python
# Wait for readiness with retries
for attempt in range(3):
    try:
        start_container()
        if wait_for_ready(timeout=60):
            return success
    except Exception:
        time.sleep(5)

return failure
```

## GPU Resource Management

### Docker GPU Configuration

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```

### Runtime Requirements

- NVIDIA Container Toolkit installed
- `nvidia` runtime available
- GPU with sufficient VRAM (8GB+ for SAM3, 32GB+ for VLM)

## Container Lifecycle

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Image     │     │  Container  │     │   Running   │
│   Build     │────▶│   Created   │────▶│   Service   │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │
       │                   │                   │
       ▼                   ▼                   ▼
inference_build_image  inference_container_start  inference_container_stop
                              │                   │
                              │                   │
                              ▼                   │
                       wait_for_ready             │
                              │                   │
                              └───────────────────┘
                                      │
                                      ▼
                           inference_container_restart
```

## Troubleshooting

### Container Won't Start

```bash
# Check Docker status
docker info

# Check GPU availability
nvidia-smi

# Check for existing container
docker ps -a | grep inference

# Remove stuck container
docker rm -f inference

# Try manual start
docker compose up inference
```

### Slow Start Times

First start is slow due to:
1. Image build (if not cached)
2. Model download (first time only)
3. Model loading to GPU

Subsequent starts are faster due to cached models.

### Memory Issues

```bash
# Check GPU memory
nvidia-smi

# Check container memory
docker stats inference
```

### Log Analysis

```bash
# View live logs
docker logs -f inference

# View last 100 lines
docker logs --tail 100 inference

# View logs since timestamp
docker logs --since 10m inference
```

## Best Practices

### Development Workflow

1. **Edit Code** → Edit `server.py` or other files
2. **Rebuild** → `inference_build_image(no_cache=False)`
3. **Restart** → `inference_container_restart()`
4. **Verify** → `inference_container_status()`

### Production Deployment

1. Build image with specific tag
2. Push to registry
3. Pull on target machine
4. Start with `docker compose up -d`

### Cleanup

```bash
# Stop container
docker stop inference

# Remove container
docker rm inference

# Remove unused images
docker image prune

# Clear model cache (if needed)
rm -rf ~/.cache/huggingface/hub/models--facebook--sam3
```
