# Debug Interface System

## Overview

The debug interface is a web-based visualization system that aggregates all media outputs (images, videos, analysis results) from the MCP server into a single browsable interface. It uses **Gradio** as the HTTP server framework and **Cloudflare Quick Tunnels** for public URL generation.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Debug Interface                              │
│                                                                      │
│  ┌─────────────────┐     ┌─────────────────┐     ┌──────────────┐  │
│  │ RequestTracker  │────▶│  DebugInterface │────▶│ Gradio UI    │  │
│  │ (Storage)       │     │  (Build/Launch) │     │ (HTTP:7860)  │  │
│  └─────────────────┘     └─────────────────┘     └──────────────┘  │
│                                                          │          │
│                                                          ▼          │
│                                                  ┌──────────────┐  │
│                                                  │ Cloudflare   │  │
│                                                  │ Tunnel       │  │
│                                                  │ (Public URL) │  │
│                                                  └──────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. RequestTracker (`debug_interface.py`)

The `RequestTracker` class manages all media requests and their metadata.

**Key Responsibilities:**
- Track image/video/tool outputs with unique request IDs (`req_000001`, `req_000002`, etc.)
- Store metadata: timestamps, prompts, analysis results, file paths
- Persist session data to disk for recovery
- Generate thumbnails for gallery display

**Storage Structure:**
```
/tmp/debug_sessions/
└── session_YYYYMMDD_HHMMSS/
    ├── requests.json           # Request metadata
    ├── req_000001.jpg          # Media files
    ├── req_000001_thumb.jpg    # Thumbnails
    ├── req_000002.mp4
    └── ...
```

**Request Types:**
| Type | Description | Sources |
|------|-------------|---------|
| `image` | Static image capture | `get_camera_frame`, `capture_multi_view` |
| `video` | Video recording | `capture_video_clip`, `create_video_from_frames` |
| `tool_output` | Tool-generated media | `render_rotating_mesh`, `debug_add_media` |
| `vlm_query` | VLM analysis with image/video | `vlm_query_image`, `vlm_query_video` |
| `sam_segment` | SAM3 segmentation results | `colorize_region`, `mask_background` |

### 2. DebugInterface Class

Builds and launches the Gradio web interface.

**Features:**
- Gallery view of all media
- Detail view with full metadata
- Search and filter by request type
- Session import from previous runs
- Real-time updates

### 3. Cloudflare Quick Tunnel Integration

**Why Cloudflare Instead of Gradio Share:**
- Gradio share (`share=True`) uses `gradio-live.com` which frequently times out
- Cloudflare Quick Tunnels are more reliable and don't require authentication
- Random subdomain: `https://<random-words>.trycloudflare.com`

**Implementation (`CloudflareTunnel` class):**

```python
class CloudflareTunnel:
    """Manages a Cloudflare Quick Tunnel for exposing local services publicly."""

    def __init__(self, local_port: int = 7860):
        self.local_port = local_port
        self._process: Optional[subprocess.Popen] = None
        self._public_url: Optional[str] = None
        self._log_file = Path("/tmp/cloudflared_tunnel.log")

    def start(self, timeout: int = 30) -> Optional[str]:
        """Start tunnel and return public URL."""
        # Check if cloudflared is installed
        result = subprocess.run(["which", "cloudflared"], capture_output=True)
        if result.returncode != 0:
            return None

        self.stop()  # Kill any existing tunnel

        # Start cloudflared in background
        log_handle = open(self._log_file, "w")
        self._process = subprocess.Popen(
            ["cloudflared", "tunnel", "--url", f"http://localhost:{self.local_port}"],
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

        # Wait for URL to appear in logs
        url_pattern = re.compile(r'https://[a-z0-9-]+\.trycloudflare\.com')
        start_time = time.time()

        while time.time() - start_time < timeout:
            time.sleep(1)
            with open(self._log_file, "r") as f:
                log_content = f.read()
            match = url_pattern.search(log_content)
            if match:
                self._public_url = match.group(0)
                return self._public_url

        return None

    def stop(self) -> None:
        """Stop the tunnel process."""
        if self._process and self._process.poll() is None:
            self._process.terminate()
            self._process.wait(timeout=5)
        self._process = None
        self._public_url = None
```

**Installation:**
```bash
# Install cloudflared CLI
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared
chmod +x /usr/local/bin/cloudflared
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG_PORT` | `7860` | Gradio HTTP server port |
| `DEBUG_SHARE` | `true` | Enable Cloudflare tunnel for public URL |
| `DEBUG_SESSION_BASE` | `/tmp/debug_sessions` | Base directory for session storage |

## Shared Directories

The debug interface relies on shared volume mounts between the host, inference container, and debug interface:

| Directory | Purpose | Container Access |
|-----------|---------|------------------|
| `/tmp/isaac_sim_output` | Camera frames, videos, masks | Isaac Sim, Inference, Host |
| `/tmp/debug_sessions` | Session storage, thumbnails | Host only (MCP server) |
| `./exports` | Persistent exports | Isaac Sim, Inference |

## MCP Tools

