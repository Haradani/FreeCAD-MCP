# SAM3 Segmentation System

## Overview

The SAM3 system provides semantic image and video segmentation using Meta's **Segment Anything Model 3 (SAM3)**. It enables text-based object segmentation through Promptable Concept Segmentation (PCS), allowing natural language queries to identify and segment objects.

**Policy**: This project uses **SAM3 EXCLUSIVELY**. SAM 2 and SAM 2.1 are NOT supported.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              MCP Server (Host)                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        SAM3 Tools Layer                              │    │
│  │  sam_load_model │ mask_background │ colorize_region │ get_region_area│    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    SAMSegmenter Client (sam_segmentation.py)         │    │
│  │  - Model loading/unloading via inference container                   │    │
│  │  - Mask processing and combination                                   │    │
│  │  - Centroid computation for positioning                             │    │
│  │  - Image manipulation (colorize, mask, extract)                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                                    ▼ ZMQ (port 5560)                        │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    Inference Container                               │    │
│  │  - SAM3 model (facebook/sam3, 8GB+ VRAM)                            │    │
│  │  - Sam3Model + Sam3Processor from transformers                      │    │
│  │  - Video segmentation with Sam3VideoModel                           │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Model Specifications

### SAM3 (Segment Anything Model 3)

| Property | Value |
|----------|-------|
| **Model ID** | `facebook/sam3` |
| **VRAM Required** | 8GB+ |
| **Architecture** | Vision Transformer with PCS |
| **Text Prompts** | 270K+ concepts supported |
| **Output** | Binary masks + bounding boxes + confidence scores |

### Key Capabilities

- **Promptable Concept Segmentation (PCS)**: Text-based segmentation without point/box prompts
- **Multi-instance Detection**: Finds ALL matching instances for a prompt
- **Video Tracking**: Consistent object tracking across video frames
- **High-resolution Masks**: Full-resolution segmentation outputs

## Model Download and Cache

### Automatic Download

Models are downloaded automatically from HuggingFace Hub on first use:

```python
# In inference container server.py
from transformers import Sam3Model, Sam3Processor

model_id = "facebook/sam3"
_sam3_processor = Sam3Processor.from_pretrained(model_id)
_sam3_model = Sam3Model.from_pretrained(model_id)
```

### Cache Location

| Environment | Path |
|-------------|------|
| **Inference Container** | `/root/.cache/huggingface/` |
| **Host Mount** | `~/.cache/huggingface/` |

The cache is mounted as a volume in docker-compose.yml:
```yaml
volumes:
  - ~/.cache/huggingface:/root/.cache/huggingface
```

This enables model persistence across container restarts.

### Model Files

```
~/.cache/huggingface/hub/
└── models--facebook--sam3/
    ├── blobs/
    │   └── <sha256-hashed model weights>
    ├── refs/
    │   └── main
    └── snapshots/
        └── <revision>/
            ├── config.json
            ├── model.safetensors
            ├── preprocessor_config.json
            └── ...
```

## Core Components

### 1. SAMSegmenter Client (`src/sam_segmentation.py`)

The main client class for SAM3 segmentation.

```python
class SAMSegmenter:
    """SAM3 segmentation client for Isaac Sim integration.

    This class communicates with the inference container to perform
    SAM3-based segmentation. SAM3 provides true text-based segmentation
    via Promptable Concept Segmentation (PCS).
    """

    def __init__(
        self,
        model_variant: str = "sam3",  # Only "sam3" supported
        device: str = "cuda",
    ):
        if model_variant != "sam3":
            raise ValueError(
                f"Only 'sam3' is supported. SAM 2 and SAM 2.1 are NOT supported."
            )
```

**Key Methods:**

| Method | Description |
|--------|-------------|
| `load_model()` | Start container and load SAM3 |
| `unload_model()` | Free GPU memory |
| `segment_by_text(image_path, prompt)` | Segment by text prompt |
| `segment_video(video_path, prompt)` | Track objects in video |
| `mask_background(image_path, prompt)` | Remove background |
| `colorize_region(image_path, prompt, color)` | Apply color overlay |
| `extract_object(image_path, prompt)` | Crop and extract object |
| `get_region_area(image_path, prompt)` | Get area and centroid stats |

