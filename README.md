# FreeCAD MCP Server

An MCP (Model Context Protocol) server that integrates FreeCAD with AI models (Claude, GPT-4o, Gemini), providing natural language CAD control, Docker-containerized headless execution, Vision AI analysis, and AI-powered 3D generation.

## Features

- **Natural Language CAD Control**: 57 MCP tools for comprehensive CAD operations
- **Docker-Containerized FreeCAD**: Headless execution with optional VNC GUI access
- **AI 3D Generation**: TRELLIS.2 for image-to-3D, ComfyUI for text-to-image generation
- **Gradio Web Interface**: Debug interface with request tracking and image gallery
- **Cloudflare Quick Tunnels**: Public URL access without port forwarding
- **Vision AI Integration**: Cosmos VLM for model analysis, SAM3 for segmentation
- **Docker Service Management**: Start/stop/monitor all services from MCP tools
- **Dual GPU Support**: Optimized for dual 24GB 3090 setup with automatic quantization

## Architecture

```
┌─────────────────┐
│  AI Model       │ (Claude/GPT-4o/Gemini)
└────────┬────────┘
         │ MCP Protocol (JSON-RPC 2.0)
┌────────▼────────┐
│  MCP Server     │ ← 57 tools
│  + Gradio UI    │ ← Web interface + tunnel
└────────┬────────┘
         │
    ┌────┴────┬─────────────┬─────────────┐
    │         │             │             │
    ▼         ▼             ▼             ▼
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│ FreeCAD │ │ TRELLIS │ │ ComfyUI │ │Inference│
│ :9875   │ │ :8000   │ │ :8188   │ │ :5555   │
│ XML-RPC │ │ HTTP    │ │ HTTP    │ │ ZMQ     │
└─────────┘ └─────────┘ └─────────┘ └─────────┘
 Headless    Image→3D   Text→Image   VLM+SAM
```

## Quick Start

### Prerequisites

- **Docker Engine**: Install from [docs.docker.com/engine/install](https://docs.docker.com/engine/install/)
- **Docker Compose**: Included with Docker Desktop, or install separately for Linux
- **NVIDIA Container Toolkit** (for GPU services): Install from [docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
- **Python 3.10+**

```bash
# Verify Docker installation
docker --version
docker compose version

# Verify NVIDIA Container Toolkit (optional, for GPU services)
docker run --rm --gpus all nvidia/cuda:12.1-base nvidia-smi
```

### 1. Start FreeCAD Container

```bash
# Start FreeCAD only
docker compose up freecad -d

# Or start with GUI (VNC access on port 3000)
ENABLE_GUI=true docker compose up freecad -d
```

### 2. Install MCP Server

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e .
```

### 3. Run MCP Server

```bash
# For Claude Desktop integration
python -m src.mcp_server

# Or run debug interface standalone
python -m src.debug_interface --port 7860
```

### 4. Configure MCP Client

There are two ways to configure the MCP server with your AI client:

#### Option A: Project-level `.mcp.json` (Recommended)

Create a `.mcp.json` file in the project root (copy from example):

```bash
cp .mcp.json.example .mcp.json
```

Edit `.mcp.json` and update the `cwd` path to your installation directory:

```json
{
  "mcpServers": {
    "freecad": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/absolute/path/to/freecad_mcp",
      "env": {
        "FREECAD_HOST": "localhost",
        "FREECAD_PORT": "9875",
        "TRELLIS_HOST": "localhost",
        "TRELLIS_PORT": "8000",
        "DIFFUSION_HOST": "localhost",
        "DIFFUSION_PORT": "8188"
      }
    }
  }
}
```

MCP clients like Claude Code will automatically detect and use this configuration when working in the project directory.

#### Option B: Global Claude Desktop Configuration

Add to `~/.config/claude-desktop/config.json` (Linux) or `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "freecad": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/absolute/path/to/freecad_mcp"
    }
  }
}
```

**Note:** The `cwd` path must be absolute (e.g., `/home/user/freecad_mcp`, not `~/freecad_mcp`).

## Available Tools

### Document Management
- `create_document` - Create new FreeCAD document
- `open_document` - Open existing .FCStd file
- `save_document` - Save document to file
- `close_document` - Close document
- `list_documents` - List all open documents

### Part Primitives
- `create_primitive` - Create Box, Cylinder, Sphere, Cone, Torus
- `boolean_operation` - Union, Cut, Intersect operations
- `transform_object` - Move, rotate, scale objects
- `fillet_chamfer` - Add fillets or chamfers to edges

### Part Design (Parametric)
- `create_body` - Create PartDesign Body container
- `create_sketch` - Create parametric sketch on plane/face
- `add_sketch_geometry` - Add lines, circles, arcs, rectangles
- `add_sketch_constraint` - Add dimensional and geometric constraints
- `pad_sketch` - Extrude sketch into solid
- `pocket_sketch` - Cut pocket from sketch

### Draft (2D)
- `draft_line` - Create 2D line
- `draft_rectangle` - Create 2D rectangle
- `draft_circle` - Create 2D circle

### General Operations
- `get_objects` - List all objects
- `get_object_info` - Detailed object introspection
- `edit_object` - Modify object properties
- `delete_object` - Remove object
- `execute_code` - Run arbitrary Python (with security checks)
- `export_model` - Export to STEP, STL, OBJ, IGES
- `import_model` - Import from various formats

### View/Rendering
- `get_view` - Capture viewport screenshot
- `set_view` - Set camera angle
- `screenshot_webpage` - Take screenshot of web interface
- `render_spinning_video` - Render spinning video of 3D model

### Measurement
- `measure_distance` - Distance between objects
- `get_bounding_box` - Object bounding box

### 3D Generation (TRELLIS.2 + ComfyUI)
- `generate_3d_from_text` - Text description → 3D mesh (via image generation)
- `generate_3d_from_image` - Image → 3D mesh
- `get_trellis_status` - Check TRELLIS.2 model status
- `load_trellis_model` / `unload_trellis_model` - GPU memory management
- `import_mesh` - Import GLB/OBJ/STL into FreeCAD

### Docker Service Management
- `start_docker_service` - Start container (freecad, trellis, diffusion, inference)
- `stop_docker_service` - Stop container
- `get_docker_status` - Check container status
- `list_docker_services` - List available services
- `get_docker_logs` - View container logs
- `get_gpu_status` - GPU memory usage
- `get_full_status` - Comprehensive system status

### Cloudflare Tunnels
- `create_tunnel` - Create public URL for local port
- `stop_tunnel` - Stop tunnel
- `list_tunnels` - List active tunnels

## 3D Generation (Optional)

Start TRELLIS.2 and ComfyUI for AI-powered 3D model generation:

```bash
# Start TRELLIS.2 (image-to-3D)
docker compose --profile trellis up -d

