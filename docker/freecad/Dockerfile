# FreeCAD Docker image with XML-RPC server for MCP integration
#
# Based on LinuxServer.io FreeCAD image for flexibility
# Supports both headless API access and optional VNC GUI access

FROM lscr.io/linuxserver/freecad:latest

LABEL maintainer="FreeCAD MCP"
LABEL description="FreeCAD with XML-RPC server for MCP integration"

# Install additional Python packages and rendering dependencies
# Including OSMesa for headless OpenGL rendering with pyrender
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-pil \
    libegl1 \
    libgl1 \
    libglib2.0-0 \
    ffmpeg \
    xvfb \
    libosmesa6-dev \
    libglew-dev \
    freeglut3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies for RPC server and 3D rendering
# VTK for high-quality offscreen rendering with proper lighting
RUN pip3 install --no-cache-dir \
    Pillow \
    trimesh \
    matplotlib \
    numpy \
    vtk

# Copy the RPC server script and rendering utilities
COPY rpc_server.py /app/rpc_server.py
COPY render_video.py /app/render_video.py
RUN chmod +x /app/rpc_server.py /app/render_video.py

# Create entrypoint script that starts both FreeCAD and RPC server
COPY <<'EOF' /app/start.sh
#!/bin/bash
set -e

echo "Starting FreeCAD MCP container..."

# Set Qt to use offscreen platform for headless operation
export QT_QPA_PLATFORM=offscreen

# Start the RPC server using FreeCAD's embedded Python interpreter
# This ensures FreeCAD modules are available
/opt/freecad/AppRun -c "exec(open('/app/rpc_server.py').read())" &
RPC_PID=$!

echo "RPC server started (PID: $RPC_PID)"

# If ENABLE_GUI is set, start the normal LinuxServer.io entrypoint
if [ "${ENABLE_GUI:-false}" = "true" ]; then
    echo "Starting GUI mode..."
    exec /init
else
    echo "Running in headless mode (RPC only)"
    # Keep container running and wait for RPC server
    wait $RPC_PID
fi
EOF
RUN chmod +x /app/start.sh

# Create a FreeCAD startup script that loads common modules
COPY <<'EOF' /app/freecad_init.py
#!/usr/bin/env python3
"""Initialize FreeCAD with common modules loaded."""

import sys
sys.path.insert(0, '/app')

# Set up FreeCAD paths
import FreeCAD
import Part
import Draft

try:
    import PartDesign
except ImportError:
    print("PartDesign workbench not available")

try:
    import Sketcher
except ImportError:
    print("Sketcher workbench not available")

print(f"FreeCAD {FreeCAD.Version()[0]}.{FreeCAD.Version()[1]} initialized")
print(f"Available workbenches: {FreeCAD.listWorkbenches()}")
EOF
RUN chmod +x /app/freecad_init.py

# Environment variables
ENV PUID=1000
ENV PGID=1000
ENV TZ=Etc/UTC
ENV RPC_PORT=9875
ENV RPC_HOST=0.0.0.0
ENV ENABLE_GUI=false

# Expose ports
# 9875: XML-RPC server
# 3000: VNC web client (if GUI enabled)
# 5900: VNC server (if GUI enabled)
EXPOSE 9875
EXPOSE 3000
EXPOSE 5900

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python3 -c "import xmlrpc.client; c=xmlrpc.client.ServerProxy('http://localhost:9875'); print(c.ping())" || exit 1

# Set working directory
WORKDIR /config

# Default command
ENTRYPOINT ["/app/start.sh"]