### 2. InferenceClient (ZMQ)

Handles communication with the inference container:

```python
class InferenceClient:
    """ZMQ client for communicating with the inference container."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5560,
        timeout: int = 120000,  # 2 minutes for model loading
    ):
        ...

    def send_command(self, command: str, **kwargs) -> Dict[str, Any]:
        """Send a command to the inference server."""
        request = {"command": command, **kwargs}
        self._socket.send_json(request)
        response = self._socket.recv_json()
        return response
```

### 3. Centroid and Offset Computation

For camera positioning and framing analysis:

```python
def _compute_centroid_and_offset(
    self,
    mask: np.ndarray,
    img_width: int,
    img_height: int,
) -> Dict:
    """Compute centroid position and offset from image center.

    Returns:
        - centroid: [x, y] pixel coordinates
        - centroid_normalized: [0-1, 0-1] where 0.5 is center
        - offset_from_center: [x, y] pixels from center
        - offset_normalized: [-1 to 1] where 0 is centered
        - position_description: Human-readable position
    """
    y_indices, x_indices = np.where(mask > 0.5)

    centroid_x = float(np.mean(x_indices))
    centroid_y = float(np.mean(y_indices))

    # Image center
    center_x = img_width / 2.0
    center_y = img_height / 2.0

    # Offset from center
    offset_x = centroid_x - center_x
    offset_y = centroid_y - center_y

    # Generate position description
    if offset_y_norm < -0.3:
        position_parts.append("near top")
    elif offset_y_norm > 0.3:
        position_parts.append("near bottom")
    # ... etc
```

## MCP Tools

### Core SAM3 Tools

| Tool | Description |
|------|-------------|
| `sam_load_model` | Load SAM3 model (8GB+ VRAM) |
| `sam_unload_model` | Unload model to free GPU |
| `sam_status` | Check model status |
| `mask_background` | Remove background by text prompt |
| `colorize_region` | Apply color overlay to regions |
| `extract_object` | Extract specific object with transparency |
| `get_region_area` | Get pixel area + centroid offset |
| `get_camera_region_area` | Capture + segment + stats |
| `segment_and_colorize_camera` | Capture + segment + colorize |
| `sam_segment_video` | Segment objects across video frames |

### Composite Tools

| Tool | Description |
|------|-------------|
| `auto_center_camera_on_object` | Iteratively center camera using SAM3 |

## Tool Examples

### Background Removal

```python
mask_background(
    image_path="/tmp/isaac_sim_output/frame.jpg",
    prompt="the robot arm",
    background_color="transparent"  # or "#000000", "#FFFFFF"
)
# Returns: {
#     "success": True,
#     "output_path": "/tmp/.../frame_masked.png",
#     "num_objects": 1
# }
```

### Region Colorization

```python
colorize_region(
    image_path="/tmp/isaac_sim_output/frame.jpg",
    prompt="the gripper",
    color="#FF0000",  # Red
    opacity=0.5  # Semi-transparent
)
# Returns: {
#     "success": True,
#     "output_path": "/tmp/.../frame_colorized.jpg",
#     "num_regions": 1,
#     "color": "#FF0000",
#     "opacity": 0.5
# }
```

### Object Extraction

```python
extract_object(
    image_path="/tmp/isaac_sim_output/frame.jpg",
    prompt="the red cube",
    padding=10  # Pixels around object
)
# Returns: {
#     "success": True,
#     "output_path": "/tmp/.../frame_extracted.png",
#     "bbox": [100, 150, 200, 250],
#     "original_size": [640, 480],
#     "extracted_size": [110, 110]
# }
```

### Region Area Analysis