# Start ComfyUI (text-to-image)
docker compose --profile diffusion up -d

# Or start both
docker compose --profile full up -d
```

### Text-to-3D Pipeline
1. ComfyUI generates image from text prompt (Z-Image Turbo)
2. TRELLIS.2 converts image to 3D mesh (GLB)
3. Optionally imports into FreeCAD

```python
generate_3d_from_text(
    prompt="a wooden dining chair",
    import_to_freecad=True
)
```

## Vision AI (Optional)

Start the inference container for VLM and SAM capabilities:

```bash
docker compose --profile vision up -d
```

### VLM Features
- Analyze CAD models with natural language
- Validate designs against requirements
- Get improvement suggestions
- Analyze spinning videos of 3D models

### SAM Features
- Segment features by clicking points
- Measure feature areas
- Highlight specific features

### Combined SAM + VLM Pipeline
- `segment_and_analyze` - Colorize regions with SAM, then have VLM describe each
- `segment_grid` - Auto-detect regions using grid sampling
- `segment_points` - Segment specific points with labels
- `identify_and_segment` - Two-pass: VLM identifies features, SAM segments, VLM analyzes
- Automatic container and model lifecycle management

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FREECAD_HOST` | localhost | FreeCAD container hostname |
| `FREECAD_PORT` | 9875 | XML-RPC port |
| `INFERENCE_HOST` | localhost | Inference container hostname |
| `INFERENCE_PORT` | 5555 | ZMQ port |
| `ENABLE_TUNNEL` | true | Enable Cloudflare Quick Tunnel |
| `VLM_QUANTIZATION` | 4bit | VLM quantization (4bit, 8bit, none) |

### GPU Configuration

The system auto-detects GPU configuration:

- **Single 48GB+ GPU**: Full precision models
- **Dual 24GB GPUs**: VLM on GPU 0 (4-bit), SAM on GPU 1

**GPU Memory Usage:**
| Service | VRAM | Default GPU |
|---------|------|-------------|
| TRELLIS.2 | ~20-24GB | cuda:1 (auto-selects) |
| ComfyUI | ~8GB | cuda:0 |
| VLM (4-bit) | ~5GB | cuda:0 |
| SAM | ~2.5GB | cuda:1 |

Use `get_gpu_status()` to check memory before starting services.

## Project Structure

```
freecad_mcp/
├── src/
│   ├── mcp_server.py          # Main MCP server (57 tools)
│   ├── cache_manager.py       # Session-based file caching
│   ├── freecad_client.py      # FreeCAD XML-RPC client
│   ├── docker_client.py       # Docker service management
│   ├── tunnel_client.py       # Cloudflare tunnel management
│   ├── segmentation_pipeline.py # SAM + VLM combined analysis
│   ├── trellis_client.py      # TRELLIS.2 HTTP client
│   ├── diffusion_client.py    # ComfyUI HTTP client
│   ├── inference_client.py    # Vision AI ZMQ client
│   ├── debug_interface.py     # Gradio web interface
│   └── code_security.py       # Code execution safety
├── docker/
│   ├── freecad/
│   │   ├── Dockerfile
│   │   ├── rpc_server.py      # FreeCAD XML-RPC server
│   │   └── render_video.py    # Headless video rendering
│   ├── inference/
│   │   ├── Dockerfile
│   │   └── server.py          # Vision AI ZMQ server
│   ├── trellis/
│   │   ├── Dockerfile
│   │   └── server.py          # TRELLIS.2 HTTP server
│   └── diffusion/
│       └── Dockerfile         # ComfyUI + workflows
├── cache/                     # Output files (auto-managed, 1GB limit)
│   └── session_YYYYMMDD_HHMMSS/
├── data/
│   └── trellis/outputs/       # Generated 3D meshes
├── tests/
├── docker-compose.yml
└── pyproject.toml
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src/

# Linting
ruff check src/
```

## Security

The `execute_code` tool has security checks to prevent:
- Dangerous module imports (os, subprocess, etc.)
- File system operations
- Network access
- FreeCAD session termination

For advanced operations, review the code security policy in `src/code_security.py`.

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`pytest`)
5. Run linting (`ruff check src/`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

### Development Setup

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/freecad-mcp.git
cd freecad-mcp

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Configure MCP server
cp .mcp.json.example .mcp.json
# Edit .mcp.json and set "cwd" to your absolute path (e.g., /home/user/freecad-mcp)

# Start FreeCAD container
docker compose up freecad -d

# Run tests
pytest
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
