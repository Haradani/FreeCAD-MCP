# Vision Language Model (VLM) System

## Overview

The VLM system provides visual reasoning capabilities using NVIDIA's **Cosmos-Reason2-8B** model. It enables natural language queries about images and videos, supporting robotics and physical AI applications with chain-of-thought reasoning.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              MCP Server (Host)                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        VLM Tools Layer                               │    │
│  │  vlm_query_image │ vlm_query_video │ vlm_query_image_sequence       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    CosmosVLM Client (cosmos_vlm.py)                  │    │
│  │  - Model loading/unloading                                           │    │
│  │  - Image quality validation                                          │    │
│  │  - Chain-of-thought parsing                                          │    │
│  │  - Message building for Qwen3-VL architecture                        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                                    ▼ ZMQ (port 5560)                        │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    Inference Container                               │    │
│  │  - Cosmos-Reason2-8B model (32GB VRAM)                              │    │
│  │  - Qwen3VLProcessor for tokenization                                │    │
│  │  - qwen_vl_utils for vision processing                              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Model Specifications

### Cosmos-Reason2-8B

| Property | Value |
|----------|-------|
| **Model ID** | `nvidia/Cosmos-Reason2-8B` |
| **Architecture** | Qwen3-VL (Vision-Language) |
| **Parameters** | 8 billion |
| **VRAM Required** | 32GB+ (tested on RTX A6000, H100, A100) |
| **Context Length** | 256K tokens |
| **Optimal Video FPS** | 4 (matches training setup) |
| **Recommended max_tokens** | 4096 |

### Key Capabilities

- **Physical AI Reasoning**: Optimized for robotics and simulation understanding
- **Spatio-Temporal Analysis**: Understanding motion, position, and trajectories
- **2D/3D Point Localization**: Identifying object positions in frames
- **Chain-of-Thought Reasoning**: Structured `<think>...</think><answer>...</answer>` output
- **Multi-Image Comparison**: Comparing multiple frames for change detection

## Core Components

### 1. CosmosVLM Client (`src/cosmos_vlm.py`)

The main client class for VLM inference.

```python
class CosmosVLM:
    """Client for Cosmos-Reason2-8B vision language model inference."""

    MODEL_NAME = "nvidia/Cosmos-Reason2-8B"

    DEFAULT_SYSTEM_PROMPT = """You are an intelligent visual reasoning assistant
    for robotics and physical AI applications.
    When answering questions about images or videos, provide clear and concise reasoning.

    Answer the question in the following format:
    <think>
    your reasoning
    </think>

    <answer>
    your answer
    </answer>"""

    # Optimal settings per Cosmos-Reason2 documentation
    DEFAULT_FPS = 4  # Matches training setup
    DEFAULT_MAX_TOKENS = 4096  # Avoid truncated chain-of-thought

    def __init__(
        self,
        model_name: str = None,
        device: str = "auto",
        dtype: str = "float16",
        max_new_tokens: int = 4096,
        temperature: float = 0.6,  # Lower = more deterministic
        top_p: float = 0.9,
        top_k: int = 50,
        do_sample: bool = True,
    ):
        ...
```

**Key Methods:**

| Method | Description |
|--------|-------------|
| `load_model()` | Load Cosmos-Reason2-8B to GPU |
| `unload_model()` | Free GPU memory |
| `query_image(image_path, prompt)` | Query about a single image |
| `query_image_data(image_data, prompt)` | Query with numpy array or bytes |
| `query_image_sequence(sequence)` | Query with interleaved images/text |
| `query_video(video_path, prompt, fps)` | Query about a video |
| `query_frames(frames, prompt)` | Query with frame sequence |
| `compute_image_quality(image)` | Compute quality metrics |

### 2. Image Quality Validation

Before running inference, images are validated to prevent hallucinations on blank/low-quality frames:

```python
@staticmethod
def compute_image_quality(image: "Image.Image") -> Dict[str, Any]:
    """Compute image quality metrics to detect black/empty/low-information images.

    Returns metrics with natural language descriptions:
    - entropy: Information content (0.0=uniform, 8.0=maximum)
    - variance: Pixel variance (low = uniform color)
    - mean: Average pixel value
    - quality_level: Human-readable assessment
    """
    # Convert to grayscale numpy array
    gray = np.array(image.convert("L"), dtype=np.float32)

    # Compute metrics
    mean_val = float(np.mean(gray))
    variance = float(np.var(gray))
    std_dev = float(np.std(gray))

    # Compute entropy (information content)
    hist, _ = np.histogram(gray.flatten(), bins=256, range=(0, 256))
    hist = hist / hist.sum()
    hist = hist[hist > 0]
    entropy = float(-np.sum(hist * np.log2(hist))) if len(hist) > 0 else 0.0

    # Determine quality level
    if variance < 1.0:
        quality_level = "blank"
    elif entropy < 0.3:
        quality_level = "near_blank"
    elif entropy < 0.5:
        quality_level = "very_low"
    elif entropy < 1.0:
        quality_level = "low"
    elif entropy < 2.0:
        quality_level = "moderate"
    elif entropy < 4.0:
        quality_level = "good"
    else:
        quality_level = "high"

    return {
        "entropy": round(entropy, 3),
        "variance": round(variance, 3),
        "std_dev": round(std_dev, 3),
        "mean": round(mean_val, 3),
        "quality_level": quality_level,
        "quality_description": quality_descriptions[quality_level],
        "is_usable": quality_level not in ("blank", "near_blank", "very_low"),
    }
```

**Quality Levels:**

| Level | Entropy Range | Description |
|-------|---------------|-------------|
| `blank` | variance < 1.0 | Completely blank (all pixels identical) |
| `near_blank` | < 0.3 | Almost no visual information |
| `very_low` | 0.3 - 0.5 | Mostly uniform image |
| `low` | 0.5 - 1.0 | Simple scene with limited detail |
| `moderate` | 1.0 - 2.0 | Some visual detail present |
| `good` | 2.0 - 4.0 | Clear visual content |
| `high` | 4.0+ | Rich visual detail |

### 3. Chain-of-Thought Parsing

The VLM outputs structured reasoning that is parsed:

```python
def _parse_response(self, response: str) -> Dict[str, str]:
    """Parse the model response to extract thinking and answer."""
    result = {
        "raw": response,
        "thinking": "",
        "answer": response,
    }

    # Extract <think> content
    if "<think>" in response and "</think>" in response:
        think_start = response.index("<think>") + len("<think>")
        think_end = response.index("</think>")
        result["thinking"] = response[think_start:think_end].strip()

    # Extract <answer> content
    if "<answer>" in response and "</answer>" in response:
        answer_start = response.index("<answer>") + len("<answer>")
        answer_end = response.index("</answer>")
        result["answer"] = response[answer_start:answer_end].strip()

    return result
```

## MCP Tools

### Core VLM Tools

| Tool | Description |
|------|-------------|
| `vlm_load_model` | Load Cosmos-Reason2-8B (~32GB VRAM) |
| `vlm_unload_model` | Unload model to free GPU memory |
| `vlm_query_camera` | Capture frame and ask question |
| `vlm_query_image` | Ask question about image file |
| `vlm_query_video` | Ask question about video (auto-prepends motion analysis) |
| `vlm_query_image_sequence` | Compare multiple images |
| `vlm_status` | Check model status and GPU info |

### Tool Examples

**Image Query:**
```python
vlm_query_image(
    image_path="/tmp/isaac_sim_output/frame.jpg",
    prompt="Is the robot arm touching the cube?"
)
# Returns: {
#     "success": True,
#     "thinking": "Looking at the image, I can see a robot arm...",
#     "answer": "No, the robot arm is approximately 5cm from the cube.",
#     "image_quality": {"entropy": 4.2, "quality_level": "high", ...}
# }
```

**Video Query:**
```python
vlm_query_video(
    video_path="/tmp/isaac_sim_output/trajectory.mp4",
    prompt="Is the robot arm moving smoothly?",
    fps=4  # Matches Cosmos training
)
# Returns: {
#     "success": True,
#     "thinking": "Analyzing the video frames...",
#     "answer": "Yes, the robot arm is moving smoothly in a zigzag pattern.",
#     "motion_analysis": {...}  # Auto-prepended motion context
# }
```

**Image Sequence Comparison:**
```python
vlm_query_image_sequence(
    sequence_json='[
        {"type": "image", "path": "/tmp/frame1.jpg"},
        {"type": "text", "content": "vs"},
        {"type": "image", "path": "/tmp/frame2.jpg"},
        {"type": "text", "content": "Has the robot moved between these frames?"}
    ]'
)
```

## Automatic Motion Analysis Integration

When querying videos, motion analysis is automatically prepended to provide context:

```python
# In mcp_server.py vlm_query_video():
if include_motion_context:
    motion_result = analyze_video_motion(video_path, sample_fps=fps)
    if motion_result.get("motion_detected"):
        motion_summary = f"""
Motion Analysis Summary:
- Motion detected: Yes
- Frames with motion: {motion_result['frames_with_motion']}/{motion_result['total_frames']}
- Average motion area: {motion_result['avg_motion_area']:.1f}%
"""
        prompt = motion_summary + "\n\n" + prompt
```

This helps the VLM understand whether the scene is static or dynamic before analyzing.

## Semantic View Centering System

### auto_center_camera_on_object Tool

A unique integration of SAM3 + camera control for automatic object framing:

```python
@mcp.tool()
def auto_center_camera_on_object(
    prompt: str,
    max_iterations: int = 5,
    tolerance: float = 0.15,
    adjustment_scale: float = 0.3,
    initial_distance: float = 2.5,
    robot_prim_path: str = None,
) -> str:
    """Iteratively adjust camera position to center an object in frame using SAM3.

    Uses SAM3 segmentation to find the object, calculates centroid offset,
    and adjusts camera position until the object is centered. If the object
    is not initially visible, attempts to position camera based on robot/scene info.
    """
```

**Algorithm:**

```
1. Find robot position in scene (if available)
2. Position camera to look at estimated target
3. For each iteration:
   a. Capture frame
   b. Run SAM3 segmentation with text prompt
   c. Calculate centroid offset from image center
   d. If offset < tolerance: SUCCESS
   e. Adjust camera position based on offset
4. Return final position and image
```

**Flow Diagram:**

```
┌─────────────────────────────────────────────────────────────────┐
│                   auto_center_camera_on_object                   │
│                                                                  │
│  1. Get robot position from scene                               │
│                      ↓                                          │
│  2. Position camera at initial_distance from target             │
│                      ↓                                          │
│  ┌─────────── iteration loop ───────────┐                       │
│  │                                       │                       │
│  │  3. Capture frame (get_camera_frame)  │                       │
│  │              ↓                        │                       │
│  │  4. SAM3 segment by prompt            │                       │
│  │              ↓                        │                       │
│  │  5. Calculate centroid offset         │                       │
│  │              ↓                        │                       │
│  │  6. Check: |offset| < tolerance?      │                       │
│  │       │              │                │                       │
│  │    NO ▼           YES ▼               │                       │
│  │  Adjust camera    Return success      │                       │
│  │                                       │                       │
│  └───────────────────────────────────────┘                       │
└─────────────────────────────────────────────────────────────────┘
```

**Example Usage:**
```python
auto_center_camera_on_object(
    prompt="robot arm",
    max_iterations=5,
    tolerance=0.15,  # 15% from center acceptable
    robot_prim_path="/UR5e"
)
# Returns: {
#     "success": True,
#     "iterations": 3,
#     "final_offset": [0.05, -0.03],
#     "final_position_description": "Object centered in frame",
#     "image_path": "/tmp/.../final_frame.jpg"
# }
```

## Debug Interface Integration

All VLM queries are automatically tracked in the debug interface:

```python
# In mcp_server.py after VLM query:
tracker.add_request(
    request_type="vlm_query",
    prompt=prompt,
    image_path=image_path,
    video_path=video_path,
    thinking=result.get("thinking"),
    answer=result.get("answer"),
    success=result.get("success"),
    processing_time=elapsed_time,
)
```

**Debug Interface Display:**
- Original image/video
- Prompt text
- Model's thinking (chain-of-thought)
- Final answer
- Processing time
- Success/failure status

## Video Processing

### Frame Extraction

For video queries, the system uses `qwen_vl_utils` with fallback to OpenCV:

```python
def query_video(self, video_path: str, prompt: str, fps: int = 4):
    """Query the model with a video and prompt.

    Args:
        fps: Frames per second to sample (default: 4, matches training)
    """
    # Primary: Use qwen_vl_utils process_vision_info
    from qwen_vl_utils import process_vision_info

    messages = self._build_messages(
        prompt=prompt,
        video_path=video_path,
        fps=fps,
    )

    image_inputs, video_inputs, video_kwargs = process_vision_info(
        [messages],
        return_video_kwargs=True,
        return_video_metadata=True,
    )
    ...
```

