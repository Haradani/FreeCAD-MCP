# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Important Coding Guidelines

**NO FALLBACKS OR DUMMY DATA**: Never implement fallback behaviors that return random, static, or placeholder data. If an operation fails, it should raise an error with a clear message. This applies to:
- Mock/placeholder data when services are unavailable
- Default values that mask failures
- Silent fallbacks that hide errors from the user

Always prefer explicit failure over silent degradation. The user needs to know when something isn't working.

## Build and Development Commands

```bash
# Install in development mode
pip install -e .

# With dev dependencies (pytest, ruff, mypy)
pip install -e ".[dev]"

# Run tests
pytest                    # All tests
pytest tests/test_mcp_server.py  # Single file
pytest -k "test_name"     # Single test by name

# Code quality
ruff check src/           # Linting
mypy src/                 # Type checking
```

## Running the Application

```bash
# Start FreeCAD container (required)
docker compose up freecad -d

# With VNC GUI access (ports 3000/5900)
ENABLE_GUI=true docker compose up freecad -d

# Start Vision AI container (optional, requires NVIDIA GPU)
docker compose --profile vision up -d

# Start TRELLIS.2 for 3D generation (optional, requires NVIDIA GPU)
docker compose --profile trellis up -d

# Start ComfyUI for text-to-image (optional, requires NVIDIA GPU)
docker compose --profile diffusion up -d

# Start all GPU services
docker compose --profile full up -d

# Run MCP server (for Claude Desktop integration)
python -m src.mcp_server

# Run Gradio debug interface standalone
python -m src.debug_interface --port 7860
```

## Architecture

```
AI Model (Claude/GPT-4o/Gemini)
    │ MCP Protocol (JSON-RPC 2.0)
    ▼
MCP Server (src/mcp_server.py) ──── Gradio UI (src/debug_interface.py)
    │                                        │ Cloudflare tunnel
    ├── XML-RPC (port 9875) ────────────────►│
    │                                        ▼
    ▼                              ┌─────────────────────────────┐
FreeCAD Container ◄───────────────►│  Inference Container        │
(docker/freecad/rpc_server.py)     │  - Cosmos VLM on cuda:0     │
    ▲                              │  - SAM3 on cuda:1           │
    │                              └─────────────────────────────┘
    │  HTTP (port 8188)
    ├───────────────────────────────► ComfyUI Container
    │                                  (docker/diffusion/)
    │                                  - Z-Image Turbo text-to-image
    │  HTTP (port 8000)
    └───────────────────────────────► TRELLIS.2 Container
                                       (docker/trellis/)
                                       - Image-to-3D mesh generation
```

**Key component connections:**
- `mcp_server.py` → `freecad_client.py` → `docker/freecad/rpc_server.py` (XML-RPC)
- `mcp_server.py` → `inference_client.py` → `docker/inference/server.py` (ZMQ port 5555)
- `mcp_server.py` → `trellis_client.py` → `docker/trellis/server.py` (HTTP port 8000)
- `mcp_server.py` → `diffusion_client.py` → ComfyUI (HTTP port 8188)
- `mcp_server.py` → `docker_client.py` → Docker Compose (subprocess)
- `mcp_server.py` → `tunnel_client.py` → cloudflared (subprocess)
- Tools use Pydantic models for input validation (`src/mcp_server.py:47+`)

## Adding New MCP Tools

Follow this pattern in `src/mcp_server.py`:

1. **Define Pydantic input model** (around line 100+):
```python
class MyToolInput(BaseModel):
    """Input for my_tool tool."""
    param: str = Field(description="Parameter description")
    optional_param: int = Field(default=10, description="Optional with default")
```

2. **Register tool** in `@server.list_tools()` (around line 700+):
```python
Tool(
    name="my_tool",
    description="What this tool does",
    inputSchema=MyToolInput.model_json_schema(),
),
```

3. **Implement handler** in `@server.call_tool()` (around line 1100+):
```python
elif name == "my_tool":
    inp = MyToolInput(**arguments)
    # Implementation here
    return [TextContent(type="text", text="Result")]
```

## MCP Tools Reference

### Document Management
| Tool | Description |
|------|-------------|
| `create_document` | Create a new FreeCAD document |
| `open_document` | Open an existing FreeCAD document (.FCStd file) |
| `save_document` | Save a FreeCAD document to file |
| `close_document` | Close a FreeCAD document |
| `list_documents` | List all open FreeCAD documents |

