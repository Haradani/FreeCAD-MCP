# Gallery Interface API Documentation

This document describes the Gradio-based Gallery Interface for viewing and managing FreeCAD MCP session outputs including images, 3D models, videos, and VLM analyses.

## Overview

The Gallery Interface (`src/gallery_interface.py`) provides a web-based UI for browsing cached session data. It can be launched standalone or via the MCP `launch_gallery` tool, with optional Cloudflare tunnel for public access.

**Default Port:** 7865

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Gallery Interface                         │
│                    (Gradio Blocks)                           │
├─────────────────────────────────────────────────────────────┤
│  Session Selector  │  Tabs: Images | Models | Videos | VLM  │
├────────────────────┼────────────────────────────────────────┤
│  Dropdown          │  Gallery/Model3D/Video/Markdown        │
│  Refresh Button    │  Metadata DataFrames                   │
└────────────────────┴────────────────────────────────────────┘
         │                        │
         ▼                        ▼
┌─────────────────────────────────────────────────────────────┐
│                   Cache Manager                              │
│               cache/session_YYYYMMDD_HHMMSS/                │
├─────────────────────────────────────────────────────────────┤
│  screenshots/  │  generated_models/  │  *.mp4  │  *.json   │
└────────────────┴────────────────────┴─────────┴─────────────┘
```

## API Endpoints

The Gradio interface exposes several API endpoints accessible via `gradio_client` or direct HTTP POST.

### Session Management

#### `/refresh_sessions`
Refreshes and returns the list of available sessions.

**Parameters:** None

**Returns:**
```python
{
    "choices": ["session_20260125_014207 (current)", "session_20260124_180000"],
    "value": "session_20260125_014207 (current)",  # Default selection
    "__type__": "update"
}
```

**Usage:**
```python
from gradio_client import Client
client = Client("http://localhost:7865")
result = client.predict(api_name="/refresh_sessions")
```

---

#### `/update_session`
Loads all content for a selected session.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `session` | string | Session name (e.g., "session_20260125_014207 (current)") |

**Returns:** Tuple of 7 elements:
1. `images` - List of image paths for the Gallery component
2. `model_dropdown` - Update dict with model choices
3. `model_data` - DataFrame with model metadata (name, size, type)
4. `video_dropdown` - Update dict with video choices
5. `video_data` - DataFrame with video metadata (name, size, path)
6. `analysis_dropdown` - Update dict with VLM analysis choices
7. `session_info` - Markdown string with session statistics

**Example Response:**
```python
(
    ["/path/to/screenshot1.png", "/path/to/screenshot2.png"],
    {"choices": ["acoustic_guitar.glb", "castle_tower.glb"], "value": None, "__type__": "update"},
    [["acoustic_guitar.glb", "25.0 MB", "glb"], ["castle_tower.glb", "25.2 MB", "glb"]],
    {"choices": ["rotating_model.mp4"], "value": None, "__type__": "update"},
    [["rotating_model.mp4", "2048.5", "videos/rotating_model.mp4"]],
    {"choices": [], "value": None, "__type__": "update"},
    "### Session: session_20260125_014207\n- 4 images\n- 6 models\n- 1 videos\n- 0 analyses"
)
```

---

### Content Loading

#### `/load_model`
Loads a 3D model for viewing in the Model3D component.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `model_name` | string | Model filename (e.g., "acoustic_guitar.glb") |
| `session` | string | Session name |

**Returns:** Tuple of 2 elements:
1. `model_path` - Absolute path to the model file (for Model3D component)
2. `model_info` - Markdown string with model details

**Example:**
```python
result = client.predict(
    model_name="acoustic_guitar.glb",
    session="session_20260125_014207 (current)",
    api_name="/load_model"
)
# Returns: ("/path/to/acoustic_guitar.glb", "### acoustic_guitar.glb\n- Size: 25.0 MB\n...")
```

---

#### `/load_video`
Loads a video for playback.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `video_name` | string | Video filename (e.g., "rotating_model.mp4") |
| `session` | string | Session name |

**Returns:** Tuple of 2 elements:
1. `video_path` - Absolute path to the video file
2. `video_info` - Markdown string with video details

---

#### `/load_all_content`
Loads all images and models from the entire cache (all sessions).

**Parameters:** None

**Returns:** Tuple of 2 elements:
1. `all_images` - List of all image paths across all sessions
2. `all_models` - List of all model paths across all sessions

**Note:** This endpoint is useful for getting a complete overview but may be slow with many sessions.

---

## Data Structures

### Session Directory Structure
```
cache/
└── session_YYYYMMDD_HHMMSS/
    ├── screenshots/
    │   └── *.png
    ├── generated_models/
    │   └── *.glb, *.obj, *.stl
    ├── segmentation/
    │   └── *_colorized.png, *_combined.png
    ├── videos/
    │   └── *.mp4
    └── vlm_analyses/
        └── *.json
