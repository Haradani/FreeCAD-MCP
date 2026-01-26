# FreeCAD Docker for Headless Cloud Work - Research Summary

## Overview

Comprehensive research on FreeCAD Docker setups optimized for headless cloud work.

---

## Top Recommendations

### 1. Official FreeCAD Worker (Best for Cloud/API Work)

**Repository:** [github.com/FreeCAD/FC-Worker](https://github.com/FreeCAD/FC-Worker)

| Feature | Details |
|---------|---------|
| Purpose | Containerized headless FreeCAD runner |
| Architecture | Cloud-native, minimal overhead |
| Invocation | Standard Docker and AWS Lambda-style |
| Interface | REST interface via docker-compose |

**Best For:** Production cloud deployments, API-driven CAD generation

---

### 2. LinuxServer.io FreeCAD Image (Most Flexible)

**Image:** `lscr.io/linuxserver/freecad:latest`

**Documentation:** [docs.linuxserver.io/images/docker-freecad](https://docs.linuxserver.io/images/docker-freecad/)

| Feature | Details |
|---------|---------|
| Modes | Pure headless OR optional GUI via VNC/noVNC |
| GPU Support | Nvidia GPU acceleration |
| Maintenance | Excellent documentation, well-maintained |
| Use Cases | Python API work + occasional interactive access |

**Best For:** Flexible deployments needing both headless and GUI options

---

### 3. Accetto Ubuntu/Xfce FreeCAD

**Repository:** [github.com/accetto/headless-drawing-g3](https://github.com/accetto/headless-drawing-g3/blob/master/docker/xfce-freecad/README.md)

| Feature | Details |
|---------|---------|
| Environment | Full VNC/noVNC headless desktop |
| Image Size | ~3-3.5GB (AppImage-based) |
| Startup Time | ~5 seconds (AppImage extraction) |
| Use Case | Interactive remote work |

**Best For:** Remote desktop access, interactive CAD sessions

---

## Key Setup Patterns

### For Pure Headless/API Work

```bash
# Use FreeCADCmd instead of GUI
FreeCADCmd -c console -p script.py

# Or with freecadcmd directly
freecadcmd script.py
```

**Configuration Tips:**
- Omit VNC/display configurations
- Keep volumes minimal (project directories, output only)
- No X11 or display server required

### Critical: GUI Access in Headless Mode

Even when running headless, to access `FreeCADGui` features (like colors, view objects), you need:

```python
import FreeCADGui

# Initialize GUI subsystem without showing window
FreeCADGui.showMainWindow()
mw = FreeCADGui.getMainWindow()
mw.hide()  # Hides but keeps functionality available

# Now you can use GUI features like:
# - Object colors
# - View providers
# - Visual properties
```

---

## Docker Compose Best Practices

### Resource Management
```yaml
services:
  freecad:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
```

### Permission Handling
```yaml
environment:
  - PUID=1000
  - PGID=1000
```

### Volume Strategy
```yaml
volumes:
  - ./projects:/projects      # Input files
  - ./workspace:/workspace    # Working directory
  - ./output:/output          # Generated files
```

### Best Practices Checklist

- [ ] Set resource limits for cloud deployment (CPU/memory caps)
- [ ] Use PUID/PGID environment variables for permission handling
- [ ] Separate volumes for projects, workspace, and output
- [ ] Use multi-stage builds to reduce image size
- [ ] Pin base image versions/digests for reproducibility

---

## Cloud Deployment Considerations

### Performance Metrics

| Metric | Range | Notes |
|--------|-------|-------|
| Image Size | 1.5-3.5GB | Smaller without VNC |
| Startup Time | 0.5-5 seconds | Faster without VNC |
| Memory Usage | 512MB-4GB | Depends on model complexity |

### GPU Support

Requires Nvidia runtime configuration:

```yaml
services:
  freecad:
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
```

### Security Considerations

- Run as non-root user
- Use minimal base packages
- No hardcoded secrets in images
- Use Docker secrets or environment variables for credentials
- Scan images for vulnerabilities

---

## Comparison Matrix

| Feature | FC-Worker | LinuxServer.io | Accetto |
|---------|-----------|----------------|---------|
| Headless Native | Yes | Yes | Partial |
| GUI Option | No | VNC/noVNC | VNC/noVNC |
| Image Size | ~1.5GB | ~2GB | ~3.5GB |
| Startup Speed | Fast | Medium | Slow |
| Cloud Native | Yes | Partial | No |
| GPU Support | No | Yes | Yes |
| Maintenance | Official | Active | Active |

---

## Quick Start Examples

### FC-Worker (Simplest Cloud Setup)
```bash
docker pull ghcr.io/freecad/fc-worker:latest
docker run -v $(pwd)/input:/input -v $(pwd)/output:/output \
  ghcr.io/freecad/fc-worker:latest script.py
```

### LinuxServer.io (Flexible Setup)
```bash
docker run -d \
  --name=freecad \
  -e PUID=1000 \
  -e PGID=1000 \
  -v /path/to/config:/config \
  -v /path/to/projects:/projects \
  lscr.io/linuxserver/freecad:latest
```

---

## References

- [FreeCAD FC-Worker GitHub](https://github.com/FreeCAD/FC-Worker)
- [LinuxServer.io FreeCAD Docs](https://docs.linuxserver.io/images/docker-freecad/)
- [Accetto Headless Drawing GitHub](https://github.com/accetto/headless-drawing-g3)
- [FreeCAD Python Scripting Wiki](https://wiki.freecad.org/Python_scripting_tutorial)

---

*Research compiled for FreeCAD MCP project - Headless Cloud Deployment*