### Part Primitives
| Tool | Description |
|------|-------------|
| `create_primitive` | Create a Part primitive shape (box, cylinder, sphere, cone, torus) |
| `boolean_operation` | Perform boolean operation (union, cut, intersect) on two objects |
| `transform_object` | Transform an object (translate, rotate, scale) |
| `fillet_chamfer` | Add fillet or chamfer to object edges |

### PartDesign (Parametric Modeling)
| Tool | Description |
|------|-------------|
| `create_body` | Create a PartDesign Body container for parametric modeling |
| `create_sketch` | Create a parametric sketch on a plane or face |
| `add_sketch_geometry` | Add geometry (line, circle, arc, rectangle, polygon) to a sketch |
| `add_sketch_constraint` | Add constraint to a sketch (coincident, horizontal, vertical, distance, angle, etc.) |
| `pad_sketch` | Extrude (pad) a sketch into a solid |
| `pocket_sketch` | Cut a pocket from a sketch |

### Draft (2D)
| Tool | Description |
|------|-------------|
| `draft_line` | Create a 2D draft line |
| `draft_rectangle` | Create a 2D draft rectangle |
| `draft_circle` | Create a 2D draft circle |

### Object Operations
| Tool | Description |
|------|-------------|
| `get_objects` | List all objects in a document |
| `get_object_info` | Get detailed information about an object |
| `edit_object` | Modify object properties |
| `delete_object` | Delete an object from the document |

### Import/Export
| Tool | Description |
|------|-------------|
| `export_model` | Export model to STEP, STL, OBJ, or IGES format |
| `import_model` | Import model from STEP, STL, or other formats |
| `import_mesh` | Import a mesh file (GLB, OBJ, STL) into FreeCAD. GLB files are automatically converted. |

### View/Rendering
| Tool | Description |
|------|-------------|
| `get_view` | Capture a viewport screenshot of the current model |
| `set_view` | Set the camera view angle |
| `screenshot_webpage` | Take a screenshot of a webpage using a headless browser |
| `render_spinning_video` | Render a spinning video of a 3D model using VTK offscreen rendering with lighting |
| `analyze_video` | Extract keyframes from video, create collage, and analyze with VLM |

### Measurement
| Tool | Description |
|------|-------------|
| `measure_distance` | Measure distance between two objects |
| `get_bounding_box` | Get the bounding box of an object |

### Code Execution
| Tool | Description |
|------|-------------|
| `execute_code` | Execute Python code in FreeCAD context (advanced users) |

### 3D Generation (TRELLIS.2 + ComfyUI)
| Tool | Description |
|------|-------------|
| `generate_3d_from_text` | Generate a 3D mesh from a text description. Uses ComfyUI for image generation and TRELLIS.2 for 3D conversion. |
| `generate_3d_from_image` | Generate a 3D mesh from an image using TRELLIS.2 |
| `get_trellis_status` | Get TRELLIS.2 service status including model load state and GPU info |
| `load_trellis_model` | Explicitly load the TRELLIS.2 model into GPU memory |
| `unload_trellis_model` | Unload the TRELLIS.2 model to free GPU memory |

### Docker Service Management
| Tool | Description |
|------|-------------|
| `start_docker_service` | Start a Docker service with optional GPU assignment. Services: freecad, trellis, diffusion, inference |
| `stop_docker_service` | Stop a running Docker service. Use force=true to kill immediately. |
| `get_docker_status` | Get status of Docker services (running, health, ports) |
| `list_docker_services` | List all available Docker services that can be managed |
| `get_docker_logs` | Get recent logs from a Docker service for debugging |
| `get_gpu_status` | Get GPU status including memory usage for each GPU |
| `get_full_status` | Get comprehensive status of all services and GPUs in one call |

### Cloudflare Tunnel Management
| Tool | Description |
|------|-------------|
| `create_tunnel` | Create a Cloudflare Quick Tunnel to expose a local port with a public URL |
| `stop_tunnel` | Stop a running Cloudflare tunnel by name |
| `list_tunnels` | List all active Cloudflare tunnels with their public URLs |
| `check_tunnel_health` | Ping tunnel public URLs and verify HTTP 200 response. Optionally auto-recreate failed tunnels. |

### Vision AI (Inference Container)
| Tool | Description |
|------|-------------|
| `load_vlm` | Load the Vision Language Model (Cosmos VLM) into GPU memory |
| `unload_vlm` | Unload the Vision Language Model to free GPU memory |
| `load_sam` | Load the SAM3 segmentation model into GPU memory |
| `unload_sam` | Unload the SAM3 model to free GPU memory |
| `get_inference_status` | Get status of the inference container including VLM/SAM load state |
| `analyze_image` | Analyze an image using the Vision Language Model |