```

### Model Metadata DataFrame
| Column | Type | Description |
|--------|------|-------------|
| Name | string | Model filename |
| Size | string | File size (e.g., "25.0 MB") |
| Type | string | File extension (glb, obj, stl) |

### Video Metadata DataFrame
| Column | Type | Description |
|--------|------|-------------|
| Name | string | Video filename |
| Size (KB) | float | File size in kilobytes |
| Path | string | Relative path within session |

---

## Component Types

| Tab | Primary Component | Type |
|-----|-------------------|------|
| Images | `gr.Gallery` | Image grid with lightbox |
| 3D Models | `gr.Model3D` | Interactive 3D viewer (WebGL) |
| Videos | `gr.Video` | HTML5 video player |
| VLM Analyses | `gr.Markdown` | Formatted analysis text |

---

## Launching the Gallery

### Via MCP Tool
```python
# Start gallery with Cloudflare tunnel
launch_gallery(port=7865, create_tunnel=True)
# Returns public URL: https://xxx-xxx-xxx.trycloudflare.com
```

### Standalone
```bash
python -m src.gallery_interface --port 7865
```

### Programmatic
```python
from src.gallery_interface import create_interface

app = create_interface()
app.launch(server_name="0.0.0.0", server_port=7865)
```

---

## Client Usage Examples

### Python (gradio_client)
```python
from gradio_client import Client

client = Client("http://localhost:7865")

# Refresh sessions
sessions = client.predict(api_name="/refresh_sessions")
print(f"Available sessions: {sessions['choices']}")

# Load a session
content = client.predict(
    session=sessions['value'],
    api_name="/update_session"
)
images, model_dropdown, model_data, video_dropdown, video_data, analysis_dropdown, info = content

# Load a specific model
if model_dropdown['choices']:
    model_path, model_info = client.predict(
        model_name=model_dropdown['choices'][0],
        session=sessions['value'],
        api_name="/load_model"
    )
    print(f"Model loaded: {model_path}")
```

### HTTP (curl)
```bash
# Refresh sessions
curl -X POST http://localhost:7865/api/refresh_sessions

# Update session
curl -X POST http://localhost:7865/api/update_session \
  -H "Content-Type: application/json" \
  -d '{"data": ["session_20260125_014207 (current)"]}'
```

---

## Integration with MCP Server

The gallery integrates with the MCP server through:

1. **Shared Cache**: Both use `src/cache_manager.py` for session-based storage
2. **launch_gallery Tool**: MCP tool starts the gallery with optional tunnel
3. **Screenshot Tool**: `screenshot_webpage` can capture the gallery UI

```python
# MCP workflow example
# 1. Generate content
generate_3d_from_text(prompt="wooden chair")

# 2. Render video
render_spinning_video(model_path="/path/to/model.glb")

# 3. Launch gallery to view
launch_gallery(create_tunnel=True)
# Share the public URL with collaborators
```

---

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| "No sessions found" | Empty cache directory | Generate content first |
| Model not loading | Invalid GLB/corrupted file | Check model with external viewer |
| Video not playing | Codec not supported | Ensure MP4 with H.264 codec |
| Tunnel timeout | cloudflared not installed | Install cloudflared binary |

---

## Performance Considerations

- **Session Loading**: Large sessions (100+ files) may take 1-2 seconds to enumerate
- **Model3D**: GLB files >50MB may cause browser memory issues
- **Gallery**: Image thumbnails are generated on-demand; first load may be slow
- **Auto-cleanup**: Cache manager removes old sessions when total size exceeds 1GB

---

## Related Documentation

- `CLAUDE.md` - Main project documentation
- `docs/research/freecad_web_interface_approaches.md` - Web interface design decisions
- `src/cache_manager.py` - Cache implementation details
- `src/tunnel_client.py` - Cloudflare tunnel management
