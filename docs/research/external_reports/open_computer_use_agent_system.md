# Open Computer Use Agent: xdotool-Based Desktop Automation

## Executive Summary

Open Computer Use Agent is an open-source implementation of AI-controlled desktop automation, similar to OpenAI's Operator. It runs a full Linux desktop (Xfce) inside a Docker container with a virtual framebuffer, exposing mouse/keyboard control via a Python API. The system uses xdotool for input simulation and scrot for screenshots, with a Gradio UI for human interaction and optional noVNC access for direct viewing.

**Repository**: https://huggingface.co/spaces/likhonsheikh/open-computer-use-agent
**License**: Implied MIT
**Key Technology**: Xvfb + Xfce + xdotool + x11vnc + noVNC

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DOCKER CONTAINER                                   │
│                         (Ubuntu 22.04 base)                                  │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    DISPLAY STACK                                        │ │
│  │                                                                          │ │
│  │   ┌─────────────┐                                                       │ │
│  │   │   Xvfb      │  Virtual framebuffer                                  │ │
│  │   │  :99        │  1280x800x24 bit color                                │ │
│  │   │             │  No physical display needed                           │ │
│  │   └──────┬──────┘                                                       │ │
│  │          │                                                               │ │
│  │          ▼                                                               │ │
│  │   ┌─────────────┐                                                       │ │
│  │   │   Xfce4     │  Full desktop environment                             │ │
│  │   │  Desktop    │  Window manager, panels, apps                         │ │
│  │   │             │  Firefox ESR pre-installed                            │ │
│  │   └──────┬──────┘                                                       │ │
│  │          │                                                               │ │
│  └──────────┼───────────────────────────────────────────────────────────────┘ │
│             │                                                                 │
│             │  DISPLAY=:99                                                    │
│             │                                                                 │
│  ┌──────────┼───────────────────────────────────────────────────────────────┐ │
│  │          ▼            INPUT/OUTPUT LAYER                                 │ │
│  │                                                                          │ │
│  │   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                │ │
│  │   │  xdotool    │    │   scrot     │    │  x11vnc     │                │ │
│  │   │             │    │             │    │             │                │ │
│  │   │ • click     │    │ • screenshot│    │ VNC server  │                │ │
│  │   │ • type      │    │   capture   │    │ port 5900   │                │ │
│  │   │ • key       │    │             │    │             │                │ │
│  │   │ • mousemove │    │             │    │             │                │ │
│  │   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                │ │
│  │          │                  │                  │                        │ │
│  └──────────┼──────────────────┼──────────────────┼────────────────────────┘ │
│             │                  │                  │                          │
│             │                  │                  │                          │
│  ┌──────────┼──────────────────┼──────────────────┼────────────────────────┐ │
│  │          ▼                  ▼                  ▼                        │ │
│  │   ┌──────────────────────────────────────────────────────────────────┐ │ │
│  │   │                    ComputerTool Class                            │ │ │
│  │   │                    (computer_tool.py)                            │ │ │
│  │   │                                                                   │ │ │
│  │   │   async screenshot() → base64 PNG                                │ │ │
│  │   │   async click(x, y, button, clicks) → ToolResult                 │ │ │
│  │   │   async type_text(text) → ToolResult                             │ │ │
│  │   │   async press_key(key) → ToolResult                              │ │ │
│  │   │   async scroll(direction, amount) → ToolResult                   │ │ │
│  │   │   async move_mouse(x, y) → ToolResult                            │ │ │
│  │   └──────────────────────────────────────────────────────────────────┘ │ │
│  │                              │                                         │ │
│  │                              ▼                                         │ │
│  │   ┌──────────────────────────────────────────────────────────────────┐ │ │
│  │   │                    Gradio Web UI                                 │ │ │
│  │   │                      (app.py)                                    │ │ │
│  │   │                                                                   │ │ │
│  │   │   • Screenshot display (1280x800)                                │ │ │
│  │   │   • Click controls (X, Y, button type)                           │ │ │
│  │   │   • Text input field                                             │ │ │
│  │   │   • Key press input (supports ctrl+c, alt+tab, etc.)            │ │ │
│  │   │   • Scroll controls (direction, amount)                          │ │ │
│  │   │   Port 7860                                                      │ │ │
│  │   └──────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                        │ │
│  │                     websockify                                         │ │
│  │                         │                                              │ │
│  │                         ▼                                              │ │
│  │   ┌──────────────────────────────────────────────────────────────────┐ │ │
│  │   │                     noVNC                                        │ │ │
│  │   │               (Port 6080)                                        │ │ │
│  │   │                                                                   │ │ │
│  │   │   Direct browser-based VNC access                                │ │ │
│  │   │   Full desktop interaction                                       │ │ │
│  │   └──────────────────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  EXPOSED PORTS:                                                              │
│    • 7860: Gradio UI (programmatic control)                                 │
│    • 6080: noVNC (direct VNC via browser)                                   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Deep Dive

