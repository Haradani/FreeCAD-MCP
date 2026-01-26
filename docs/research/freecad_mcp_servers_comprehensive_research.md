# FreeCAD MCP Servers on GitHub: Comprehensive Research Report

## Executive Summary

FreeCAD Model Context Protocol (MCP) servers represent a transformative convergence of parametric 3D CAD design and artificial intelligence, enabling natural language control of FreeCAD through standardized AI integration. This research identifies six major GitHub implementations, analyzes their technical architectures, evaluates adoption patterns, and contextualizes the findings within the rapidly expanding MCP ecosystem—which achieved $95.2 billion market valuation and 134% year-over-year growth in Q1 2025.

The FreeCAD MCP landscape demonstrates characteristic early-stage innovation: multiple competing implementations with divergent architectural approaches, ranging from minimal 2-tool servers to comprehensive 82+ tool frameworks. The leading implementation by neka-nat has achieved 259 GitHub stars through simplicity and Claude Desktop integration, while emerging solutions like jango-blockchained's multi-provider architecture position for enterprise adoption through advanced features including Docker deployment, performance monitoring, and support for Claude 4, GPT-4o, and Gemini 2.5 models.

### Key Findings

- **Six active implementations** identified, with collective community engagement exceeding 350 GitHub stars
- **Technical fragmentation** across XML-RPC, JSON-RPC, socket, and embedded connection methods
- **AI provider diversity** expanding from Claude-only to multi-model support (Anthropic, OpenAI, Google, OpenRouter)
- **Security concerns** inherent to execute_code capabilities requiring human-in-the-loop approval mechanisms
- **Ecosystem momentum** driven by 28% Fortune 500 adoption and 33% monthly growth rates

---

## Table of Contents