```python
get_region_area(
    image_path="/tmp/isaac_sim_output/frame.jpg",
    prompt="robot arm"
)
# Returns: {
#     "success": True,
#     "total_area": 45000,
#     "num_regions": 1,
#     "coverage_percent": 14.65,
#     "centroid": [320.5, 280.3],
#     "centroid_normalized": [0.501, 0.584],
#     "offset_from_center": [0.5, 40.3],
#     "offset_normalized": [0.002, 0.168],
#     "position_description": "below center, horizontally centered"
# }
```

### Video Segmentation

```python
sam_segment_video(
    video_path="/tmp/isaac_sim_output/trajectory.mp4",
    prompt="robot arm",
    fps=4,
    max_frames=50
)
# Returns: {
#     "success": True,
#     "frames_processed": 40,
#     "outputs_per_frame": {
#         0: {"mask_paths": [...], "boxes": [...], "scores": [...]},
#         1: {...},
#         ...
#     }
# }
```

## SAM3 Prompt Guidelines

For scenes with robots on pedestals:

| Prompt | Result |
|--------|--------|
| `"robot arm"` | Segments articulated arm only, excludes pedestal |
| `"articulated robot arm"` | Same as above |
| `"UR5e robot"` | Includes pedestal/base - use for whole robot |
| `"cylindrical pillar"` | Segments pedestal only |
| `"gripper"` | Segments end effector |

**Recommendation**: Use `"robot arm"` for centering on the articulated portion without the pedestal.

## Inference Container Server

The SAM3 model runs in a Docker container:

```python
# docker/inference/server.py

def sam_load() -> Dict[str, Any]:
    """Load SAM3 model."""
    global _sam3_model, _sam3_processor

    from transformers import Sam3Model, Sam3Processor

    model_id = "facebook/sam3"
    _sam3_processor = Sam3Processor.from_pretrained(model_id)
    _sam3_model = Sam3Model.from_pretrained(model_id)

    # Use float16 for memory efficiency
    # Note: bfloat16 causes "Got unsupported ScalarType BFloat16"
    if torch.cuda.is_available():
        _sam3_model = _sam3_model.to("cuda", dtype=torch.float16)

def sam_segment_by_text(image_path: str, prompt: str, threshold: float = 0.5):
    """Segment image by text prompt using SAM3 PCS."""

    image = Image.open(image_path).convert("RGB")

    # Process inputs - processor handles text tokenization
    inputs = _sam3_processor(
        images=image,
        text=prompt,
        return_tensors="pt"
    ).to(_sam3_model.device, dtype=torch.float16)

    # Run inference
    with torch.no_grad():
        with torch.amp.autocast(device_type='cuda', dtype=torch.float16):
            outputs = _sam3_model(**inputs)

    # Post-process results
    results = _sam3_processor.post_process_instance_segmentation(
        outputs,
        threshold=threshold,
        mask_threshold=0.5,
        target_sizes=target_sizes
    )[0]

    # Save masks to shared directory as numpy files
    for i, mask in enumerate(results["masks"]):
        mask_np = mask.cpu().numpy().astype(np.uint8)
        mask_path = os.path.join(SHARED_OUTPUT_DIR, f"mask_{i}.npy")
        np.save(mask_path, mask_np)
        masks.append(mask_path)

    return {
        "success": True,
        "mask_paths": masks,
        "bboxes": bboxes,
        "scores": scores,
        "num_masks": len(masks),
    }
```

## Dockerfile (Inference Container)

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

**Key Dependencies:**
- `transformers` from main branch (required for SAM3 classes)
- `torch==2.9.0` with CUDA 12.6
- `pyzmq` for ZMQ communication
- `av` for video processing