### 1. Docker Environment (`Dockerfile`)

```dockerfile
FROM ubuntu:22.04

# Desktop environment
RUN apt-get install -y \
    xfce4 \              # Full desktop environment
    xfce4-goodies \      # Extra utilities
    x11vnc \             # VNC server
    xvfb \               # Virtual framebuffer
    xdotool \            # Input simulation
    imagemagick \        # Image manipulation (fallback screenshot)
    scrot \              # Screenshot tool
    novnc \              # Web VNC client
    websockify \         # WebSocket proxy for VNC
    firefox-esr          # Web browser

# Remove screen lockers (would block automation)
RUN apt-get remove -y light-locker xfce4-screensaver xfce4-power-manager

# Non-root user (HuggingFace requirement)
RUN useradd -m -u 1000 user
```

**Key Design Decisions**:
- Uses Xfce4 (lightweight, stable desktop)
- Removes screen lockers that would interfere with automation
- Firefox ESR for web automation tasks
- Non-root user for security (HF Spaces requirement)

### 2. Startup Script (`start.sh`)

```bash
#!/bin/bash

# 1. Start virtual framebuffer
Xvfb :99 -screen 0 1280x800x24 &
sleep 2
export DISPLAY=:99

# 2. Start Xfce desktop
startxfce4 &
sleep 3

# 3. Start VNC server (localhost only)
x11vnc -display :99 -forever -shared -nopw -listen localhost -rfbport 5900 &

# 4. Start WebSocket proxy for noVNC
websockify --web=/usr/share/novnc 6080 localhost:5900 &

# 5. Start Gradio application
python3 app.py
```

**Startup Sequence**:
1. **Xvfb** creates virtual display :99 with 1280x800 resolution, 24-bit color
2. **Xfce4** launches full desktop on virtual display
3. **x11vnc** exposes VNC server on localhost:5900 (no password)
4. **websockify** bridges VNC to WebSocket on port 6080 for browser access
5. **Gradio** serves the control interface on port 7860

### 3. Computer Tool Implementation (`computer_tool.py`)

```python
class ComputerTool:
    def __init__(
        self,
        display_width: int = 1280,
        display_height: int = 800,
        display_num: int = 99
    ):
        self.display_width = display_width
        self.display_height = display_height
        self.display_num = display_num
        self._display_prefix = f"DISPLAY=:{self.display_num} "
        self._screenshot_delay = 0.5
        self._typing_delay_ms = 12
```

#### Screenshot Capture
```python
async def screenshot(self) -> ToolResult:
    screenshot_path = Path(f"/tmp/screenshot_{os.getpid()}.png")

    # Primary: scrot (faster)
    if shutil.which("scrot"):
        cmd = f"{self._display_prefix}scrot -o {screenshot_path}"
    # Fallback: ImageMagick import
    else:
        cmd = f"{self._display_prefix}import -window root {screenshot_path}"

    await self._run_shell(cmd)

    # Return as base64
    with open(screenshot_path, "rb") as f:
        base64_image = base64.standard_b64encode(f.read()).decode()

    screenshot_path.unlink()  # Cleanup
    return ToolResult(base64_image=base64_image)
```