1. [Background: The Model Context Protocol Revolution](#background-the-model-context-protocol-revolution)
2. [FreeCAD MCP Server Implementations: Detailed Analysis](#freecad-mcp-server-implementations-detailed-analysis)
   - [neka-nat/freecad-mcp: Market Leader Through Simplicity](#1-neka-natfreecad-mcp-market-leader-through-simplicity)
   - [bonninr/freecad_mcp: Minimalist Architecture](#2-bonninrfreecad_mcp-minimalist-architecture)
   - [jango-blockchained/mcp-freecad: Enterprise-Grade Multi-Provider Platform](#3-jango-blockchainedmcp-freecad-enterprise-grade-multi-provider-platform)
   - [spkane/freecad-robust-mcp-and-more: Production-Hardened Infrastructure](#4-spkanefreecad-robust-mcp-and-more-production-hardened-infrastructure)
   - [Additional Implementations](#5-additional-implementations-emerging-solutions)
3. [Technical Architecture Deep Dive](#technical-architecture-deep-dive)
4. [Use Cases and Applications](#use-cases-and-applications)
5. [Limitations and Challenges](#limitations-and-challenges)
6. [Future Directions and Recommendations](#future-directions-and-recommendations)
7. [Conclusion](#conclusion)

---

## Background: The Model Context Protocol Revolution

### Protocol Genesis and Adoption

The Model Context Protocol, introduced by Anthropic in November 2024, addresses the fundamental "N×M integration problem" that plagued pre-MCP AI systems. Prior to MCP, connecting N AI applications to M data sources required N×M custom integrations—an approach OpenAI attempted to solve through function-calling APIs and ChatGPT plugins, but which lacked vendor-agnostic standardization.

MCP achieves standardization through JSON-RPC 2.0 transport and architectural patterns borrowed from the Language Server Protocol (LSP), which revolutionized code editor integration in software development. The protocol's first year has exceeded expectations:

- **OpenAI** officially adopted MCP across ChatGPT products in March 2025
- **Google** integrated it into Gemini models and CLI tools
- **AWS** deployed it across agentic AI services
- **December 2025**: Anthropic donated MCP governance to the Agentic AI Foundation under the Linux Foundation

The protocol's rapid maturation is evidenced by sophisticated governance mechanisms (Working and Interest Groups established via SEP-1302), security enhancements (SEP-1024 client requirements, SEP-835 default scopes), and architectural innovations including the extensions framework for scenario-specific additions without core specification changes.

### Market Context and Industry Traction

The AI server market explosion provides critical context for FreeCAD MCP development:

| Metric | Value | Context |
|--------|-------|---------|
| Q1 2025 Market Size | $95.2 billion | 134% YoY expansion |
| Fortune 500 MCP Adoption | 28% | Up from 12% in 2024 |
| Fintech Sector Adoption | 45% | Leading vertical |
| Healthcare Sector Adoption | 32% | Strong growth |
| E-commerce Sector Adoption | 27% | Steady adoption |
| Average Dev Time Savings | 40% | Reported by enterprises |
| Monthly Growth Rate | 33% | Post-initial 6x surge |

Monthly growth metrics from PulseMCP show sustained 33% expansion after initial 6x adoption surge, indicating network effects are taking hold: more AI clients supporting MCP incentivizes server development, which in turn makes clients more valuable, completing the virtuous cycle.

Infrastructure maturation is evident through emergence of specialized vendors:
- **Stainless**: SDK generation
- **Cloudflare**: Secure hosting
- **Smithery**: Deployment automation
- **Mintlify's mcpt, OpenTools, Glama**: Discovery and distribution marketplaces

---

## FreeCAD MCP Server Implementations: Detailed Analysis

### 1. neka-nat/freecad-mcp: Market Leader Through Simplicity

| Attribute | Value |
|-----------|-------|
| **Repository** | github.com/neka-nat/freecad-mcp |
| **GitHub Stars** | 259 |
| **Forks** | 41 |
| **Contributors** | 3 (neka-nat, lwsinclair, zamalali) |
| **License** | MIT |
| **Architecture** | XML-RPC server implemented as FreeCAD addon workbench |

#### Technical Implementation

The neka-nat implementation achieves market leadership through architectural simplicity and seamless Claude Desktop integration. The system operates as a Remote Procedure Call (RPC) server running inside FreeCAD on `localhost:9875`, exposing modeling functions via Model Context Protocol.

The addon integrates directly into FreeCAD's workbench system, appearing in the standard workbench selector after installation. Users start the RPC server through a dedicated toolbar button in the "FreeCAD MCP" workbench, establishing the communication bridge between FreeCAD and external MCP clients.

#### Tool Inventory (10 Tools)

| Tool | Function | Parameters |
|------|----------|------------|
| `create_document` | Initialize new FreeCAD documents | Document name |
| `create_object` | Generate geometric primitives | Document name, object type, properties |
| `edit_object` | Modify existing object properties | Document name, object name, property dictionary |
| `delete_object` | Remove objects from documents | Document name, object name |
| `execute_code` | Run arbitrary Python in FreeCAD context | Python code string |
| `insert_part_from_library` | Import from FreeCAD parts library | Document name, part path |
| `get_view` | Capture screenshot of active viewport | None |
| `get_objects` | List all objects in document | Document name |
| `get_object` | Retrieve specific object details | Document name, object name |
| `get_parts_list` | Enumerate available library parts | None |

**Supported Object Types:**
- `Part::Box`, `Part::Cylinder`, `Part::Sphere`, `Part::Cone`, `Part::Torus`
- `Draft::Rectangle`, `Draft::Circle`, `Draft::Line`, `Draft::Wire`, `Draft::BSpline`
- `PartDesign::Body`, `PartDesign::Pad`, `PartDesign::Pocket`
- `Fem::FemMeshGmsh`, `Fem::ConstraintFixed`

#### Installation and Configuration

**Stage 1: Addon Installation**

```bash
# Clone the repository
git clone https://github.com/neka-nat/freecad-mcp.git
cd freecad-mcp

# Copy addon to FreeCAD Mod directory (platform-specific)
# Linux (Ubuntu/Debian):
cp -r addon/FreeCADMCP ~/.FreeCAD/Mod/

# Linux (Snap):
cp -r addon/FreeCADMCP ~/snap/freecad/common/Mod/

# macOS:
cp -r addon/FreeCADMCP ~/Library/Application\ Support/FreeCAD/Mod/

# Windows (PowerShell):
Copy-Item -Recurse addon/FreeCADMCP $env:APPDATA\FreeCAD\Mod\
```

**Platform-Specific Addon Directories:**

| Platform | Path |
|----------|------|
| macOS | `~/Library/Application Support/FreeCAD/Mod/` |
| Windows | `%APPDATA%\FreeCAD\Mod\` |
| Linux (Ubuntu) | `~/.FreeCAD/Mod/` or `~/snap/freecad/common/Mod/` |
| Linux (Debian) | `~/.local/share/FreeCAD/Mod` |

**Stage 2: Dependency Management**

The implementation requires `uvx` (UV package manager) for Python dependency resolution:

```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify installation
uvx --version
```

**Stage 3: Claude Desktop Configuration**

Edit `claude_desktop_config.json` at platform-specific locations:

| Platform | Config Path |
|----------|-------------|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

**Standard Configuration:**

```json
{
  "mcpServers": {
    "freecad": {
      "command": "uvx",
      "args": ["freecad-mcp"]
    }
  }
}
```

**Token-Optimized Configuration (No Screenshots):**

```json
{
  "mcpServers": {
    "freecad": {
      "command": "uvx",
      "args": ["freecad-mcp", "--only-text-feedback"]
    }
  }
}
```

#### Code Examples

**Example 1: Creating a Simple Box**

```python
# AI-generated code executed via execute_code tool
import FreeCAD
import Part

# Create a new document
doc = FreeCAD.newDocument("MyDesign")

# Create a box primitive
box = doc.addObject("Part::Box", "MainBox")
box.Length = 100  # mm
box.Width = 50    # mm
box.Height = 30   # mm

# Position the box
box.Placement.Base = FreeCAD.Vector(0, 0, 0)

# Recompute to update the model
doc.recompute()
```

**Example 2: Creating a Flange with Bolt Holes**

```python
import FreeCAD
import Part
import math

doc = FreeCAD.newDocument("Flange")

# Create main flange body
flange = doc.addObject("Part::Cylinder", "FlangeBody")
flange.Radius = 75  # mm
flange.Height = 15  # mm

# Create center bore
bore = doc.addObject("Part::Cylinder", "CenterBore")
bore.Radius = 25  # mm
bore.Height = 20  # mm
bore.Placement.Base = FreeCAD.Vector(0, 0, -2.5)

# Boolean cut for center hole
flange_with_bore = doc.addObject("Part::Cut", "FlangeWithBore")
flange_with_bore.Base = flange
flange_with_bore.Tool = bore

# Create bolt holes (8 holes on 60mm PCD)
bolt_holes = []
pcd_radius = 55  # Pitch Circle Diameter / 2
num_holes = 8
hole_radius = 5.5  # For M10 bolts

for i in range(num_holes):
    angle = (2 * math.pi * i) / num_holes
    x = pcd_radius * math.cos(angle)
    y = pcd_radius * math.sin(angle)

    hole = doc.addObject("Part::Cylinder", f"BoltHole_{i}")
    hole.Radius = hole_radius
    hole.Height = 20
    hole.Placement.Base = FreeCAD.Vector(x, y, -2.5)
    bolt_holes.append(hole)

# Fuse all bolt holes
bolt_hole_union = bolt_holes[0]
for hole in bolt_holes[1:]:
    fusion = doc.addObject("Part::Fuse", "TempFusion")
    fusion.Base = bolt_hole_union
    fusion.Tool = hole
    doc.recompute()
    bolt_hole_union = fusion

# Final cut for bolt holes
final_flange = doc.addObject("Part::Cut", "FinalFlange")
final_flange.Base = flange_with_bore
final_flange.Tool = bolt_hole_union

doc.recompute()

# Hide intermediate objects
for obj in doc.Objects:
    if obj.Name != "FinalFlange":
        obj.ViewObject.Visibility = False
```

**Example 3: Parametric Mounting Bracket**

```python
import FreeCAD
import Part

doc = FreeCAD.newDocument("MountingBracket")

# Parameters (easily modifiable)
params = {
    "base_length": 80,
    "base_width": 40,
    "base_thickness": 5,
    "wall_height": 50,
    "wall_thickness": 5,
    "hole_diameter": 6.5,  # M6 clearance
    "fillet_radius": 3,
    "mounting_holes": [
        {"x": 15, "y": 20},
        {"x": 65, "y": 20},
    ],
    "wall_holes": [
        {"x": 20, "z": 25},
        {"x": 60, "z": 25},
    ]
}

# Create base plate
base = Part.makeBox(
    params["base_length"],
    params["base_width"],
    params["base_thickness"]
)

# Create vertical wall
wall = Part.makeBox(
    params["base_length"],
    params["wall_thickness"],
    params["wall_height"]
)
wall.translate(FreeCAD.Vector(0, 0, params["base_thickness"]))

# Fuse base and wall
bracket = base.fuse(wall)

# Add fillets at the junction
edges_to_fillet = []
for edge in bracket.Edges:
    # Find edges at the base-wall junction
    if abs(edge.CenterOfMass.z - params["base_thickness"]) < 0.1:
        edges_to_fillet.append(edge)

if edges_to_fillet:
    bracket = bracket.makeFillet(params["fillet_radius"], edges_to_fillet)

# Create mounting holes in base
for hole_pos in params["mounting_holes"]:
    hole = Part.makeCylinder(
        params["hole_diameter"] / 2,
        params["base_thickness"] * 2,
        FreeCAD.Vector(hole_pos["x"], hole_pos["y"], -1)
    )
    bracket = bracket.cut(hole)

# Create mounting holes in wall
for hole_pos in params["wall_holes"]:
    hole = Part.makeCylinder(
        params["hole_diameter"] / 2,
        params["wall_thickness"] * 2,
        FreeCAD.Vector(hole_pos["x"], -1, params["base_thickness"] + hole_pos["z"]),
        FreeCAD.Vector(0, 1, 0)  # Direction vector
    )
    bracket = bracket.cut(hole)

# Add to document
bracket_obj = doc.addObject("Part::Feature", "MountingBracket")
bracket_obj.Shape = bracket

doc.recompute()
```

#### Use Case Demonstrations

The neka-nat repository showcases three compelling demonstrations:

1. **Flange Design:** User requests a standard pipe flange through conversational prompts. Claude interprets dimensional specifications, generates appropriate FreeCAD Python code, and iterates on bolt hole patterns and sealing surfaces based on visual feedback.

2. **Toy Car Creation:** Complex multi-component assembly from high-level description. The AI decomposes "toy car" into chassis, wheels, axles, and decorative elements, creating each component with appropriate geometric primitives and spatial relationships.

3. **2D Drawing Translation:** User provides 2D engineering drawing image. Claude analyzes the drawing, extracts dimensions and geometric relationships, and generates corresponding 3D parametric model.

---

### 2. bonninr/freecad_mcp: Minimalist Architecture

| Attribute | Value |
|-----------|-------|
| **Repository** | github.com/bonninr/freecad_mcp |
| **GitHub Stars** | 87 |
| **Forks** | 19 |
| **Contributors** | 1 (single maintainer) |
| **License** | MIT |
| **Architecture** | Socket-based JSON-RPC server-client system |

#### Architectural Philosophy

The bonninr implementation adopts radically minimalist design, exposing just two tools: `get_scene_info` and `run_script`. This approach prioritizes flexibility over predefined functionality—rather than offering specialized tools for each CAD operation, the system provides comprehensive scene introspection and unrestricted Python execution, enabling AI assistants to implement arbitrary workflows through code generation.

The JSON-RPC over TCP socket architecture (port 9876) offers performance advantages over HTTP-based approaches:
- Socket communication reduces protocol overhead
- Persistent connections eliminate handshake latency
- Positions FreeCAD as a stateful service rather than request-response endpoint

#### Tool Specification

**`get_scene_info` Tool**

Returns comprehensive document state including:

| Category | Data Returned |
|----------|---------------|
| Document properties | Name, label, filename, object count, save status |
| Object catalog | Complete list with types, labels, and identifiers |
| Geometric details | Position vectors, rotation matrices, bounding boxes |
| Shape properties | Volume, surface area, center of mass (for solid objects) |
| Sketch information | Geometry elements (lines, arcs, circles), constraint definitions |
| View configuration | Camera position, direction, focal distance, viewport dimensions |

**Example Response Structure:**

```json
{
  "document": {
    "name": "MyDesign",
    "label": "My Design Project",
    "filename": "/home/user/designs/mydesign.FCStd",
    "objectCount": 15,
    "modified": true
  },
  "objects": [
    {
      "name": "Box",
      "label": "Main Housing",
      "type": "Part::Box",
      "position": [0, 0, 0],
      "rotation": [0, 0, 0, 1],
      "boundingBox": {
        "min": [0, 0, 0],
        "max": [100, 50, 30]
      },
      "properties": {
        "Length": 100,
        "Width": 50,
        "Height": 30
      },
      "shape": {
        "volume": 150000,
        "surfaceArea": 22000,
        "centerOfMass": [50, 25, 15]
      }
    }
  ],
  "view": {
    "cameraPosition": [200, -200, 150],
    "cameraDirection": [-0.577, 0.577, -0.577],
    "focalDistance": 346.4,
    "viewportSize": [1920, 1080]
  }
}
```

**`run_script` Tool**

Executes arbitrary Python code within the FreeCAD environment with full API access:

```python
# Example: Complex parametric operation via run_script
import FreeCAD
import Part

doc = FreeCAD.ActiveDocument

# Create helical spring
helix = Part.makeHelix(
    pitch=10,      # 10mm pitch
    height=50,     # 50mm total height
    radius=15,     # 15mm radius
    angle=0        # Right-handed
)

# Create wire profile for sweep
circle = Part.makeCircle(2)  # 2mm wire diameter
wire = Part.Wire([circle])

# Sweep profile along helix
spring = Part.Wire(helix).makePipeShell([wire], True, True)

# Add to document
spring_obj = doc.addObject("Part::Feature", "Spring")
spring_obj.Shape = spring
doc.recompute()

print(f"Spring created with {spring.Faces.__len__()} faces")
```

#### Cross-Platform Configuration

**Windows Configuration:**

```json
{
  "mcpServers": {
    "freecad": {
      "command": "C:\\ProgramData\\anaconda3\\python.exe",
      "args": [
        "C:\\Users\\USER\\AppData\\Roaming\\FreeCAD\\Mod\\freecad_mcp\\src\\freecad_bridge.py"
      ]
    }
  }
}
```

**Linux Configuration:**

```json
{
  "mcpServers": {
    "freecad": {
      "command": "/usr/bin/python3",
      "args": [
        "/home/USER/.FreeCAD/Mod/freecad_mcp/src/freecad_bridge.py"
      ]
    }
  }
}
```

**macOS Configuration:**

```json
{
  "mcpServers": {
    "freecad": {
      "command": "/usr/local/bin/python3",
      "args": [
        "/Users/USER/Library/Application Support/FreeCAD/Mod/freecad_mcp/src/freecad_bridge.py"
      ]
    }
  }
}
```

---

### 3. jango-blockchained/mcp-freecad: Enterprise-Grade Multi-Provider Platform

| Attribute | Value |
|-----------|-------|
| **Repository** | github.com/jango-blockchained/mcp-freecad |
| **GitHub Stars** | 12 |
| **Forks** | 1 |
| **Contributors** | 2 (jango-blockchained, Cursor Agent) |
| **License** | MIT |
| **Status** | Active development |
| **Architecture** | Modular tool provider system with six connection methods |

#### Architectural Sophistication

The jango-blockchained implementation represents the most architecturally sophisticated FreeCAD MCP server, featuring:
- **82+ tools** organized into modular providers
- **4 major AI platforms** with 13+ models
- **6 distinct connection methods**
- **Docker containerization**
- **Performance monitoring**
- **Connection recovery mechanisms**

**Core Infrastructure Components:**

| Component | File | Purpose |
|-----------|------|---------|
| Connection Manager | `freecad_connection_manager.py` | Multi-method connection handling with automatic fallback |
| MCP Server | `freecad_mcp_server.py` | MCP protocol implementation and request routing |
| HTTP Server | `server.py` | FastAPI-based HTTP server for remote deployments |
| Cache | `cache.py` | Resource caching to minimize FreeCAD API calls |
| Diagnostics | `diagnostics.py` | Real-time performance monitoring and health checks |
| Recovery | `recovery.py` | Automatic connection recovery and retry logic |

**Tool Providers (Modular Architecture):**

| Provider | File | Capabilities |
|----------|------|--------------|
| Primitives | `primitives.py` | Box, cylinder, sphere, cone, torus creation |
| Model Manipulation | `model_manipulation.py` | Transforms, booleans, fillets, chamfers, mirror, scale |
| Export/Import | `export_import.py` | STL, STEP, IGES, OBJ, SAT file handling |
| Measurement | `measurement.py` | Volume, surface area, center of mass, bounding box |
| Code Generator | `code_generator.py` | Python script generation from natural language |

#### Multi-Provider AI Integration

**Anthropic Claude 4 Series:**

| Model | Context | Pricing (in/out per 1M) | Features |
|-------|---------|------------------------|----------|
| `claude-opus-4` | 200K | $15 / $75 | Most advanced reasoning, extended thinking |
| `claude-sonnet-4` | 200K | $3 / $15 | Balanced performance, superior coding |
| `claude-haiku-3.5` | 200K | $0.25 / $1.25 | Fast lightweight operations |

**OpenAI Models:**

| Model | Context | Pricing (per 1M) | Features |
|-------|---------|-----------------|----------|
| `gpt-4o` | 128K | ~$5 | Default multimodal (text/image/audio) |
| `gpt-4.1` | 1M | ~$2.5 | Extended context, multimodal video |
| `gpt-4-turbo` | 128K | ~$10 | Cost-effective high-volume |
| `o3` | 128K | ~$10 | Advanced reasoning for complex geometry |
| `o4-mini` | 128K | ~$0.15 | Budget-conscious reasoning |

**Google Gemini 2.5 Series:**

| Model | Context | Features |
|-------|---------|----------|
| `gemini-2.5-pro-preview-05-06` | 1M | Enhanced reasoning, thinking mode |
| `gemini-2.5-flash-preview-04-17` | 1M | Performance-optimized, adaptive thinking |
| `gemini-2.0-flash-001` | 1M | Production-ready, 2× faster than 1.5 Pro |
| `gemini-2.0-flash-lite` | 1M | Cost-optimized for high-volume |

**OpenRouter Unified Access:**

| Model | Features |
|-------|----------|
| `anthropic/claude-sonnet-4` | Single API access to Anthropic |
| `openai/gpt-4o` | Single API access to OpenAI |
| `google/gemini-2.5-pro-preview` | Single API access to Google |
| `deepseek/deepseek-r1` | Free tier, advanced reasoning |
| `deepseek/deepseek-v3` | Free tier, general purpose |

**Model Selection Guide:**

| Use Case | Recommended Model | Alternative |
|----------|------------------|-------------|
| General CAD work | `claude-sonnet-4` | `gpt-4o`, `gemini-2.0-flash-001` |
| Complex reasoning | `claude-opus-4` | `o3`, `gemini-2.5-pro-preview` |
| Multimodal tasks | `gpt-4o` | `gpt-4.1`, `claude-opus-4` |
| Cost-effective | `o4-mini` | `claude-haiku-3.5`, `gemini-2.0-flash-lite` |
| High volume | `gpt-4-turbo` | `claude-sonnet-4`, `gemini-2.0-flash-001` |
| Free usage | `deepseek/deepseek-r1` | `google/gemini-2.5-flash-preview` |

**Multi-Provider Configuration Example:**

```json
{
  "providers": {
    "anthropic": {
      "enabled": true,
      "api_key": "${ANTHROPIC_API_KEY}",
      "model": "claude-sonnet-4",
      "thinking_mode": true,
      "max_tokens": 64000
    },
    "openai": {
      "enabled": true,
      "api_key": "${OPENAI_API_KEY}",
      "model": "gpt-4o",
      "max_tokens": 32000
    },
    "google": {
      "enabled": true,
      "api_key": "${GOOGLE_API_KEY}",
      "model": "gemini-2.0-flash-001",
      "thinking_mode": true
    },
    "openrouter": {
      "enabled": true,
      "api_key": "${OPENROUTER_API_KEY}",
      "model": "anthropic/claude-sonnet-4",
      "free_models": ["deepseek/deepseek-r1", "deepseek/deepseek-v3"]
    }
  }
}
```

#### Six Connection Methods

| Method | Protocol | Best For | Configuration |
|--------|----------|----------|---------------|
| **Launcher** | AppImage/AppRun | Linux users, simplest setup | `"connection_method": "launcher"` |
| **Server** | TCP Socket | Low-latency operations | `"connection_method": "server", "port": 12345` |
| **Bridge** | CLI | Maximum isolation | `"connection_method": "bridge"` |
| **RPC** | XML-RPC | Network-transparent | `"connection_method": "rpc", "port": 9875` |
| **Wrapper** | Subprocess | Full process control | `"connection_method": "wrapper"` |
| **Mock** | None | Testing only | `"connection_method": "mock"` |

**Launcher Mode Configuration:**

```json
{
  "connection_method": "launcher",
  "use_apprun": true,
  "apprun_path": "/path/to/squashfs-root/AppRun",
  "freecad_args": ["--console", "--log-file", "/tmp/freecad.log"]
}
```

**Server Mode Configuration:**

```json
{
  "connection_method": "server",
  "host": "localhost",
  "port": 12345,
  "timeout": 30,
  "retry_attempts": 3,
  "retry_delay": 1.0
}
```

**RPC Mode Configuration (Compatible with neka-nat addon):**

```json
{
  "connection_method": "rpc",
  "host": "localhost",
  "port": 9875,
  "protocol": "xmlrpc"
}
```

#### Docker Deployment

**docker-compose.yml:**

```yaml
version: '3.8'

services:
  freecad-mcp:
    build:
      context: .
      dockerfile: Dockerfile
    image: freecad-mcp:latest
    container_name: freecad-mcp-server
    ports:
      - "12345:12345"
      - "8080:8080"  # Optional HTTP API
    volumes:
      - ./models:/app/models:rw
      - ./exports:/app/exports:rw
      - ./config:/app/config:ro
    environment:
      - FREECAD_MODE=server
      - FREECAD_HOST=0.0.0.0
      - FREECAD_PORT=12345
      - LOG_LEVEL=INFO
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '2'
        reservations:
          memory: 2G
          cpus: '1'

  prometheus:
    image: prom/prometheus:latest
    container_name: freecad-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
    depends_on:
      - freecad-mcp

  grafana:
    image: grafana/grafana:latest
    container_name: freecad-grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-data:/var/lib/grafana
    depends_on:
      - prometheus

volumes:
  grafana-data:
```

**Dockerfile:**

```dockerfile
FROM ubuntu:22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    software-properties-common \
    wget \
    curl \
    xvfb \
    libgl1-mesa-glx \
    libglib2.0-0 \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install FreeCAD
RUN add-apt-repository ppa:freecad-maintainers/freecad-stable \
    && apt-get update \
    && apt-get install -y freecad \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy application files
COPY requirements.txt .
COPY src/ ./src/
COPY config/ ./config/

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Create non-root user
RUN useradd -m -s /bin/bash freecad \
    && chown -R freecad:freecad /app

USER freecad

# Set environment variables
ENV DISPLAY=:99
ENV QT_QPA_PLATFORM=offscreen
ENV FREECAD_USER_HOME=/app

# Expose ports
EXPOSE 12345 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Start script
COPY --chown=freecad:freecad entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
```

**entrypoint.sh:**

```bash
#!/bin/bash
set -e

# Start virtual framebuffer for headless operation
Xvfb :99 -screen 0 1920x1080x24 &
sleep 2

# Start FreeCAD in server mode
freecad --console &
FREECAD_PID=$!
sleep 5

# Start MCP server
python3 /app/src/freecad_mcp_server.py &
MCP_PID=$!

# Wait for either process to exit
wait -n $FREECAD_PID $MCP_PID

# If one exits, kill the other
kill $FREECAD_PID $MCP_PID 2>/dev/null || true
```

#### Performance Monitoring and Diagnostics

**Metrics Tracked:**

| Metric Category | Specific Metrics |
|-----------------|------------------|
| Connection | Latency (ms), connection state, reconnection count |
| Tool Execution | Duration per tool, success/failure rate, queue depth |
| Cache | Hit rate, miss rate, eviction count, memory usage |
| Resources | CPU usage, memory consumption, file descriptors |
| Errors | Error rate by type, error messages, stack traces |

**Prometheus Metrics Endpoint Example:**

```python
# diagnostics.py excerpt
from prometheus_client import Counter, Histogram, Gauge, generate_latest

# Define metrics
TOOL_CALLS = Counter(
    'freecad_mcp_tool_calls_total',
    'Total number of tool calls',
    ['tool_name', 'status']
)

TOOL_DURATION = Histogram(
    'freecad_mcp_tool_duration_seconds',
    'Tool execution duration',
    ['tool_name'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

CONNECTION_STATUS = Gauge(
    'freecad_mcp_connection_status',
    'FreeCAD connection status (1=connected, 0=disconnected)'
)

CACHE_HIT_RATE = Gauge(
    'freecad_mcp_cache_hit_rate',
    'Cache hit rate percentage'
)

class DiagnosticsManager:
    def record_tool_call(self, tool_name: str, duration: float, success: bool):
        status = 'success' if success else 'failure'
        TOOL_CALLS.labels(tool_name=tool_name, status=status).inc()
        TOOL_DURATION.labels(tool_name=tool_name).observe(duration)

    def update_connection_status(self, connected: bool):
        CONNECTION_STATUS.set(1 if connected else 0)

    def update_cache_stats(self, hits: int, misses: int):
        total = hits + misses
        rate = (hits / total * 100) if total > 0 else 0
        CACHE_HIT_RATE.set(rate)

    def get_metrics(self) -> bytes:
        return generate_latest()
```

---

### 4. spkane/freecad-robust-mcp-and-more: Production-Hardened Infrastructure

| Attribute | Value |
|-----------|-------|
| **Repository** | github.com/spkane/freecad-robust-mcp-and-more |
| **Docker Hub** | spkane/freecad-robust-mcp (227 pulls) |
| **License** | MIT |
| **Architecture** | Bridge-based with XML-RPC/JSON-RPC dual protocol support |

#### Enterprise Focus and Governance

Originally named "FreeCAD MCP," the project was renamed "Robust MCP Server" to reflect its broader scope and stability improvements. The implementation targets:
- **GUI and headless operation** support
- **Comprehensive CAD operations** (82+ tools)
- **Production-grade reliability** through bridge architecture
- **Standalone FreeCAD macros** for non-AI automation

The project includes a macro registered in the official FreeCAD documentation: "Macro Start MCP Bridge", providing community recognition and validation.

#### Tri-Mode Connection Architecture

| Mode | Protocol | Port | Platform Support | Use Case |
|------|----------|------|------------------|----------|
| **XML-RPC** | HTTP | 9875 | All | Recommended, network-transparent |
| **Socket** | JSON-RPC/TCP | 9876 | All | Lower latency alternative |
| **Embedded** | Direct Python | N/A | Linux only | Zero overhead, maximum performance |

**XML-RPC Mode Configuration:**

```bash
export FREECAD_MODE=xmlrpc
export FREECAD_SOCKET_HOST=localhost
export FREECAD_SOCKET_PORT=9875
```

**Socket Mode Configuration:**

```bash
export FREECAD_MODE=socket
export FREECAD_SOCKET_HOST=localhost
export FREECAD_SOCKET_PORT=9876
```

**Embedded Mode Configuration (Linux Only):**

```bash
export FREECAD_MODE=embedded
export PYTHONPATH="/usr/lib/freecad/lib:$PYTHONPATH"
```

#### Docker Deployment Complexity

**macOS/Windows (Docker Desktop):**

```bash
docker run -i --rm \
  -e FREECAD_MODE=xmlrpc \
  -e FREECAD_SOCKET_HOST=host.docker.internal \
  -e FREECAD_SOCKET_PORT=9875 \
  spkane/freecad-robust-mcp:latest
```

**Linux Option 1: Host Networking (Recommended):**

```bash
docker run -i --rm \
  --network=host \
  -e FREECAD_MODE=xmlrpc \
  -e FREECAD_SOCKET_HOST=localhost \
  -e FREECAD_SOCKET_PORT=9875 \
  spkane/freecad-robust-mcp:latest
```

**Linux Option 2: Explicit IP Address:**

```bash
# Get host IP
HOST_IP=$(hostname -I | awk '{print $1}')

docker run -i --rm \
  -e FREECAD_MODE=xmlrpc \
  -e FREECAD_SOCKET_HOST=$HOST_IP \
  -e FREECAD_SOCKET_PORT=9875 \
  spkane/freecad-robust-mcp:latest
```

**Linux Option 3: Host Gateway (Docker 20.10+):**

```bash
docker run -i --rm \
  --add-host=host.docker.internal:host-gateway \
  -e FREECAD_MODE=xmlrpc \
  -e FREECAD_SOCKET_HOST=host.docker.internal \
  -e FREECAD_SOCKET_PORT=9875 \
  spkane/freecad-robust-mcp:latest
```

**Claude Desktop Configuration for Docker:**

```json
{
  "mcpServers": {
    "freecad-robust": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "--network=host",
        "-e", "FREECAD_MODE=xmlrpc",
        "-e", "FREECAD_SOCKET_HOST=localhost",
        "spkane/freecad-robust-mcp:latest"
      ]
    }
  }
}
```

#### Bridge Architecture Details

```python
# Simplified bridge architecture example
import xmlrpc.client
import json
from typing import Any, Dict, Optional

class FreeCADBridge:
    """Bridge between MCP protocol and FreeCAD API."""

    def __init__(self, host: str = "localhost", port: int = 9875):
        self.host = host
        self.port = port
        self._proxy: Optional[xmlrpc.client.ServerProxy] = None

    def connect(self) -> bool:
        """Establish connection to FreeCAD RPC server."""
        try:
            self._proxy = xmlrpc.client.ServerProxy(
                f"http://{self.host}:{self.port}/",
                allow_none=True
            )
            # Test connection
            self._proxy.system.listMethods()
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def execute_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an MCP tool via the bridge."""
        if not self._proxy:
            raise ConnectionError("Not connected to FreeCAD")

        try:
            # Map MCP tools to FreeCAD RPC methods
            method_map = {
                "create_document": self._create_document,
                "create_object": self._create_object,
                "execute_code": self._execute_code,
                "get_objects": self._get_objects,
                "export_model": self._export_model,
            }

            handler = method_map.get(tool_name)
            if not handler:
                raise ValueError(f"Unknown tool: {tool_name}")

            result = handler(params)
            return {"success": True, "result": result}

        except xmlrpc.client.Fault as e:
            return {"success": False, "error": str(e)}

    def _create_document(self, params: Dict) -> Dict:
        """Create a new FreeCAD document."""
        name = params.get("name", "Unnamed")
        return self._proxy.create_document(name)

    def _create_object(self, params: Dict) -> Dict:
        """Create a geometric object."""
        doc_name = params["document"]
        obj_type = params["type"]
        properties = params.get("properties", {})
        return self._proxy.create_object(doc_name, obj_type, properties)

    def _execute_code(self, params: Dict) -> Dict:
        """Execute arbitrary Python code in FreeCAD."""
        code = params["code"]
        return self._proxy.execute_code(code)

    def _get_objects(self, params: Dict) -> list:
        """Get all objects in a document."""
        doc_name = params["document"]
        return self._proxy.get_objects(doc_name)

    def _export_model(self, params: Dict) -> Dict:
        """Export model to file."""
        doc_name = params["document"]
        file_path = params["path"]
        file_format = params.get("format", "step")
        return self._proxy.export_model(doc_name, file_path, file_format)
```

---

### 5. Additional Implementations: Emerging Solutions

#### ATOI-Ming/FreeCAD-MCP

| Attribute | Value |
|-----------|-------|
| **Repository** | github.com/ATOI-Ming/FreeCAD-MCP |
| **Status** | Early-stage or private maintenance |
| **Focus** | Plugin approach for model creation, macro execution, view management |

Limited public documentation available. The implementation appears to focus on:
- Model creation automation
- Macro execution capabilities
- View management features

#### lucygoodchild/freecad-mcp-server

| Attribute | Value |
|-----------|-------|
| **Repository** | github.com/lucygoodchild/freecad-mcp-server |
| **GitHub Stars** | 4 |
| **Language** | TypeScript |
| **Architecture** | Node.js-based MCP server |

The TypeScript implementation enables:
- Web-based FreeCAD frontends through MCP abstraction
- Integration with Electron-based applications
- npm ecosystem tooling and deployment
- Browser-based AI assistant interfaces

**TypeScript MCP Server Structure:**

```typescript
// Example TypeScript MCP server structure
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

interface FreeCADConnection {
  host: string;
  port: number;
  connected: boolean;
}

class FreeCADMCPServer {
  private server: Server;
  private connection: FreeCADConnection;

  constructor() {
    this.server = new Server(
      { name: "freecad-mcp", version: "1.0.0" },
      { capabilities: { tools: {} } }
    );

    this.connection = {
      host: "localhost",
      port: 9875,
      connected: false
    };

    this.registerTools();
  }

  private registerTools(): void {
    this.server.setRequestHandler("tools/list", async () => ({
      tools: [
        {
          name: "create_box",
          description: "Create a box primitive in FreeCAD",
          inputSchema: {
            type: "object",
            properties: {
              length: { type: "number", description: "Box length in mm" },
              width: { type: "number", description: "Box width in mm" },
              height: { type: "number", description: "Box height in mm" },
              position: {
                type: "array",
                items: { type: "number" },
                description: "Position [x, y, z]"
              }
            },
            required: ["length", "width", "height"]
          }
        },
        {
          name: "execute_python",
          description: "Execute Python code in FreeCAD",
          inputSchema: {
            type: "object",
            properties: {
              code: { type: "string", description: "Python code to execute" }
            },
            required: ["code"]
          }
        }
      ]
    }));

    this.server.setRequestHandler("tools/call", async (request) => {
      const { name, arguments: args } = request.params;

      switch (name) {
        case "create_box":
          return this.createBox(args);
        case "execute_python":
          return this.executePython(args);
        default:
          throw new Error(`Unknown tool: ${name}`);
      }
    });
  }

  private async createBox(args: any): Promise<any> {
    const code = `
import FreeCAD
import Part

doc = FreeCAD.ActiveDocument or FreeCAD.newDocument("Untitled")
box = doc.addObject("Part::Box", "Box")
box.Length = ${args.length}
box.Width = ${args.width}
box.Height = ${args.height}
${args.position ? `box.Placement.Base = FreeCAD.Vector(${args.position.join(", ")})` : ""}
doc.recompute()
print(f"Created box: {box.Name}")
    `;
    return this.executePython({ code });
  }

  private async executePython(args: any): Promise<any> {
    // Send to FreeCAD via RPC
    const response = await fetch(
      `http://${this.connection.host}:${this.connection.port}/execute`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: args.code })
      }
    );
    return response.json();
  }

  async start(): Promise<void> {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
  }
}

const server = new FreeCADMCPServer();
server.start().catch(console.error);
```

---

## Technical Architecture Deep Dive

### Communication Protocol Analysis

| Protocol | Transport | Port | Latency | Overhead | Debug Ease | Implementations |
|----------|-----------|------|---------|----------|------------|-----------------|
| XML-RPC | HTTP | 9875 | Medium | High | Excellent | neka-nat, spkane |
| JSON-RPC | TCP Socket | 9876 | Low | Low | Moderate | bonninr, spkane |
| stdio | Process I/O | N/A | Lowest | Minimal | Good | jango-blockchained |
| Embedded | Direct Import | N/A | Zero | Zero | Limited | jango-blockchained, spkane |

#### XML-RPC Implementation Example

```python
# FreeCAD addon side (server)
from xmlrpc.server import SimpleXMLRPCServer
import FreeCAD
import FreeCADGui

class FreeCADRPCServer:
    def __init__(self, host="localhost", port=9875):
        self.server = SimpleXMLRPCServer(
            (host, port),
            allow_none=True,
            logRequests=False
        )
        self.server.register_introspection_functions()
        self._register_methods()

    def _register_methods(self):
        self.server.register_function(self.create_document)
        self.server.register_function(self.create_object)
        self.server.register_function(self.execute_code)
        self.server.register_function(self.get_objects)
        self.server.register_function(self.get_view)

    def create_document(self, name: str) -> dict:
        """Create a new FreeCAD document."""
        doc = FreeCAD.newDocument(name)
        return {
            "name": doc.Name,
            "label": doc.Label,
            "objects": []
        }

    def create_object(self, doc_name: str, obj_type: str, properties: dict) -> dict:
        """Create an object in the specified document."""
        doc = FreeCAD.getDocument(doc_name)
        if not doc:
            raise ValueError(f"Document '{doc_name}' not found")

        obj = doc.addObject(obj_type, properties.get("name", "Object"))

        # Set properties
        for key, value in properties.items():
            if key != "name" and hasattr(obj, key):
                setattr(obj, key, value)

        doc.recompute()

        return {
            "name": obj.Name,
            "label": obj.Label,
            "type": obj.TypeId
        }

    def execute_code(self, code: str) -> dict:
        """Execute Python code in FreeCAD context."""
        import io
        import sys

        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()

        try:
            exec(code, {"FreeCAD": FreeCAD, "FreeCADGui": FreeCADGui})
            output = sys.stdout.getvalue()
            return {"success": True, "output": output}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            sys.stdout = old_stdout

    def get_objects(self, doc_name: str) -> list:
        """Get all objects in a document."""
        doc = FreeCAD.getDocument(doc_name)
        if not doc:
            return []

        objects = []
        for obj in doc.Objects:
            obj_info = {
                "name": obj.Name,
                "label": obj.Label,
                "type": obj.TypeId,
            }

            # Add geometric properties if available
            if hasattr(obj, "Shape") and obj.Shape:
                obj_info["volume"] = obj.Shape.Volume
                obj_info["area"] = obj.Shape.Area
                obj_info["boundBox"] = {
                    "min": list(obj.Shape.BoundBox.getPoint(0)),
                    "max": list(obj.Shape.BoundBox.getPoint(7))
                }

            objects.append(obj_info)

        return objects

    def get_view(self) -> str:
        """Capture screenshot of active view as base64."""
        import base64
        import tempfile
        import os

        view = FreeCADGui.ActiveDocument.ActiveView

        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            temp_path = f.name

        view.saveImage(temp_path, 1920, 1080, "Current")

        # Read and encode
        with open(temp_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        os.unlink(temp_path)

        return image_data

    def serve_forever(self):
        """Start serving requests."""
        print(f"FreeCAD RPC Server running on port {self.server.server_address[1]}")
        self.server.serve_forever()
```

```python
# MCP client side
import xmlrpc.client
from mcp.server import Server
from mcp.types import Tool, TextContent

class FreeCADMCPClient:
    def __init__(self):
        self.rpc = xmlrpc.client.ServerProxy("http://localhost:9875/")
        self.server = Server("freecad-mcp")
        self._setup_handlers()

    def _setup_handlers(self):
        @self.server.list_tools()
        async def list_tools():
            return [
                Tool(
                    name="create_document",
                    description="Create a new FreeCAD document",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Document name"}
                        },
                        "required": ["name"]
                    }
                ),
                Tool(
                    name="create_box",
                    description="Create a box primitive",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "document": {"type": "string"},
                            "length": {"type": "number"},
                            "width": {"type": "number"},
                            "height": {"type": "number"}
                        },
                        "required": ["document", "length", "width", "height"]
                    }
                ),
                Tool(
                    name="execute_code",
                    description="Execute Python code in FreeCAD",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "code": {"type": "string"}
                        },
                        "required": ["code"]
                    }
                )
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict):
            if name == "create_document":
                result = self.rpc.create_document(arguments["name"])
            elif name == "create_box":
                result = self.rpc.create_object(
                    arguments["document"],
                    "Part::Box",
                    {
                        "Length": arguments["length"],
                        "Width": arguments["width"],
                        "Height": arguments["height"]
                    }
                )
            elif name == "execute_code":
                result = self.rpc.execute_code(arguments["code"])
            else:
                raise ValueError(f"Unknown tool: {name}")

            return [TextContent(type="text", text=str(result))]
```

### Security Architecture and Threat Model

#### Execute_Code Security Implications

The `execute_code` tool represents the highest-risk MCP capability:

**Attack Surface:**

| Attack Vector | Risk Level | Description |
|---------------|------------|-------------|
| File System Access | Critical | Read/write/delete any accessible file |
| Network Operations | Critical | Data exfiltration, C2 communication |
| System Commands | Critical | Via `os.system()` or `subprocess` |
| Memory Manipulation | High | Corrupt FreeCAD state |
| Resource Exhaustion | Medium | DoS via infinite loops or memory allocation |

**Mitigation Mechanisms:**

```python
# Example: Code analysis for dangerous patterns
import ast
import re

class CodeSecurityAnalyzer:
    """Analyze Python code for potentially dangerous operations."""

    DANGEROUS_IMPORTS = {
        'os', 'subprocess', 'socket', 'urllib', 'requests',
        'shutil', 'pathlib', 'sys', 'importlib', 'pickle',
        'marshal', 'shelve', 'ctypes', 'multiprocessing'
    }

    DANGEROUS_FUNCTIONS = {
        'eval', 'exec', 'compile', 'open', 'input',
        '__import__', 'getattr', 'setattr', 'delattr'
    }

    DANGEROUS_PATTERNS = [
        r'os\.(system|popen|exec|spawn)',
        r'subprocess\.(run|call|Popen|check_output)',
        r'socket\.',
        r'urllib\.request',
        r'requests\.(get|post|put|delete)',
        r'open\s*\([^)]*["\']w["\']',  # File write
        r'shutil\.(rmtree|move|copy)',
    ]

    def analyze(self, code: str) -> dict:
        """Analyze code and return security assessment."""
        findings = {
            "safe": True,
            "warnings": [],
            "blocked": []
        }

        # Check for dangerous imports
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split('.')[0] in self.DANGEROUS_IMPORTS:
                            findings["blocked"].append(
                                f"Dangerous import: {alias.name}"
                            )
                            findings["safe"] = False

                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.split('.')[0] in self.DANGEROUS_IMPORTS:
                        findings["blocked"].append(
                            f"Dangerous import: {node.module}"
                        )
                        findings["safe"] = False

                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in self.DANGEROUS_FUNCTIONS:
                            findings["warnings"].append(
                                f"Potentially dangerous function: {node.func.id}"
                            )

        except SyntaxError as e:
            findings["blocked"].append(f"Syntax error: {e}")
            findings["safe"] = False

        # Pattern matching for obfuscated dangerous code
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, code):
                findings["blocked"].append(f"Dangerous pattern detected: {pattern}")
                findings["safe"] = False

        return findings


# Example usage in MCP server
class SecureCodeExecutor:
    def __init__(self):
        self.analyzer = CodeSecurityAnalyzer()
        self.allowed_globals = {
            'FreeCAD': __import__('FreeCAD'),
            'Part': __import__('Part'),
            'Draft': __import__('Draft'),
            'Sketcher': __import__('Sketcher'),
            'math': __import__('math'),
            '__builtins__': {
                'print': print,
                'range': range,
                'len': len,
                'str': str,
                'int': int,
                'float': float,
                'list': list,
                'dict': dict,
                'tuple': tuple,
                'abs': abs,
                'min': min,
                'max': max,
                'sum': sum,
                'round': round,
            }
        }

    def execute(self, code: str) -> dict:
        """Execute code with security checks."""
        # Analyze code
        analysis = self.analyzer.analyze(code)

        if not analysis["safe"]:
            return {
                "success": False,
                "error": "Code blocked by security analysis",
                "details": analysis["blocked"]
            }

        # Execute in restricted environment
        try:
            exec(code, self.allowed_globals, {})
            return {"success": True, "warnings": analysis["warnings"]}
        except Exception as e:
            return {"success": False, "error": str(e)}
```

#### Security Best Practices

**Mandatory Measures:**

```yaml
# security-policy.yaml
mandatory:
  - Review and approve all AI-generated code before execution
  - Run FreeCAD MCP servers with least-privilege user accounts
  - Disable network access for FreeCAD process unless required
  - Use stdio transport for local-only deployments
  - Implement rate limiting on execute_code operations

recommended:
  - Deploy FreeCAD in containerized environment with filesystem restrictions
  - Implement allowlist for Python imports permitted in execute_code
  - Log all executed code for audit trails
  - Configure mandatory code review for production workflows
  - Implement timeout limits on script execution (30 seconds max)

enterprise:
  - Require authentication for remote MCP server access
  - Implement role-based access control (RBAC) for tool categories
  - Use mutual TLS for network communications
  - Deploy intrusion detection monitoring MCP traffic
  - Establish security incident response procedures
```

### Performance Considerations

#### FreeCAD Performance Bottlenecks

| Issue | Impact | Mitigation |
|-------|--------|------------|
| Large assemblies (16,384+ parts) | Multi-minute operations | Use single-shape variants where possible |
| Memory consumption | >4GB RAM, peaks to 15GB+ | Increase container memory limits |
| Recursive operations | Exponential scaling | Limit recursion depth |
| Recomputation delays | UI unresponsiveness | Batch operations, defer recompute |

#### MCP-Specific Performance Challenges

**Context Window Consumption:**

```python
# Example: Tool description token consumption analysis
import tiktoken

def analyze_tool_tokens(tools: list) -> dict:
    """Analyze token consumption of tool definitions."""
    encoder = tiktoken.encoding_for_model("gpt-4")

    results = {
        "total_tokens": 0,
        "tools": []
    }

    for tool in tools:
        tool_json = json.dumps(tool, indent=2)
        token_count = len(encoder.encode(tool_json))

        results["tools"].append({
            "name": tool["name"],
            "tokens": token_count
        })
        results["total_tokens"] += token_count

    return results

# Example output for 82-tool server:
# {
#   "total_tokens": 12847,
#   "tools": [
#     {"name": "create_box", "tokens": 156},
#     {"name": "create_cylinder", "tokens": 189},
#     ...
#   ]
# }
```

**Token Optimization Strategies:**

```python
# Modular tool loading to reduce context consumption
class ModularToolProvider:
    """Load only required tool categories."""

    TOOL_CATEGORIES = {
        "primitives": ["create_box", "create_cylinder", "create_sphere", ...],
        "manipulation": ["move", "rotate", "scale", "mirror", ...],
        "boolean": ["union", "cut", "intersect", ...],
        "export": ["export_step", "export_stl", "export_obj", ...],
        "analysis": ["measure_volume", "measure_area", "get_mass", ...],
    }

    def __init__(self, enabled_categories: list = None):
        self.enabled = enabled_categories or list(self.TOOL_CATEGORIES.keys())

    def get_tools(self) -> list:
        """Get only tools from enabled categories."""
        tools = []
        for category in self.enabled:
            if category in self.TOOL_CATEGORIES:
                tools.extend(self._load_category_tools(category))
        return tools

    def _load_category_tools(self, category: str) -> list:
        """Load tool definitions for a category."""
        # Implementation would load from tool definition files
        pass

# Usage: Load only primitives and export tools
provider = ModularToolProvider(enabled_categories=["primitives", "export"])
```

---

## Use Cases and Applications

### AI-Assisted Parametric Design

#### Novice User Workflow

**User Request:** "Create a mounting bracket for a Raspberry Pi with 2.75mm holes spaced 58mm × 49mm apart, 3mm thickness, with 2mm radius fillets on all edges."

**AI-Generated Code:**

```python
import FreeCAD
import Part

doc = FreeCAD.newDocument("RaspberryPiBracket")

# Parameters
params = {
    "plate_length": 85,      # mm (Pi 4 dimensions + margin)
    "plate_width": 56,       # mm
    "thickness": 3,          # mm
    "hole_diameter": 2.75,   # mm (M2.5 clearance)
    "hole_spacing_x": 58,    # mm
    "hole_spacing_y": 49,    # mm
    "fillet_radius": 2,      # mm
    "standoff_height": 5,    # mm
    "standoff_diameter": 6,  # mm
}

# Calculate hole positions (centered on plate)
center_x = params["plate_length"] / 2
center_y = params["plate_width"] / 2
half_spacing_x = params["hole_spacing_x"] / 2
half_spacing_y = params["hole_spacing_y"] / 2

hole_positions = [
    (center_x - half_spacing_x, center_y - half_spacing_y),
    (center_x + half_spacing_x, center_y - half_spacing_y),
    (center_x - half_spacing_x, center_y + half_spacing_y),
    (center_x + half_spacing_x, center_y + half_spacing_y),
]

# Create base plate
plate = Part.makeBox(
    params["plate_length"],
    params["plate_width"],
    params["thickness"]
)

# Add fillets to all edges
plate = plate.makeFillet(params["fillet_radius"], plate.Edges)

# Create mounting holes and standoffs
for x, y in hole_positions:
    # Create standoff
    standoff = Part.makeCylinder(
        params["standoff_diameter"] / 2,
        params["standoff_height"],
        FreeCAD.Vector(x, y, params["thickness"])
    )
    plate = plate.fuse(standoff)

    # Create through hole
    hole = Part.makeCylinder(
        params["hole_diameter"] / 2,
        params["thickness"] + params["standoff_height"] + 2,
        FreeCAD.Vector(x, y, -1)
    )
    plate = plate.cut(hole)

# Add to document
bracket = doc.addObject("Part::Feature", "RaspberryPiBracket")
bracket.Shape = plate

doc.recompute()
print("Raspberry Pi mounting bracket created successfully!")
```

#### Expert User Workflow

**User Request:** "Generate a parametric involute gear with: module 2.5mm, 25 teeth, 20° pressure angle, 6mm face width, 8mm bore with DIN 6885 keyway."

**AI-Generated Code:**

```python
import FreeCAD
import Part
import math

doc = FreeCAD.newDocument("InvoluteGear")

class InvoluteGear:
    """Parametric involute spur gear generator."""

    def __init__(self, module, teeth, pressure_angle, face_width, bore, keyway_din=None):
        self.m = module                    # Module (mm)
        self.z = teeth                     # Number of teeth
        self.alpha = math.radians(pressure_angle)  # Pressure angle
        self.b = face_width                # Face width (mm)
        self.bore = bore                   # Bore diameter (mm)
        self.keyway_din = keyway_din       # DIN 6885 keyway designation

        # Calculated parameters
        self.d = self.m * self.z           # Pitch diameter
        self.da = self.d + 2 * self.m      # Tip diameter
        self.df = self.d - 2.5 * self.m    # Root diameter
        self.db = self.d * math.cos(self.alpha)  # Base diameter

    def involute(self, angle):
        """Calculate involute curve point."""
        return math.tan(angle) - angle

    def involute_angle(self, diameter):
        """Calculate involute angle at given diameter."""
        if diameter <= self.db:
            return 0
        return math.acos(self.db / diameter)

    def create_tooth_profile(self, num_points=20):
        """Generate tooth profile points."""
        points = []

        # Generate involute curve from base to tip
        for i in range(num_points):
            # Parameter from 0 to max involute angle
            t = i / (num_points - 1)

            # Diameter at this point
            r = self.db / 2 + t * (self.da / 2 - self.db / 2)

            if r < self.db / 2:
                continue

            # Involute angle
            inv_angle = self.involute_angle(2 * r)

            # Tooth thickness angle at pitch circle
            tooth_thickness = math.pi / (2 * self.z)

            # Point angle
            angle = tooth_thickness + self.involute(self.alpha) - inv_angle

            x = r * math.cos(angle)
            y = r * math.sin(angle)
            points.append(FreeCAD.Vector(x, y, 0))

        return points

    def create_gear(self):
        """Create the complete gear shape."""
        # Create one tooth profile
        profile_points = self.create_tooth_profile()

        # Create tooth outline as wire
        # (Simplified - full implementation would include root fillet)
        tooth_edges = []
        for i in range(len(profile_points) - 1):
            edge = Part.makeLine(profile_points[i], profile_points[i + 1])
            tooth_edges.append(edge)

        # Mirror for other side of tooth
        mirror_points = [FreeCAD.Vector(p.x, -p.y, 0) for p in reversed(profile_points)]
        for i in range(len(mirror_points) - 1):
            edge = Part.makeLine(mirror_points[i], mirror_points[i + 1])
            tooth_edges.append(edge)

        # Create full tooth wire
        tooth_wire = Part.Wire(tooth_edges)

        # Close tooth at root
        root_arc = Part.makeCircle(
            self.df / 2,
            FreeCAD.Vector(0, 0, 0),
            FreeCAD.Vector(0, 0, 1),
            -360 / self.z / 2,
            360 / self.z / 2
        )

        # Create solid tooth by extrusion
        tooth_face = Part.Face(tooth_wire)
        tooth_solid = tooth_face.extrude(FreeCAD.Vector(0, 0, self.b))

        # Rotate and fuse all teeth
        gear = tooth_solid
        for i in range(1, self.z):
            angle = 360 * i / self.z
            rotated_tooth = tooth_solid.copy()
            rotated_tooth.rotate(
                FreeCAD.Vector(0, 0, 0),
                FreeCAD.Vector(0, 0, 1),
                angle
            )
            gear = gear.fuse(rotated_tooth)

        # Create bore
        bore_cyl = Part.makeCylinder(
            self.bore / 2,
            self.b + 2,
            FreeCAD.Vector(0, 0, -1)
        )
        gear = gear.cut(bore_cyl)

        # Add keyway if specified
        if self.keyway_din:
            keyway = self.create_keyway()
            gear = gear.cut(keyway)

        return gear

    def create_keyway(self):
        """Create DIN 6885 keyway."""
        # DIN 6885 dimensions for 8mm shaft
        # (Simplified - would normally lookup from table)
        key_width = 3      # mm
        key_depth = 1.8    # mm (in hub)

        keyway = Part.makeBox(
            key_width,
            self.bore / 2 + key_depth,
            self.b + 2
        )
        keyway.translate(FreeCAD.Vector(-key_width / 2, 0, -1))

        return keyway


# Create gear with specified parameters
gear_params = InvoluteGear(
    module=2.5,
    teeth=25,
    pressure_angle=20,
    face_width=6,
    bore=8,
    keyway_din="6885"
)

gear_shape = gear_params.create_gear()

# Add to document
gear_obj = doc.addObject("Part::Feature", "InvoluteGear")
gear_obj.Shape = gear_shape

# Add parameters as properties for parametric updates
gear_obj.addProperty("App::PropertyFloat", "Module", "Gear", "Gear module")
gear_obj.Module = 2.5
gear_obj.addProperty("App::PropertyInteger", "Teeth", "Gear", "Number of teeth")
gear_obj.Teeth = 25
gear_obj.addProperty("App::PropertyFloat", "PressureAngle", "Gear", "Pressure angle")
gear_obj.PressureAngle = 20
gear_obj.addProperty("App::PropertyFloat", "FaceWidth", "Gear", "Face width")
gear_obj.FaceWidth = 6

doc.recompute()

print(f"Gear created:")
print(f"  Pitch diameter: {gear_params.d:.2f} mm")
print(f"  Tip diameter: {gear_params.da:.2f} mm")
print(f"  Root diameter: {gear_params.df:.2f} mm")
print(f"  Base diameter: {gear_params.db:.2f} mm")
```

### Design Automation and Batch Processing

**Product Family Generation Example:**

```python
import FreeCAD
import Part
import csv
import os

def generate_enclosure_family(csv_path: str, output_dir: str):
    """Generate product family from CSV specifications."""

    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        variants = list(reader)

    for variant in variants:
        doc = FreeCAD.newDocument(variant['part_number'])

        # Parse dimensions
        length = float(variant['length'])
        width = float(variant['width'])
        height = float(variant['height'])
        wall_thickness = float(variant['wall_thickness'])
        corner_radius = float(variant['corner_radius'])

        # Create outer shell
        outer = Part.makeBox(length, width, height)
        outer = outer.makeFillet(corner_radius, outer.Edges)

        # Create inner cavity
        inner = Part.makeBox(
            length - 2 * wall_thickness,
            width - 2 * wall_thickness,
            height - wall_thickness
        )
        inner.translate(FreeCAD.Vector(
            wall_thickness,
            wall_thickness,
            wall_thickness
        ))
        inner = inner.makeFillet(
            corner_radius - wall_thickness,
            inner.Edges
        )

        # Boolean cut for hollow enclosure
        enclosure = outer.cut(inner)

        # Add mounting bosses if specified
        if variant.get('mounting_holes'):
            holes = variant['mounting_holes'].split(';')
            for hole_spec in holes:
                x, y, dia = map(float, hole_spec.split(','))
                boss = Part.makeCylinder(
                    dia * 1.5,
                    wall_thickness * 2,
                    FreeCAD.Vector(x, y, 0)
                )
                enclosure = enclosure.fuse(boss)

                hole = Part.makeCylinder(
                    dia / 2,
                    wall_thickness * 3,
                    FreeCAD.Vector(x, y, -wall_thickness)
                )
                enclosure = enclosure.cut(hole)

        # Add to document
        obj = doc.addObject("Part::Feature", "Enclosure")
        obj.Shape = enclosure
        doc.recompute()

        # Export files
        base_name = variant['part_number']

        # Export STEP
        step_path = os.path.join(output_dir, f"{base_name}.step")
        Part.export([obj], step_path)

        # Export STL
        stl_path = os.path.join(output_dir, f"{base_name}.stl")
        obj.Shape.exportStl(stl_path)

        # Save FreeCAD file
        fcstd_path = os.path.join(output_dir, f"{base_name}.FCStd")
        doc.saveAs(fcstd_path)

        print(f"Generated: {base_name}")

        FreeCAD.closeDocument(doc.Name)

# Example CSV format:
# part_number,length,width,height,wall_thickness,corner_radius,mounting_holes
# ENC-S-001,100,60,30,2.5,3,"10,10,3;90,10,3;10,50,3;90,50,3"
# ENC-M-001,150,100,50,3,5,"15,15,4;135,15,4;15,85,4;135,85,4"
```

---

## Limitations and Challenges

### Technical Limitations

| Limitation | Impact | Workaround |
|------------|--------|------------|
| Complex assembly constraints | Cannot define kinematic joints, gear relationships | Use specialized FreeCAD workbenches (A2plus, Assembly4) |
| Sketcher integration gaps | Limited parametric sketch control | Use `execute_code` with full Sketcher API |
| Error recovery unreliability | AI struggles with technical error messages | Implement better error parsing and suggestions |
| Visual design intent | Aesthetic judgments beyond automation | Human review and refinement stages |

### MCP Ecosystem Challenges

| Challenge | Impact | Mitigation |
|-----------|--------|------------|
| Incomplete tool descriptions | Wrong tool selection, failed operations | Improve tool metadata, add examples |
| Context window pollution | Reduced conversation capacity | Modular tool loading |
| Standardization absence | Non-portable workflows | Community standardization effort |
| Security gaps | Enterprise adoption barriers | Implement authentication, sandboxing |

### Platform and Deployment Challenges

```yaml
# Common issues and solutions
python_environment:
  issue: "Version mismatches between FreeCAD and MCP server"
  solution: "Use uvx for isolated environments or Docker"

docker_networking:
  issue: "Platform-specific hostname resolution"
  solutions:
    macos_windows: "Use host.docker.internal"
    linux_host_mode: "Use --network=host"
    linux_gateway: "Use --add-host=host.docker.internal:host-gateway"

freecad_versions:
  issue: "API differences between 0.21 and 1.0"
  solution: "Document minimum version, implement version detection"
```

---

## Future Directions and Recommendations

### Roadmap Overview

| Timeframe | Focus Areas |
|-----------|-------------|
| **2025-2026** | Protocol standardization, security hardening, visual feedback optimization |
| **2026-2027** | Multimodal integration, domain-specific tools, multi-agent systems |
| **2027-2030** | Autonomous design agents, generative design integration, democratization |

### Near-Term Priorities (2025-2026)

**1. Protocol Standardization:**

```yaml
# Proposed FreeCAD MCP Standard v1.0
tools:
  naming_convention: "snake_case, verb_noun format"
  categories:
    - primitives
    - manipulation
    - boolean
    - export
    - analysis
    - sketch

data_formats:
  geometry:
    vertices: "[[x, y, z], ...]"
    edges: "[[v1_idx, v2_idx], ...]"
    faces: "[[edge_indices], ...]"

  transforms:
    position: "[x, y, z]"
    rotation: "[x, y, z, w]"  # Quaternion
    scale: "[sx, sy, sz]"

error_codes:
  - code: "FC001"
    name: "DocumentNotFound"
    description: "Specified document does not exist"
  - code: "FC002"
    name: "ObjectNotFound"
    description: "Specified object does not exist"
  - code: "FC003"
    name: "InvalidGeometry"
    description: "Geometry operation failed"
```

**2. Security Hardening:**

```python
# Sandboxed execution environment
import seccomp
import resource

class SandboxedExecutor:
    """Execute code in restricted sandbox."""

    def __init__(self):
        self.filter = seccomp.SyscallFilter(seccomp.KILL)

        # Allow only safe syscalls
        safe_syscalls = [
            seccomp.Syscall.read,
            seccomp.Syscall.write,
            seccomp.Syscall.mmap,
            seccomp.Syscall.munmap,
            seccomp.Syscall.brk,
            seccomp.Syscall.exit_group,
        ]

        for syscall in safe_syscalls:
            self.filter.add_rule(seccomp.ALLOW, syscall)

    def execute(self, code: str, timeout: int = 30):
        """Execute code with resource limits."""
        # Set resource limits
        resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout))
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))  # No file writes

        # Apply seccomp filter
        self.filter.load()

        # Execute
        exec(code, self.get_safe_globals())
```

### Recommendations by Stakeholder

#### For Users

| User Profile | Recommended Server | Rationale |
|--------------|-------------------|-----------|
| Beginner exploring AI + CAD | neka-nat/freecad-mcp | Easiest installation, visual feedback |
| Python developer automating | bonninr/freecad_mcp | Maximum flexibility, direct execution |
| Enterprise evaluation | jango-blockchained/mcp-freecad | Multi-provider, Docker, monitoring |
| Multi-model experimentation | jango-blockchained/mcp-freecad | Native multi-provider support |
| Linux performance priority | jango-blockchained (embedded) | Zero-latency direct import |

#### For Developers

**High-Impact Contribution Areas:**

1. **Security hardening** - Sandboxing, code analysis, authentication
2. **Documentation** - Installation guides, tutorials, videos
3. **Tool providers** - Domain-specific tool collections
4. **Performance** - Profiling, caching, optimization
5. **Testing** - Automated test suites, CI/CD

#### For Organizations

**Pilot Project Framework:**

```yaml
pilot_project:
  phase_1_setup:
    duration: "2 weeks"
    activities:
      - Select non-critical design domain
      - Install chosen MCP implementation
      - Configure AI provider integration
      - Train 5-10 early adopters

  phase_2_evaluation:
    duration: "4 weeks"
    metrics:
      - Usage frequency
      - Error rates
      - User satisfaction scores
      - Time savings estimates
    activities:
      - Daily design tasks using MCP
      - Document issues and workarounds
      - Weekly feedback sessions

  phase_3_assessment:
    duration: "2 weeks"
    activities:
      - Compile metrics report
      - Security review
      - Cost-benefit analysis
      - Go/no-go recommendation

  success_criteria:
    - Error rate < 10%
    - User satisfaction > 7/10
    - Demonstrated time savings > 20%
    - No security incidents
```

---

## Conclusion

FreeCAD MCP servers represent the early stages of a profound transformation in computer-aided design, where natural language interfaces democratize access to parametric 3D modeling while accelerating workflows for experienced practitioners. The six implementations identified on GitHub demonstrate vibrant community innovation with diverse architectural approaches, from minimalist 2-tool systems prioritizing flexibility to comprehensive 82-tool frameworks targeting enterprise production.

### Key Takeaways

| Aspect | Current State | Future Direction |
|--------|--------------|------------------|
| **Implementations** | 6 active, fragmented | Consolidation, standardization |
| **Architecture** | Diverse protocols (XML-RPC, JSON-RPC, socket, embedded) | Convergence on stdio local, HTTP/SSE remote |
| **AI Providers** | Claude-dominant, emerging multi-provider | Universal multi-model support |
| **Security** | Human-in-the-loop primary defense | Sandboxing, authentication, audit logging |
| **Adoption** | Hobbyist/developer focus | Enterprise readiness |

### Impact Potential

The explosive growth of the MCP ecosystem—$95.2 billion market, 28% Fortune 500 adoption, 33% monthly growth—creates powerful tailwinds for FreeCAD MCP development. As standardization matures, security hardens, and AI models improve, FreeCAD MCP servers will evolve from experimental developer tools to production infrastructure enabling AI-native CAD workflows.

The democratizing potential is substantial: natural language interfaces could make parametric 3D modeling accessible to billions currently excluded by CAD complexity, fundamentally expanding who can participate in design and manufacturing.

The convergence of open-source parametric CAD (FreeCAD), standardized AI integration (MCP), and frontier language models (Claude 4, GPT-4o, Gemini 2.5) creates unprecedented opportunity. The implementations documented in this research represent the first steps toward AI-native design workflows that will reshape manufacturing, education, and creative expression.

---

## References

### GitHub Repositories

- neka-nat/freecad-mcp: https://github.com/neka-nat/freecad-mcp
- bonninr/freecad_mcp: https://github.com/bonninr/freecad_mcp
- jango-blockchained/mcp-freecad: https://github.com/jango-blockchained/mcp-freecad
- spkane/freecad-robust-mcp-and-more: https://github.com/spkane/freecad-robust-mcp-and-more
- ATOI-Ming/FreeCAD-MCP: https://github.com/ATOI-Ming/FreeCAD-MCP
- lucygoodchild/freecad-mcp-server: https://github.com/lucygoodchild/freecad-mcp-server

### Documentation and Standards

- Model Context Protocol Specification: https://modelcontextprotocol.io
- MCP First Anniversary Blog: https://blog.modelcontextprotocol.io/posts/2025-11-25-first-mcp-anniversary/
- FreeCAD Python Scripting Tutorial: https://wiki.freecad.org/Python_scripting_tutorial
- FreeCAD Macro Start MCP Bridge: https://wiki.freecad.org/Macro_Start_MCP_Bridge

### Industry Analysis

- BinarCode MCP Analysis: https://www.binarcode.com/blog/mcp-or-why-2025-will-never-be-like-2025
- Stainless MCP Ecosystem Evolution: https://www.stainless.com/mcp/mcp-ai-ecosystem-evolution
- Wikipedia Model Context Protocol: https://en.wikipedia.org/wiki/Model_Context_Protocol

### Docker Resources

- spkane/freecad-robust-mcp Docker Hub: https://hub.docker.com/r/spkane/freecad-robust-mcp

---

*Document generated: January 2026*
*Research scope: FreeCAD MCP implementations on GitHub*
*Classification: Public research document*