**Fallback Method (cv2):**
```python
def _query_video_fallback(self, video_path: str, prompt: str, fps: int = 4):
    """Fallback video query using cv2 frame extraction."""
    import cv2

    cap = cv2.VideoCapture(video_path)
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    frame_interval = max(1, int(video_fps / fps))

    frames = []
    while len(frames) < 32:  # Max frames limit
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % frame_interval == 0:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append(Image.fromarray(frame_rgb))
        frame_idx += 1

    # Send frames as image sequence
    ...
```

## Inference Container Server

The VLM runs in a Docker container with ZMQ server:

```python
# docker/inference/server.py

def vlm_load() -> Dict[str, Any]:
    """Load Cosmos VLM model."""
    global _vlm_model, _vlm_processor

    model_id = "nvidia/Cosmos-Reason2-8B"
    log(f"Loading Cosmos VLM from {model_id}...")

    _vlm_processor = AutoProcessor.from_pretrained(model_id)
    _vlm_model = AutoModelForVision2Seq.from_pretrained(
        model_id,
        torch_dtype=torch.float16,
        device_map="auto",
    )

def vlm_query_image(image_path: str, prompt: str, max_tokens: int = 4096):
    """Query Cosmos VLM about an image."""
    from qwen_vl_utils import process_vision_info

    image = Image.open(image_path).convert("RGB")

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": prompt},
            ],
        }
    ]

    # Process and generate
    text = _vlm_processor.apply_chat_template(messages, ...)
    image_inputs, video_inputs = process_vision_info(messages)

    inputs = _vlm_processor(
        text=[text],
        images=image_inputs,
        ...
    ).to(_vlm_model.device)

    generated_ids = _vlm_model.generate(**inputs, max_new_tokens=max_tokens)
    ...
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `INFERENCE_PORT` | `5560` | ZMQ port for inference server |

### Model Cache

Models are cached in the HuggingFace cache directory:
- **Container path**: `/root/.cache/huggingface/`
- **Host mount**: `~/.cache/huggingface/` (via docker-compose volume)

This enables model persistence across container restarts.

## Performance Considerations

### GPU Memory Management

- **VLM requires ~32GB VRAM** - Cannot run alongside SAM3 on 24GB GPU
- **Use `vlm_unload_model()`** before loading SAM3 if memory constrained
- **dtype=float16** reduces memory vs float32

### Optimal Settings

| Setting | Recommended | Reason |
|---------|-------------|--------|
| `fps` | 4 | Matches Cosmos training data |
| `max_new_tokens` | 4096 | Prevents truncated chain-of-thought |
| `temperature` | 0.6 | Deterministic but not greedy |
| `top_p` | 0.9 | Nucleus sampling threshold |

### Quality Gating

Images with `quality_level` in `["blank", "near_blank", "very_low"]` are rejected:
- Prevents hallucinations on empty frames
- Returns error with quality metrics
- Can be bypassed with `skip_quality_check=True`

## Error Handling

### Common Issues

| Error | Cause | Solution |
|-------|-------|----------|
| "Failed to load model" | Insufficient VRAM | Use GPU with 32GB+ |
| "Image quality too low" | Blank/gray frame | Check camera/lighting |
| "video_fps not found" | Video metadata issue | Uses cv2 fallback automatically |
| "Connection refused" | Inference container not running | Start container first |

### Fallback Chain

```
1. Primary: qwen_vl_utils video processing
   └── Failure → 2. cv2 frame extraction
                     └── Failure → 3. Return error
```

## Integration Points

### With SAM3

- `auto_center_camera_on_object` uses SAM3 for object detection
- VLM can analyze SAM3 segmentation results

### With Debug Interface

- All queries logged with full metadata
- Images/videos stored in session directory
- Accessible via `debug_list_requests(request_type="vlm_query")`

### With Camera System

- `vlm_query_camera` captures frame automatically
- Quality analysis runs before inference
- Results include camera metadata

## Troubleshooting

### VLM Not Responding

```bash
# Check inference container status
docker logs inference-container 2>&1 | tail -20

# Verify ZMQ port
nc -zv localhost 5560

# Check GPU memory
nvidia-smi
```

### Poor Quality Results

1. Check image quality metrics in response
2. Ensure `fps=4` for video queries
3. Use specific prompts (avoid vague questions)
4. Verify lighting in simulation scene

### Memory Issues

```python
# Unload VLM to free memory
vlm_unload_model()

# Check status
vlm_status()
# Returns: {"loaded": False, "gpu_info": {...}}
```