#### Mouse Click
```python
async def click(self, x: int, y: int, button: str = "left", clicks: int = 1) -> ToolResult:
    button_map = {"left": 1, "middle": 2, "right": 3}
    btn = button_map.get(button, 1)

    # Move mouse to position
    await self._run_shell(f"{self._display_prefix}xdotool mousemove --sync {x} {y}")

    # Perform click(s)
    await self._run_shell(
        f"{self._display_prefix}xdotool click --repeat {clicks} --delay 100 {btn}"
    )

    await asyncio.sleep(self._screenshot_delay)
    return ToolResult(output=f"Clicked {button} at ({x}, {y})")
```

#### Text Input
```python
async def type_text(self, text: str) -> ToolResult:
    # --delay: milliseconds between keystrokes (prevents dropped keys)
    cmd = f"{self._display_prefix}xdotool type --delay {self._typing_delay_ms} -- {shlex.quote(text)}"
    await self._run_shell(cmd)
    await asyncio.sleep(self._screenshot_delay)
    return ToolResult(output=f"Typed: {text[:50]}...")
```

#### Key Press (with modifier support)
```python
async def press_key(self, key: str) -> ToolResult:
    # Map common key names to X11 keysyms
    key_map = {
        "enter": "Return", "return": "Return",
        "tab": "Tab", "escape": "Escape", "esc": "Escape",
        "backspace": "BackSpace", "space": "space",
        "up": "Up", "down": "Down", "left": "Left", "right": "Right",
    }

    # Handle modifier combinations (ctrl+c, alt+tab, etc.)
    keys = key.lower().split("+")
    mapped = [key_map.get(k.strip(), k.strip()) for k in keys]
    key_combo = "+".join(mapped)

    await self._run_shell(
        f"{self._display_prefix}xdotool key -- {shlex.quote(key_combo)}"
    )
    return ToolResult(output=f"Pressed: {key}")
```

#### Scroll
```python
async def scroll(self, direction: str = "down", amount: int = 3) -> ToolResult:
    # X11 button mapping for scroll
    button_map = {
        "up": 4,     # Scroll wheel up
        "down": 5,   # Scroll wheel down
        "left": 6,   # Horizontal scroll left
        "right": 7   # Horizontal scroll right
    }
    button = button_map.get(direction, 5)

    await self._run_shell(
        f"{self._display_prefix}xdotool click --repeat {amount} --delay 50 {button}"
    )
    return ToolResult(output=f"Scrolled {direction}")
```

### 4. Data Structures

```python
class Action(str, Enum):
    SCREENSHOT = "screenshot"
    KEY = "key"
    TYPE = "type"
    MOUSE_MOVE = "mouse_move"
    LEFT_CLICK = "left_click"
    RIGHT_CLICK = "right_click"
    DOUBLE_CLICK = "double_click"
    SCROLL = "scroll"
    WAIT = "wait"

@dataclass
class ToolResult:
    output: Optional[str] = None       # Success message
    error: Optional[str] = None        # Error message
    base64_image: Optional[str] = None # Screenshot data
```

---

## Command Reference

### xdotool Commands Used

| Action | Command | Notes |
|--------|---------|-------|
| Move mouse | `xdotool mousemove --sync X Y` | `--sync` waits for completion |
| Click | `xdotool click --repeat N --delay MS BUTTON` | BUTTON: 1=left, 2=middle, 3=right |
| Type text | `xdotool type --delay MS "TEXT"` | Delay prevents dropped keys |
| Press key | `xdotool key KEYSYM` | Supports combos like `ctrl+c` |
| Scroll | `xdotool click BUTTON` | 4=up, 5=down, 6=left, 7=right |

### X11 Key Symbols

Common mappings for key press:
```
Return, Tab, Escape, BackSpace, space
Up, Down, Left, Right
F1-F12
ctrl, alt, shift, super (Windows key)
```

---

## Integration with AI Agents

### Current State

The Gradio UI provides manual control, but the `ComputerTool` class is designed for AI integration:

```python
# AI agent usage pattern
computer = ComputerTool(display_width=1280, display_height=800)

# Get current screen state
screenshot = await computer.screenshot()
# -> Send screenshot.base64_image to vision model

# AI decides: "Click on Firefox icon at (50, 400)"
await computer.click(50, 400, "left")

# AI decides: "Type URL"
await computer.type_text("https://google.com")

# AI decides: "Press Enter"
await computer.press_key("enter")
```

### MCP Tool Integration

Could expose as MCP tools:

```python
# Tool: computer_screenshot
# Returns: base64 image for vision analysis

# Tool: computer_click
# Params: x, y, button (left/right/double)

# Tool: computer_type
# Params: text

# Tool: computer_key
# Params: key (supports modifiers like ctrl+c)

# Tool: computer_scroll
# Params: direction (up/down/left/right), amount
```

---

## FreeCAD MCP Integration Opportunities

### 1. GUI Fallback Mode

When the XML-RPC API can't accomplish a task, fall back to GUI automation:

```python
# Scenario: User wants to use Render workbench (no API)

# 1. Get FreeCAD window screenshot
screenshot = await computer.screenshot()

# 2. VLM identifies: "Render menu at (150, 30)"
menu_location = await vlm.find_element(screenshot, "Render menu")

# 3. Click to open menu
await computer.click(menu_location.x, menu_location.y)

# 4. Screenshot again, find "Render Image" option
screenshot = await computer.screenshot()
option_location = await vlm.find_element(screenshot, "Render Image")

# 5. Click option
await computer.click(option_location.x, option_location.y)
```

### 2. Visual Verification Loop

```
┌─────────────────────────────────────────────────────────────────┐
│                    MCP Server with GUI Fallback                  │
│                                                                  │
│   User: "Create a box and render it"                            │
│         │                                                        │
│         ▼                                                        │
│   ┌─────────────────┐                                           │
│   │  Try XML-RPC    │  create_primitive("box", ...)            │
│   │  (headless)     │  ✓ Success                                │
│   └────────┬────────┘                                           │
│            │                                                     │
│            ▼                                                     │
│   ┌─────────────────┐                                           │
│   │  Try XML-RPC    │  render_scene()                          │
│   │  (headless)     │  ✗ Render workbench not available        │
│   └────────┬────────┘                                           │
│            │                                                     │
│            ▼                                                     │
│   ┌─────────────────┐                                           │
│   │  Fall back to   │  Use ComputerTool                        │
│   │  GUI automation │                                           │
│   └────────┬────────┘                                           │
│            │                                                     │
│            ▼                                                     │
│   screenshot() → VLM → click(menu) → screenshot() → ...        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3. Hybrid Docker Architecture

```yaml
# docker-compose.yml addition
services:
  freecad-gui:
    build:
      context: ./docker/freecad-gui
      dockerfile: Dockerfile.gui
    environment:
      - DISPLAY=:99
    volumes:
      - /tmp/.X11-unix:/tmp/.X11-unix
    ports:
      - "6080:6080"   # noVNC
      - "7861:7860"   # ComputerTool Gradio
    depends_on:
      - freecad  # Headless container
```

### 4. FreeCAD-Specific Automation Script

```python
class FreeCADGUITool(ComputerTool):
    """Extended ComputerTool with FreeCAD-specific helpers."""

    async def open_workbench(self, workbench_name: str):
        """Open a FreeCAD workbench via GUI."""
        # Click View menu
        await self.click(100, 30)
        await asyncio.sleep(0.3)

        # Click Workbenches submenu
        await self.click(100, 150)
        await asyncio.sleep(0.3)

        # Find and click workbench (would need VLM)
        # ...

    async def run_macro(self, macro_name: str):
        """Run a FreeCAD macro via GUI."""
        # Press Ctrl+Shift+M for macro dialog
        await self.press_key("ctrl+shift+m")
        await asyncio.sleep(0.5)

        # Type macro name
        await self.type_text(macro_name)

        # Press Enter to run
        await self.press_key("enter")

    async def export_via_gui(self, format: str, path: str):
        """Export using File menu (for formats not in API)."""
        # File menu
        await self.press_key("alt+f")
        await asyncio.sleep(0.3)

        # Export
        await self.press_key("e")
        await asyncio.sleep(0.5)

        # Type path
        await self.type_text(path)

        # Save
        await self.press_key("enter")