### Segmentation Pipeline (SAM + VLM)
| Tool | Description |
|------|-------------|
| `segment_grid` | Segment image using grid of sample points, returns colorized regions with legend |
| `segment_points` | Segment specific points in image with distinct colors |
| `segment_and_analyze` | Combined SAM segmentation + VLM analysis: colorize regions then describe them |
| `colorize_region` | Segment and colorize a single region at a specific point |
| `identify_and_segment` | Two-pass: VLM identifies features, then SAM segments and VLM analyzes colorized result |

### Gallery Interface
| Tool | Description |
|------|-------------|
| `launch_gallery` | Launch a Gradio gallery to view cached images, 3D models, and VLM analyses with optional public Cloudflare tunnel |

## Cache Management

Output files are stored in timestamped session directories under `cache/` in the project root.

```
cache/
├── session_20260124_120000/
│   ├── screenshots/
│   ├── segmentation/
│   ├── videos/
│   └── generated_models/
└── session_20260124_140000/
```

- Automatic cleanup on startup: if total size > 1GB and more than 1 session exists, oldest sessions are deleted
- All tools that produce output files use the cache system by default
- Tools accept optional `output_dir` parameter to override

**API:**
```python
from src.cache_manager import get_output_path, get_session_dir

path = get_output_path("result.png", "segmentation")
# Returns: cache/session_YYYYMMDD_HHMMSS/segmentation/result.png
```

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `FREECAD_HOST` | localhost | FreeCAD XML-RPC host |
| `FREECAD_PORT` | 9875 | FreeCAD XML-RPC port |
| `INFERENCE_HOST` | localhost | Vision AI ZMQ host |
| `INFERENCE_PORT` | 5555 | Vision AI ZMQ port |
| `VLM_QUANTIZATION` | 4bit | VLM quantization (4bit, 8bit, none) |
| `VLM_DEVICE` | cuda:0 | GPU for Cosmos VLM |
| `SAM_DEVICE` | cuda:1 | GPU for SAM3 |
| `TRELLIS_HOST` | localhost | TRELLIS.2 HTTP host |
| `TRELLIS_PORT` | 8000 | TRELLIS.2 HTTP port |
| `TRELLIS_DEVICE` | cuda:1 | GPU selection (cuda:0/cuda:1/auto) |
| `DIFFUSION_HOST` | localhost | ComfyUI HTTP host |
| `DIFFUSION_PORT` | 8188 | ComfyUI HTTP port |

## GPU Configuration

**GPU Memory Usage:**
- TRELLIS.2: ~20-24GB VRAM (auto-selects GPU with most free memory)
- ComfyUI/Z-Image Turbo: ~8GB VRAM
- VLM (4-bit): ~5GB on cuda:0
- SAM: ~2.5GB on cuda:1

**GPU Assignment:**
```python
start_docker_service(service_name="trellis", gpus="1")
start_docker_service(service_name="diffusion", gpus="0")
start_docker_service(service_name="inference", gpus="0,1")
```

## Key Files

| File | Purpose |
|------|---------|
| `src/mcp_server.py` | Main MCP server with all tool definitions |
| `src/cache_manager.py` | Session-based file caching with auto-cleanup |
| `src/gallery_interface.py` | Gradio gallery for viewing cached content |
| `src/docker_client.py` | Docker Compose service management |
| `src/tunnel_client.py` | Cloudflare Quick Tunnel management |
| `src/inference_client.py` | ZMQ client for VLM/SAM inference container |
| `src/segmentation_pipeline.py` | Combined SAM + VLM pipeline |
| `src/trellis_client.py` | HTTP client for TRELLIS.2 3D generation |
| `src/diffusion_client.py` | HTTP client for ComfyUI image generation |
| `src/freecad_client.py` | XML-RPC client for FreeCAD container |
| `src/code_security.py` | AST-based security for execute_code tool |
| `docker/freecad/rpc_server.py` | XML-RPC server running inside FreeCAD container |
| `docker/freecad/render_video.py` | VTK-based video rendering (runs in container) |
| `docker-compose.yml` | Service definitions with GPU configs |

## Cloudflare Tunnels

Create temporary public URLs for local services. Requires `cloudflared`:

```bash
wget -O ~/.local/bin/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
chmod +x ~/.local/bin/cloudflared
```

```python
create_tunnel(name="gallery", local_port=7865)
# Returns: https://xxx-xxx-xxx.trycloudflare.com

check_tunnel_health(auto_recreate=True)  # Verify and auto-fix
```

## Security

The `execute_code` tool uses `src/code_security.py` with AST analysis to block dangerous imports (os, subprocess, sys, socket) and builtins (eval, exec, open).