## Mask Data Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  MCP Server     │     │  Inference      │     │  Shared Volume  │
│  (Host)         │     │  Container      │     │  /tmp/isaac_    │
│                 │     │                 │     │  sim_output/    │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         │  1. send_command      │                       │
         │  ("sam_segment_by_    │                       │
         │   text", image_path)  │                       │
         ├──────────────────────▶│                       │
         │                       │                       │
         │                       │  2. Load image        │
         │                       │  from shared dir      │
         │                       │◀──────────────────────┤
         │                       │                       │
         │                       │  3. Run SAM3          │
         │                       │  inference            │
         │                       │                       │
         │                       │  4. Save masks        │
         │                       │  as .npy files        │
         │                       ├──────────────────────▶│
         │                       │                       │
         │  5. Return mask_paths │                       │
         │◀──────────────────────┤                       │
         │                       │                       │
         │  6. Load masks        │                       │
         │  from shared dir      │                       │
         ├───────────────────────┼──────────────────────▶│
         │                       │                       │
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `INFERENCE_HOST` | `localhost` | Inference server host |
| `INFERENCE_PORT` | `5560` | ZMQ port |

### Shared Directories

| Host Path | Container Path | Purpose |
|-----------|----------------|---------|
| `/tmp/isaac_sim_output` | `/tmp/isaac_sim_output` | Images, masks, videos |
| `~/.cache/huggingface` | `/root/.cache/huggingface` | Model weights cache |

## Integration Points

### With VLM System

- SAM3 provides object localization for VLM queries
- `auto_center_camera_on_object` uses SAM3 to center objects before VLM analysis

### With Debug Interface

- All segmentation results tracked via RequestTracker
- Colorized images and masks stored in session directory
- Accessible via `debug_list_requests(request_type="sam_segment")`

### With Camera System

- `get_camera_region_area`: Capture + segment in one call
- `segment_and_colorize_camera`: Capture + segment + visualize

## Video Segmentation

SAM3 supports video object tracking:

```python
# In server.py
def sam_segment_video(video_path: str, prompt: str, fps: int = 4, max_frames: int = 50):
    """Segment video by text prompt using SAM3 video PCS."""
    from transformers import Sam3VideoModel, Sam3VideoProcessor
    from transformers.video_utils import load_video

    # Load video model (separate from image model)
    video_model = Sam3VideoModel.from_pretrained("facebook/sam3")
    video_processor = Sam3VideoProcessor.from_pretrained("facebook/sam3")

    # Load video frames
    video_frames, _ = load_video(video_path)

    # Initialize video session
    inference_session = video_processor.init_video_session(
        video=video_frames,
        inference_device=str(device),
        processing_device="cpu",
        video_storage_device="cpu",
    )

    # Add text prompt
    inference_session = video_processor.add_text_prompt(
        inference_session=inference_session,
        text=prompt,
    )

    # Process all frames
    for model_outputs in video_model.propagate_in_video_iterator(
        inference_session=inference_session,
        max_frame_num_to_track=max_frames
    ):
        processed = video_processor.postprocess_outputs(...)
        # Save per-frame masks
```

## Troubleshooting

### SAM3 Not Loading

```bash
# Check inference container status
docker logs inference 2>&1 | tail -20

# Verify transformers has SAM3 support
docker exec inference python3 -c "from transformers import Sam3Model; print('OK')"

# Check GPU memory
nvidia-smi
```

### No Masks Found

1. Check prompt specificity - use `"robot arm"` not `"arm"`
2. Lower threshold: `segment_by_text(..., threshold=0.3)`
3. Verify image has the object visible

### Slow Inference

- First run downloads model (~2GB)
- Subsequent runs use cached model
- Video segmentation loads separate video model

### Memory Issues

```python
# Unload SAM3 before loading VLM
sam_unload_model()

# Check status
sam_status()
# Returns: {"sam3_loaded": False, "gpu_info": {...}}
```

## Performance Considerations

### GPU Memory

- SAM3 alone: ~8GB VRAM
- SAM3 + VLM: May exceed 24GB - unload one first
- Use `float16` dtype (bfloat16 causes errors in post-processing)

### Inference Speed

| Operation | Typical Time |
|-----------|--------------|
| Model load | 10-30s (first time includes download) |
| Single image segment | 0.5-2s |
| Video (50 frames) | 30-60s |

### Mask Storage

- Masks saved as `.npy` files in shared directory
- Automatically cleaned up after use
- Large video runs may accumulate GB of mask files