```

---

## Performance Characteristics

| Operation | Typical Latency | Notes |
|-----------|-----------------|-------|
| Screenshot | 50-100ms | scrot faster than ImageMagick |
| Mouse move | 10-20ms | `--sync` adds small overhead |
| Click | 20-50ms | Including delay between double-clicks |
| Type text | 12ms/char | Configurable via `_typing_delay_ms` |
| Key press | 10-20ms | Single key or combo |

**Screenshot delay**: 500ms after actions (configurable) to let UI update

---

## Security Considerations

1. **No VNC password**: x11vnc runs with `-nopw` flag
2. **Localhost binding**: VNC only listens on localhost (websockify proxies)
3. **Non-root user**: Runs as UID 1000 user
4. **No persistent state**: Container is ephemeral
5. **Internet access**: Firefox can access internet (potential data exfil)

**For FreeCAD MCP integration**, consider:
- Disabling internet access in container
- Using tighter X11 permissions
- Adding authentication to websockify

---

## Limitations

1. **Single display**: Only one virtual display (:99)
2. **Fixed resolution**: 1280x800 hardcoded (should be configurable)
3. **No audio**: No PulseAudio/ALSA setup
4. **No clipboard**: xclip not installed for clipboard operations
5. **Synchronous screenshots**: Could queue multiple actions before screenshot
6. **No GPU**: Software rendering only (slow for 3D)

---

## Recommended Enhancements for FreeCAD

### 1. Add Clipboard Support
```bash
apt-get install -y xclip xsel
```
```python
async def copy_to_clipboard(self, text: str):
    cmd = f"echo -n {shlex.quote(text)} | {self._display_prefix}xclip -selection clipboard"
    await self._run_shell(cmd)

async def paste_from_clipboard(self) -> str:
    stdout, _ = await self._run_shell(f"{self._display_prefix}xclip -selection clipboard -o")
    return stdout.strip()
```

### 2. Add GPU Support (for FreeCAD 3D)
```dockerfile
FROM nvidia/cuda:12.6.0-base-ubuntu22.04

# Install VirtualGL for GPU-accelerated rendering
RUN apt-get install -y virtualgl

# Run Xvfb with VirtualGL
CMD vglrun startxfce4
```

### 3. Add Window Management
```python
async def find_window(self, name: str) -> int:
    """Find window ID by name."""
    stdout, _ = await self._run_shell(
        f"{self._display_prefix}xdotool search --name {shlex.quote(name)}"
    )
    return int(stdout.strip().split()[0])

async def focus_window(self, window_id: int):
    """Focus a specific window."""
    await self._run_shell(
        f"{self._display_prefix}xdotool windowactivate {window_id}"
    )

async def get_window_geometry(self, window_id: int) -> dict:
    """Get window position and size."""
    stdout, _ = await self._run_shell(
        f"{self._display_prefix}xdotool getwindowgeometry {window_id}"
    )
    # Parse output...
```

### 4. Vision-Guided Clicking
```python
async def click_element(self, description: str):
    """Use VLM to find and click an element."""
    screenshot = await self.screenshot()

    # Send to VLM
    location = await self.vlm.find_element(
        screenshot.base64_image,
        f"Find the {description} and return its coordinates"
    )

    if location:
        await self.click(location.x, location.y)
        return ToolResult(output=f"Clicked {description} at ({location.x}, {location.y})")
    else:
        return ToolResult(error=f"Could not find {description}")
```

---

## Conclusion

Open Computer Use Agent provides a solid foundation for AI-controlled desktop automation. For FreeCAD MCP integration, it offers:

1. **GUI fallback** when API operations aren't available
2. **Visual verification** of API-created models
3. **Access to all workbenches** including those without Python API
4. **Full FreeCAD functionality** via keyboard shortcuts and menus

The xdotool-based approach is proven and reliable, though it requires careful timing and potentially VLM assistance for dynamic UI elements.