### Core Debug Tools

| Tool | Description |
|------|-------------|
| `debug_url` | Get current debug interface URL |
| `restart_debug_interface` | Restart with new settings |
| `debug_import_session` | Import previous session data |
| `debug_add_media` | Add external media file |

### Query Tools

| Tool | Description |
|------|-------------|
| `debug_list_requests` | List all tracked requests |
| `debug_get_request` | Get details for specific ID |
| `debug_get_latest` | Get most recent request(s) |
| `debug_search_requests` | Search by prompt/answer text |
| `debug_verify_output` | Verify media files exist |
| `debug_get_session_info` | Get session storage info |
| `debug_clear_requests` | Clear all requests (requires confirm) |

## Media Flow

### 1. Camera Capture Flow

```
get_camera_frame()
    │
    ├── Capture frame from Isaac Sim
    │
    ├── Save to /tmp/isaac_sim_output/frame_XXXX.jpg
    │
    ├── Run quality analysis (entropy, sharpness)
    │
    └── Register with RequestTracker
            │
            └── Copy to session directory
                    │
                    └── Generate thumbnail
```

### 2. Video Creation Flow

```
create_video_from_frames()
    │
    ├── Run ffmpeg on frame sequence
    │
    ├── Save to /tmp/isaac_sim_output/video.mp4
    │
    ├── Run motion analysis (optional)
    │
    └── Register with RequestTracker
            │
            └── Copy to session directory
```

### 3. External Media Flow

```
debug_add_media(file_path, description, source_name)
    │
    ├── Validate file exists and type
    │
    ├── Copy to session directory
    │
    ├── Generate thumbnail (for images)
    │
    └── Return request_id and debug_url
```

## VLM Integration

The debug interface tracks all VLM queries with their associated media:

```python
# VLM query registration
tracker.add_vlm_request(
    prompt="Is the robot arm moving?",
    image_path="/tmp/isaac_sim_output/frame.jpg",
    thinking="The robot arm appears to be...",
    answer="Yes, the arm is moving left",
    success=True,
)
```

**Stored Metadata:**
- Original prompt
- Image/video file path
- Model thinking (chain-of-thought)
- Final answer
- Processing time
- Success/failure status

## Video Integration

### Automatic Motion Analysis

Videos are automatically analyzed for motion detection:

```python
motion_result = analyze_video_motion(
    video_path,
    sample_fps=4,
    motion_threshold=25,
    min_motion_area=0.5
)
# Returns:
{
    "motion_detected": True,
    "motion_percentage": 85.0,
    "stuck_detected": False,
    "frames_with_motion": 34,
    "total_frames": 40,
}
```

### Stuck Detection

If `motion_percentage < 20%`, `stuck_detected` is set to `True`, indicating the robot may be frozen.

## Session Management

### Session Lifecycle

1. **Creation**: New session created on MCP server startup
2. **Active**: Requests added during operation
3. **Persistence**: Session data saved to disk
4. **Recovery**: Previous sessions can be imported

### Session Import

```python
# List available sessions
debug_import_session(list_sessions=True)
# Returns: ["session_20260123_100804", "session_20260122_143022", ...]

# Import specific session
debug_import_session(source_session="session_20260123_100804")
# Imports all requests from that session into current debug interface
```

## Gradio Interface Structure

The Gradio interface is built with these components:

```python
with gr.Blocks() as app:
    # Header
    gr.Markdown("# Debug Interface")

    # Gallery tab
    with gr.Tab("Gallery"):
        gallery = gr.Gallery(label="All Media")
        filter_dropdown = gr.Dropdown(choices=["all", "image", "video", "vlm_query"])

    # Detail tab
    with gr.Tab("Detail"):
        request_id = gr.Textbox(label="Request ID")
        metadata = gr.JSON(label="Metadata")
        image = gr.Image(label="Image")
        video = gr.Video(label="Video")

    # Search tab
    with gr.Tab("Search"):
        query = gr.Textbox(label="Search Query")
        results = gr.Dataframe(label="Results")
```

## Troubleshooting

### Debug Interface Not Starting

```bash
# Check if port is in use
lsof -i :7860

# Kill existing process
kill $(lsof -t -i:7860)

# Restart via MCP
restart_debug_interface(share=True)
```

### Cloudflare Tunnel Not Working

```bash
# Check if cloudflared is installed
which cloudflared

# Check tunnel logs
cat /tmp/cloudflared_tunnel.log

# Manually start tunnel for testing
cloudflared tunnel --url http://localhost:7860
```

### Media Not Showing

1. Check file exists: `ls -la /tmp/isaac_sim_output/`
2. Check permissions: Files need to be readable
3. Check session storage: `debug_get_session_info()`
4. Verify request tracking: `debug_list_requests(limit=5)`

## Performance Considerations

- **Thumbnail Generation**: Large images are resized to 256x256 for gallery
- **Video Thumbnails**: First frame is extracted as thumbnail
- **Session Size**: Old sessions are not auto-pruned; clear manually with `debug_clear_requests(confirm=True)`
- **Memory**: Gradio caches recent requests in memory
