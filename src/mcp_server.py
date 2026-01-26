"""FreeCAD MCP Server - Main entry point with tool definitions."""

import asyncio
import base64
import io
import json
import logging
import os
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    TextContent,
    ImageContent,
    Tool,
    INVALID_PARAMS,
    INTERNAL_ERROR,
)
from pydantic import BaseModel, Field

from .freecad_client import FreeCADClient, ObjectInfo
from .trellis_client import TrellisClient
from .diffusion_client import DiffusionClient
from .docker_client import DockerClient
from .tunnel_client import TunnelClient, get_tunnel_client
from .glb_converter import convert_glb_to_obj, convert_glb_to_stl
from .inference_client import InferenceClient, get_inference_client
from .segmentation_pipeline import (
    SegmentationPipeline,
    SegmentAndAnalyzePipeline,
    SegmentationResult,
    create_annotation_image,
)
from .cache_manager import (
    init_cache,
    get_cache_manager,
    get_output_path,
    get_session_dir,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global clients
_freecad_client: FreeCADClient | None = None
_trellis_client: TrellisClient | None = None
_diffusion_client: DiffusionClient | None = None
_docker_client: DockerClient | None = None


def get_freecad_client() -> FreeCADClient:
    """Get or create the FreeCAD client singleton."""
    global _freecad_client
    if _freecad_client is None:
        host = os.environ.get("FREECAD_HOST", "localhost")
        port = int(os.environ.get("FREECAD_PORT", "9875"))
        _freecad_client = FreeCADClient(host=host, port=port)
    return _freecad_client


def get_trellis_client() -> TrellisClient:
    """Get or create the TRELLIS client singleton."""
    global _trellis_client
    if _trellis_client is None:
        host = os.environ.get("TRELLIS_HOST", "localhost")
        port = int(os.environ.get("TRELLIS_PORT", "8000"))
        _trellis_client = TrellisClient(host=host, port=port)
    return _trellis_client


def get_diffusion_client() -> DiffusionClient:
    """Get or create the ComfyUI diffusion client singleton."""
    global _diffusion_client
    if _diffusion_client is None:
        host = os.environ.get("DIFFUSION_HOST", "localhost")
        port = int(os.environ.get("DIFFUSION_PORT", "8188"))
        _diffusion_client = DiffusionClient(host=host, port=port)
    return _diffusion_client


def get_docker_client() -> DockerClient:
    """Get or create the Docker client singleton."""
    global _docker_client
    if _docker_client is None:
        _docker_client = DockerClient()
    return _docker_client


# =============================================================================
# Tool Input Models
# =============================================================================


class CreateDocumentInput(BaseModel):
    """Input for create_document tool."""

    name: str = Field(default="Unnamed", description="Document name")


class OpenDocumentInput(BaseModel):
    """Input for open_document tool."""

    file_path: str = Field(description="Path to .FCStd file")


class SaveDocumentInput(BaseModel):
    """Input for save_document tool."""

    doc_name: str | None = Field(default=None, description="Document name (uses active if omitted)")
    file_path: str | None = Field(default=None, description="Save path (uses existing if omitted)")


class CloseDocumentInput(BaseModel):
    """Input for close_document tool."""

    doc_name: str | None = Field(default=None, description="Document name (uses active if omitted)")


class CreatePrimitiveInput(BaseModel):
    """Input for create_primitive tool."""

    primitive_type: str = Field(description="Type: 'box', 'cylinder', 'sphere', 'cone', 'torus'")
    name: str | None = Field(default=None, description="Object name")
    doc_name: str | None = Field(default=None, description="Document name")
    length: float | None = Field(default=None, description="Box length (mm)")
    width: float | None = Field(default=None, description="Box width (mm)")
    height: float | None = Field(default=None, description="Box/cylinder/cone height (mm)")
    radius: float | None = Field(default=None, description="Sphere/cylinder radius (mm)")
    radius1: float | None = Field(default=None, description="Cone base radius / torus major radius")
    radius2: float | None = Field(default=None, description="Cone top radius / torus minor radius")


class BooleanOperationInput(BaseModel):
    """Input for boolean_operation tool."""

    operation: str = Field(description="Operation: 'union', 'cut', 'intersect'")
    obj1_name: str = Field(description="First object name")
    obj2_name: str = Field(description="Second object name")
    result_name: str | None = Field(default=None, description="Result object name")
    doc_name: str | None = Field(default=None, description="Document name")


class TransformObjectInput(BaseModel):
    """Input for transform_object tool."""

    obj_name: str = Field(description="Object to transform")
    translate: list[float] | None = Field(default=None, description="[x, y, z] translation in mm")
    rotate: list[float] | None = Field(default=None, description="[roll, pitch, yaw] in degrees")
    scale: float | list[float] | None = Field(default=None, description="Scale factor or [x, y, z]")
    doc_name: str | None = Field(default=None, description="Document name")


class FilletChamferInput(BaseModel):
    """Input for fillet_chamfer tool."""

    obj_name: str = Field(description="Object to modify")
    operation: str = Field(description="'fillet' or 'chamfer'")
    edges: list[int] | str = Field(description="Edge indices or 'all'")
    radius: float = Field(description="Radius in mm")
    doc_name: str | None = Field(default=None, description="Document name")


class CreateBodyInput(BaseModel):
    """Input for create_body tool."""

    name: str | None = Field(default=None, description="Body name")
    doc_name: str | None = Field(default=None, description="Document name")


class CreateSketchInput(BaseModel):
    """Input for create_sketch tool."""

    plane: str = Field(default="XY", description="Plane: 'XY', 'XZ', 'YZ' or face reference")
    body_name: str | None = Field(default=None, description="PartDesign Body to attach to")
    name: str | None = Field(default=None, description="Sketch name")
    doc_name: str | None = Field(default=None, description="Document name")


class AddSketchGeometryInput(BaseModel):
    """Input for add_sketch_geometry tool."""

    sketch_name: str = Field(description="Sketch to add to")
    geometry_type: str = Field(description="Type: 'line', 'circle', 'arc', 'rectangle', 'polygon'")
    doc_name: str | None = Field(default=None, description="Document name")
    start: list[float] | None = Field(default=None, description="[x, y] start point (line)")
    end: list[float] | None = Field(default=None, description="[x, y] end point (line)")
    center: list[float] | None = Field(default=None, description="[x, y] center (circle/arc)")
    radius: float | None = Field(default=None, description="Radius (circle/arc)")
    start_angle: float | None = Field(default=None, description="Start angle in degrees (arc)")
    end_angle: float | None = Field(default=None, description="End angle in degrees (arc)")
    corner1: list[float] | None = Field(default=None, description="[x, y] first corner (rectangle)")
    corner2: list[float] | None = Field(default=None, description="[x, y] second corner (rectangle)")
    points: list[list[float]] | None = Field(default=None, description="[[x, y], ...] points (polygon)")


class AddSketchConstraintInput(BaseModel):
    """Input for add_sketch_constraint tool."""

    sketch_name: str = Field(description="Sketch to constrain")
    constraint_type: str = Field(
        description="Type: 'coincident', 'horizontal', 'vertical', 'parallel', "
        "'perpendicular', 'distance', 'angle', 'radius', 'equal'"
    )
    doc_name: str | None = Field(default=None, description="Document name")
    geometry_index: int | None = Field(default=None, description="Geometry index")
    geometry_index2: int | None = Field(default=None, description="Second geometry index")
    point_index: int | None = Field(default=None, description="Point index on geometry")
    point_index2: int | None = Field(default=None, description="Second point index")
    value: float | None = Field(default=None, description="Constraint value (distance, angle, etc.)")


class PadSketchInput(BaseModel):
    """Input for pad_sketch tool."""

    sketch_name: str = Field(description="Sketch to extrude")
    length: float = Field(description="Extrusion length in mm")
    symmetric: bool = Field(default=False, description="Extrude symmetrically")
    reversed: bool = Field(default=False, description="Reverse direction")
    name: str | None = Field(default=None, description="Feature name")
    doc_name: str | None = Field(default=None, description="Document name")


class PocketSketchInput(BaseModel):
    """Input for pocket_sketch tool."""

    sketch_name: str = Field(description="Sketch defining pocket")
    length: float = Field(description="Pocket depth in mm")
    through_all: bool = Field(default=False, description="Cut through entire part")
    reversed: bool = Field(default=False, description="Reverse direction")
    name: str | None = Field(default=None, description="Feature name")
    doc_name: str | None = Field(default=None, description="Document name")


class DraftLineInput(BaseModel):
    """Input for draft_line tool."""

    start: list[float] = Field(description="[x, y, z] start point")
    end: list[float] = Field(description="[x, y, z] end point")
    name: str | None = Field(default=None, description="Object name")
    doc_name: str | None = Field(default=None, description="Document name")


class DraftRectangleInput(BaseModel):
    """Input for draft_rectangle tool."""

    corner: list[float] = Field(description="[x, y, z] corner point")
    width: float = Field(description="Rectangle width")
    height: float = Field(description="Rectangle height")
    name: str | None = Field(default=None, description="Object name")
    doc_name: str | None = Field(default=None, description="Document name")


class DraftCircleInput(BaseModel):
    """Input for draft_circle tool."""

    center: list[float] = Field(description="[x, y, z] center point")
    radius: float = Field(description="Circle radius")
    name: str | None = Field(default=None, description="Object name")
    doc_name: str | None = Field(default=None, description="Document name")


class GetObjectsInput(BaseModel):
    """Input for get_objects tool."""

    doc_name: str | None = Field(default=None, description="Document name (uses active if omitted)")


class GetObjectInfoInput(BaseModel):
    """Input for get_object_info tool."""

    obj_name: str = Field(description="Object name")
    doc_name: str | None = Field(default=None, description="Document name")


class EditObjectInput(BaseModel):
    """Input for edit_object tool."""

    obj_name: str = Field(description="Object to modify")
    doc_name: str | None = Field(default=None, description="Document name")
    properties: dict[str, Any] = Field(description="Properties to set")


class DeleteObjectInput(BaseModel):
    """Input for delete_object tool."""

    obj_name: str = Field(description="Object to delete")
    doc_name: str | None = Field(default=None, description="Document name")


class ExecuteCodeInput(BaseModel):
    """Input for execute_code tool."""

    code: str = Field(description="Python code to execute in FreeCAD")
    doc_name: str | None = Field(default=None, description="Document context")


class ExportModelInput(BaseModel):
    """Input for export_model tool."""

    file_path: str = Field(description="Output file path")
    format: str | None = Field(
        default=None, description="Format: 'step', 'stl', 'obj', 'iges' (auto-detect if omitted)"
    )
    objects: list[str] | None = Field(default=None, description="Objects to export (all if omitted)")
    doc_name: str | None = Field(default=None, description="Document name")


class ImportModelInput(BaseModel):
    """Input for import_model tool."""

    file_path: str = Field(description="Input file path")
    doc_name: str | None = Field(default=None, description="Target document")


class GetViewInput(BaseModel):
    """Input for get_view tool."""

    view_angle: str = Field(
        default="isometric",
        description="View: 'front', 'back', 'top', 'bottom', 'left', 'right', 'isometric'",
    )
    width: int = Field(default=800, description="Image width in pixels")
    height: int = Field(default=600, description="Image height in pixels")
    doc_name: str | None = Field(default=None, description="Document name")


class SetViewInput(BaseModel):
    """Input for set_view tool."""

    view_angle: str = Field(
        description="View: 'front', 'back', 'top', 'bottom', 'left', 'right', 'isometric'"
    )
    doc_name: str | None = Field(default=None, description="Document name")


class RenderSpinningVideoInput(BaseModel):
    """Input for render_spinning_video tool."""

    model_path: str = Field(description="Path to 3D model file (GLB, OBJ, STL)")
    output_path: str | None = Field(
        default=None, description="Output video path (.mp4). If not specified, saves to cache."
    )
    num_frames: int = Field(default=36, description="Number of frames for full rotation")
    width: int = Field(default=640, description="Frame width in pixels")
    height: int = Field(default=480, description="Frame height in pixels")
    fps: int = Field(default=30, description="Frames per second")


class MeasureDistanceInput(BaseModel):
    """Input for measure_distance tool."""

    obj1_name: str = Field(description="First object")
    obj2_name: str = Field(description="Second object")
    doc_name: str | None = Field(default=None, description="Document name")


class GetBoundingBoxInput(BaseModel):
    """Input for get_bounding_box tool."""

    obj_name: str = Field(description="Object name")
    doc_name: str | None = Field(default=None, description="Document name")


# =============================================================================
# 3D Generation Tool Input Models
# =============================================================================


class Generate3DFromImageInput(BaseModel):
    """Input for generate_3d_from_image tool."""

    image_path: str | None = Field(default=None, description="Path to input image file")
    image_base64: str | None = Field(default=None, description="Base64-encoded image data")
    seed: int = Field(default=42, description="Random seed for generation")
    resolution: str = Field(default="512", description="Output resolution: '512', '1024', '1024_cascade'")
    import_to_freecad: bool = Field(default=True, description="Import generated mesh into FreeCAD")
    doc_name: str | None = Field(default=None, description="FreeCAD document name for import")


class Generate3DFromTextInput(BaseModel):
    """Input for generate_3d_from_text tool."""

    prompt: str = Field(description="Text description of 3D object to generate")
    seed: int | None = Field(default=None, description="Random seed (random if not specified)")
    resolution: str = Field(default="512", description="Output resolution: '512', '1024', '1024_cascade'")
    import_to_freecad: bool = Field(default=True, description="Import generated mesh into FreeCAD")
    doc_name: str | None = Field(default=None, description="FreeCAD document name for import")


class GetTrellisStatusInput(BaseModel):
    """Input for get_trellis_status tool."""

    pass


class LoadTrellisModelInput(BaseModel):
    """Input for load_trellis_model tool."""

    pass


class UnloadTrellisModelInput(BaseModel):
    """Input for unload_trellis_model tool."""

    pass


class ImportMeshInput(BaseModel):
    """Input for import_mesh tool."""

    mesh_path: str = Field(description="Path to mesh file (GLB, OBJ, STL)")
    convert_format: str | None = Field(default=None, description="Convert to format before import: 'obj', 'stl'")
    doc_name: str | None = Field(default=None, description="FreeCAD document name")


# =============================================================================
# Docker Service Tool Input Models
# =============================================================================


class StartDockerServiceInput(BaseModel):
    """Input for start_docker_service tool."""

    service_name: str = Field(
        description="Service to start: 'freecad', 'trellis', 'diffusion', 'inference', 'freecad-headless'"
    )
    with_gui: bool = Field(
        default=False,
        description="Enable GUI for FreeCAD (VNC on ports 3000/5900)"
    )
    timeout: int = Field(
        default=120,
        description="Timeout in seconds to wait for service to start"
    )
    gpus: str | None = Field(
        default=None,
        description="GPU assignment (e.g., '0', '1', '0,1'). Uses service default if not specified."
    )
    rebuild: bool = Field(
        default=False,
        description="Force rebuild of the container image before starting"
    )


class StopDockerServiceInput(BaseModel):
    """Input for stop_docker_service tool."""

    service_name: str = Field(
        description="Service to stop: 'freecad', 'trellis', 'diffusion', 'inference', 'freecad-headless'"
    )
    force: bool = Field(
        default=False,
        description="Force kill the container immediately"
    )


class GetDockerStatusInput(BaseModel):
    """Input for get_docker_status tool."""

    service_name: str | None = Field(
        default=None,
        description="Service to check (all services if omitted)"
    )


class ListDockerServicesInput(BaseModel):
    """Input for list_docker_services tool."""

    pass


class GetDockerLogsInput(BaseModel):
    """Input for get_docker_logs tool."""

    service_name: str = Field(description="Service to get logs from")
    lines: int = Field(default=50, description="Number of log lines to return")


class ScreenshotWebpageInput(BaseModel):
    """Input for screenshot_webpage tool."""

    url: str = Field(description="URL of the webpage to screenshot")
    width: int = Field(default=1280, description="Viewport width in pixels")
    height: int = Field(default=720, description="Viewport height in pixels")
    full_page: bool = Field(default=False, description="Capture full page or just viewport")
    wait_seconds: int = Field(default=2, description="Wait time in seconds before screenshot")


# =============================================================================
# Cloudflare Tunnel Tool Input Models
# =============================================================================


class CreateTunnelInput(BaseModel):
    """Input for create_tunnel tool."""

    name: str = Field(description="Friendly name for this tunnel (e.g., 'gradio', 'freecad-vnc')")
    local_port: int = Field(description="Local port to expose (e.g., 7860 for Gradio)")
    local_host: str = Field(default="localhost", description="Local hostname")
    protocol: str = Field(default="http", description="Protocol: 'http' or 'https'")


class StopTunnelInput(BaseModel):
    """Input for stop_tunnel tool."""

    name: str = Field(description="Name of the tunnel to stop")


class ListTunnelsInput(BaseModel):
    """Input for list_tunnels tool."""

    pass


class CheckTunnelHealthInput(BaseModel):
    """Input for check_tunnel_health tool."""

    name: str | None = Field(default=None, description="Tunnel name to check (checks all if omitted)")
    auto_recreate: bool = Field(default=False, description="Auto-recreate tunnel if health check fails")
    timeout: int = Field(default=10, description="HTTP request timeout in seconds")


class AnalyzeVideoInput(BaseModel):
    """Input for analyze_video tool."""

    video_path: str = Field(description="Path to the video file to analyze")
    question: str = Field(description="Question to ask about the video content")
    num_frames: int = Field(default=8, description="Number of frames to extract (evenly spaced)")
    max_tokens: int = Field(default=1024, description="Maximum response tokens")


# =============================================================================
# Inference Model Tool Input Models
# =============================================================================


class LoadVLMInput(BaseModel):
    """Input for load_vlm tool."""

    pass


class UnloadVLMInput(BaseModel):
    """Input for unload_vlm tool."""

    pass


class LoadSAMInput(BaseModel):
    """Input for load_sam tool."""

    pass


class UnloadSAMInput(BaseModel):
    """Input for unload_sam tool."""

    pass


class GetInferenceStatusInput(BaseModel):
    """Input for get_inference_status tool."""

    pass


class AnalyzeImageInput(BaseModel):
    """Input for analyze_image tool."""

    image_path: str = Field(description="Path to the image file to analyze")
    question: str = Field(description="Question to ask about the image")
    max_tokens: int = Field(default=512, description="Maximum response tokens")


# =============================================================================
# GPU Status Tool Input Models
# =============================================================================


class GetGPUStatusInput(BaseModel):
    """Input for get_gpu_status tool."""

    pass


class GetFullStatusInput(BaseModel):
    """Input for get_full_status tool."""

    pass


# =============================================================================
# Segmentation Pipeline Tool Input Models
# =============================================================================


class SegmentGridInput(BaseModel):
    """Input for segment_grid tool."""

    image_path: str = Field(description="Path to the image file to segment")
    grid_size: int = Field(default=5, description="Number of sample points per dimension (grid_size x grid_size)")
    min_area_percent: float = Field(default=1.0, description="Minimum region area as percentage of image")
    output_dir: str | None = Field(default=None, description="Directory to save output images (default: session cache)")


class SegmentPointsInput(BaseModel):
    """Input for segment_points tool."""

    image_path: str = Field(description="Path to the image file to segment")
    points: list[list[int]] = Field(description="List of [x, y] points to segment at")
    labels: list[str] | None = Field(default=None, description="Optional labels for each point")
    output_dir: str | None = Field(default=None, description="Directory to save output images (default: session cache)")


class SegmentAndAnalyzeInput(BaseModel):
    """Input for segment_and_analyze tool."""

    image_path: str = Field(description="Path to the image file")
    question: str | None = Field(default=None, description="Question for VLM (default: describe the regions)")
    grid_size: int = Field(default=5, description="Grid size for segmentation")
    output_dir: str | None = Field(default=None, description="Directory to save output images (default: session cache)")


class ColorizeRegionInput(BaseModel):
    """Input for colorize_region tool."""

    image_path: str = Field(description="Path to the image file")
    point: list[int] = Field(description="[x, y] point to segment and colorize")
    color: list[int] = Field(default=[255, 0, 0], description="RGB color [r, g, b] for overlay")
    alpha: float = Field(default=0.5, description="Transparency (0-1)")
    output_path: str | None = Field(default=None, description="Output path (default: session cache)")


class IdentifyAndSegmentInput(BaseModel):
    """Input for identify_and_segment tool."""

    image_path: str = Field(description="Path to the image file")
    grid_size: int = Field(default=5, description="Grid size for segmentation")
    output_dir: str | None = Field(default=None, description="Directory to save output images (default: session cache)")


class LaunchGalleryInput(BaseModel):
    """Input for launch_gallery tool."""

    port: int = Field(default=7865, description="Port to run the gallery on")
    create_tunnel: bool = Field(default=True, description="Create a Cloudflare tunnel for public access")


# =============================================================================
# MCP Server Setup
# =============================================================================

# Create the MCP server
server = Server("freecad-mcp")


def format_object_info(obj: ObjectInfo) -> str:
    """Format object info for display."""
    lines = [f"Name: {obj.name}", f"Type: {obj.type}", f"Label: {obj.label}"]
    if obj.placement:
        lines.append(f"Position: ({obj.placement.get('x', 0)}, {obj.placement.get('y', 0)}, {obj.placement.get('z', 0)})")
    if obj.properties:
        lines.append("Properties:")
        for k, v in obj.properties.items():
            lines.append(f"  {k}: {v}")
    return "\n".join(lines)


# =============================================================================
# Tool Definitions
# =============================================================================

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available FreeCAD tools."""
    return [
        # Document Management
        Tool(
            name="create_document",
            description="Create a new FreeCAD document",
            inputSchema=CreateDocumentInput.model_json_schema(),
        ),
        Tool(
            name="open_document",
            description="Open an existing FreeCAD document (.FCStd file)",
            inputSchema=OpenDocumentInput.model_json_schema(),
        ),
        Tool(
            name="save_document",
            description="Save a FreeCAD document to file",
            inputSchema=SaveDocumentInput.model_json_schema(),
        ),
        Tool(
            name="close_document",
            description="Close a FreeCAD document",
            inputSchema=CloseDocumentInput.model_json_schema(),
        ),
        Tool(
            name="list_documents",
            description="List all open FreeCAD documents",
            inputSchema={"type": "object", "properties": {}},
        ),
        # Part Primitives
        Tool(
            name="create_primitive",
            description="Create a Part primitive shape (box, cylinder, sphere, cone, torus)",
            inputSchema=CreatePrimitiveInput.model_json_schema(),
        ),
        Tool(
            name="boolean_operation",
            description="Perform boolean operation (union, cut, intersect) on two objects",
            inputSchema=BooleanOperationInput.model_json_schema(),
        ),
        Tool(
            name="transform_object",
            description="Transform an object (translate, rotate, scale)",
            inputSchema=TransformObjectInput.model_json_schema(),
        ),
        Tool(
            name="fillet_chamfer",
            description="Add fillet or chamfer to object edges",
            inputSchema=FilletChamferInput.model_json_schema(),
        ),
        # Part Design (Parametric)
        Tool(
            name="create_body",
            description="Create a PartDesign Body container for parametric modeling",
            inputSchema=CreateBodyInput.model_json_schema(),
        ),
        Tool(
            name="create_sketch",
            description="Create a parametric sketch on a plane or face",
            inputSchema=CreateSketchInput.model_json_schema(),
        ),
        Tool(
            name="add_sketch_geometry",
            description="Add geometry (line, circle, arc, rectangle, polygon) to a sketch",
            inputSchema=AddSketchGeometryInput.model_json_schema(),
        ),
        Tool(
            name="add_sketch_constraint",
            description="Add constraint to a sketch (coincident, horizontal, vertical, distance, angle, etc.)",
            inputSchema=AddSketchConstraintInput.model_json_schema(),
        ),
        Tool(
            name="pad_sketch",
            description="Extrude (pad) a sketch into a solid",
            inputSchema=PadSketchInput.model_json_schema(),
        ),
        Tool(
            name="pocket_sketch",
            description="Cut a pocket from a sketch",
            inputSchema=PocketSketchInput.model_json_schema(),
        ),
        # Draft (2D)
        Tool(
            name="draft_line",
            description="Create a 2D draft line",
            inputSchema=DraftLineInput.model_json_schema(),
        ),
        Tool(
            name="draft_rectangle",
            description="Create a 2D draft rectangle",
            inputSchema=DraftRectangleInput.model_json_schema(),
        ),
        Tool(
            name="draft_circle",
            description="Create a 2D draft circle",
            inputSchema=DraftCircleInput.model_json_schema(),
        ),
        # Object Operations
        Tool(
            name="get_objects",
            description="List all objects in a document",
            inputSchema=GetObjectsInput.model_json_schema(),
        ),
        Tool(
            name="get_object_info",
            description="Get detailed information about an object",
            inputSchema=GetObjectInfoInput.model_json_schema(),
        ),
        Tool(
            name="edit_object",
            description="Modify object properties",
            inputSchema=EditObjectInput.model_json_schema(),
        ),
        Tool(
            name="delete_object",
            description="Delete an object from the document",
            inputSchema=DeleteObjectInput.model_json_schema(),
        ),
        # Code Execution
        Tool(
            name="execute_code",
            description="Execute Python code in FreeCAD context (advanced users). Use for operations not covered by other tools.",
            inputSchema=ExecuteCodeInput.model_json_schema(),
        ),
        # Import/Export
        Tool(
            name="export_model",
            description="Export model to STEP, STL, OBJ, or IGES format",
            inputSchema=ExportModelInput.model_json_schema(),
        ),
        Tool(
            name="import_model",
            description="Import model from STEP, STL, or other formats",
            inputSchema=ImportModelInput.model_json_schema(),
        ),
        # View/Rendering
        Tool(
            name="get_view",
            description="Capture a viewport screenshot of the current model",
            inputSchema=GetViewInput.model_json_schema(),
        ),
        Tool(
            name="set_view",
            description="Set the camera view angle",
            inputSchema=SetViewInput.model_json_schema(),
        ),
        Tool(
            name="render_spinning_video",
            description="Render a spinning video of a 3D model (GLB/OBJ/STL). Creates an MP4 video showing the model rotating 360 degrees.",
            inputSchema=RenderSpinningVideoInput.model_json_schema(),
        ),
        # Measurement
        Tool(
            name="measure_distance",
            description="Measure distance between two objects",
            inputSchema=MeasureDistanceInput.model_json_schema(),
        ),
        Tool(
            name="get_bounding_box",
            description="Get the bounding box of an object",
            inputSchema=GetBoundingBoxInput.model_json_schema(),
        ),
        # 3D Generation (TRELLIS.2)
        Tool(
            name="generate_3d_from_image",
            description="Generate a 3D mesh from an image using TRELLIS.2. Optionally imports the result into FreeCAD.",
            inputSchema=Generate3DFromImageInput.model_json_schema(),
        ),
        Tool(
            name="generate_3d_from_text",
            description="Generate a 3D mesh from a text description. Uses ComfyUI for image generation and TRELLIS.2 for 3D conversion. Optionally imports the result into FreeCAD.",
            inputSchema=Generate3DFromTextInput.model_json_schema(),
        ),
        Tool(
            name="get_trellis_status",
            description="Get TRELLIS.2 service status including model load state and GPU info",
            inputSchema=GetTrellisStatusInput.model_json_schema(),
        ),
        Tool(
            name="load_trellis_model",
            description="Explicitly load the TRELLIS.2 model into GPU memory",
            inputSchema=LoadTrellisModelInput.model_json_schema(),
        ),
        Tool(
            name="unload_trellis_model",
            description="Unload the TRELLIS.2 model to free GPU memory",
            inputSchema=UnloadTrellisModelInput.model_json_schema(),
        ),
        Tool(
            name="import_mesh",
            description="Import a mesh file (GLB, OBJ, STL) into FreeCAD. GLB files are automatically converted.",
            inputSchema=ImportMeshInput.model_json_schema(),
        ),
        # Docker Service Management
        Tool(
            name="start_docker_service",
            description="Start a Docker service (freecad, trellis, diffusion, inference). Use this to start containers needed for CAD operations.",
            inputSchema=StartDockerServiceInput.model_json_schema(),
        ),
        Tool(
            name="stop_docker_service",
            description="Stop a running Docker service. Use force=true to kill immediately.",
            inputSchema=StopDockerServiceInput.model_json_schema(),
        ),
        Tool(
            name="get_docker_status",
            description="Get status of Docker services (running, health, ports). Omit service_name to see all services.",
            inputSchema=GetDockerStatusInput.model_json_schema(),
        ),
        Tool(
            name="list_docker_services",
            description="List all available Docker services that can be managed, with descriptions.",
            inputSchema=ListDockerServicesInput.model_json_schema(),
        ),
        Tool(
            name="get_docker_logs",
            description="Get recent logs from a Docker service for debugging.",
            inputSchema=GetDockerLogsInput.model_json_schema(),
        ),
        # Utility Tools
        Tool(
            name="screenshot_webpage",
            description="Take a screenshot of a webpage using a headless browser. Useful for verifying web interfaces.",
            inputSchema=ScreenshotWebpageInput.model_json_schema(),
        ),
        # Cloudflare Tunnel Tools
        Tool(
            name="create_tunnel",
            description="Create a Cloudflare Quick Tunnel to expose a local port with a public URL. Useful for sharing Gradio interfaces or web services. Returns a temporary trycloudflare.com URL.",
            inputSchema=CreateTunnelInput.model_json_schema(),
        ),
        Tool(
            name="stop_tunnel",
            description="Stop a running Cloudflare tunnel by name.",
            inputSchema=StopTunnelInput.model_json_schema(),
        ),
        Tool(
            name="list_tunnels",
            description="List all active Cloudflare tunnels with their public URLs.",
            inputSchema=ListTunnelsInput.model_json_schema(),
        ),
        Tool(
            name="check_tunnel_health",
            description="Check if tunnel public URLs are accessible. Pings the URL and verifies HTTP 200 response. Optionally auto-recreates failed tunnels.",
            inputSchema=CheckTunnelHealthInput.model_json_schema(),
        ),
        # Video Analysis Tool
        Tool(
            name="analyze_video",
            description="Analyze a video using the Vision Language Model. Extracts keyframes and creates a frame collage for VLM analysis. Useful for verifying 3D model renders from all angles.",
            inputSchema=AnalyzeVideoInput.model_json_schema(),
        ),
        # Inference Model Tools
        Tool(
            name="load_vlm",
            description="Load the Vision Language Model (Cosmos VLM) into GPU memory. Required before using analyze_image.",
            inputSchema=LoadVLMInput.model_json_schema(),
        ),
        Tool(
            name="unload_vlm",
            description="Unload the Vision Language Model to free GPU memory.",
            inputSchema=UnloadVLMInput.model_json_schema(),
        ),
        Tool(
            name="load_sam",
            description="Load the SAM3 segmentation model into GPU memory.",
            inputSchema=LoadSAMInput.model_json_schema(),
        ),
        Tool(
            name="unload_sam",
            description="Unload the SAM3 model to free GPU memory.",
            inputSchema=UnloadSAMInput.model_json_schema(),
        ),
        Tool(
            name="get_inference_status",
            description="Get status of the inference container including VLM/SAM load state and GPU info.",
            inputSchema=GetInferenceStatusInput.model_json_schema(),
        ),
        Tool(
            name="analyze_image",
            description="Analyze an image using the Vision Language Model. Ask questions about images, describe CAD models, or verify visual content.",
            inputSchema=AnalyzeImageInput.model_json_schema(),
        ),
        # Segmentation Pipeline Tools
        Tool(
            name="segment_grid",
            description="Segment an image into distinct regions using a grid of sample points. Returns colorized image with legend showing each region. Automatically manages inference service.",
            inputSchema=SegmentGridInput.model_json_schema(),
        ),
        Tool(
            name="segment_points",
            description="Segment specific points in an image. Each point gets a distinct color. Useful for highlighting specific features or components in a 3D model image.",
            inputSchema=SegmentPointsInput.model_json_schema(),
        ),
        Tool(
            name="segment_and_analyze",
            description="Segment an image and analyze it with VLM. Colorizes regions and asks VLM to describe what each colored region represents. Combines SAM segmentation with vision-language analysis.",
            inputSchema=SegmentAndAnalyzeInput.model_json_schema(),
        ),
        Tool(
            name="colorize_region",
            description="Segment a region at a point and apply a color overlay. Returns the colorized image.",
            inputSchema=ColorizeRegionInput.model_json_schema(),
        ),
        Tool(
            name="identify_and_segment",
            description="First uses VLM to identify features, then segments them with SAM. Two-pass analysis: initial identification, then segmentation with colorization, then detailed analysis.",
            inputSchema=IdentifyAndSegmentInput.model_json_schema(),
        ),
        # GPU Status Tools
        Tool(
            name="get_gpu_status",
            description="Get GPU status including memory usage for each GPU. Helps decide which GPU to use for services.",
            inputSchema=GetGPUStatusInput.model_json_schema(),
        ),
        Tool(
            name="get_full_status",
            description="Get comprehensive status of all services and GPUs in one call. Shows running services, GPU memory, and service-GPU mapping.",
            inputSchema=GetFullStatusInput.model_json_schema(),
        ),
        # Gallery Interface
        Tool(
            name="launch_gallery",
            description="Launch a Gradio gallery interface to view cached images, 3D models, and VLM analyses. Optionally creates a Cloudflare tunnel for public access.",
            inputSchema=LaunchGalleryInput.model_json_schema(),
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent | ImageContent]:
    """Handle tool calls."""
    client = get_freecad_client()

    try:
        # Document Management
        if name == "create_document":
            inp = CreateDocumentInput(**arguments)
            doc_name = client.create_document(inp.name)
            return [TextContent(type="text", text=f"Created document: {doc_name}")]

        elif name == "open_document":
            inp = OpenDocumentInput(**arguments)
            doc_name = client.open_document(inp.file_path)
            return [TextContent(type="text", text=f"Opened document: {doc_name}")]

        elif name == "save_document":
            inp = SaveDocumentInput(**arguments)
            path = client.save_document(inp.doc_name, inp.file_path)
            return [TextContent(type="text", text=f"Saved document to: {path}")]

        elif name == "close_document":
            inp = CloseDocumentInput(**arguments)
            client.close_document(inp.doc_name)
            return [TextContent(type="text", text="Document closed")]

        elif name == "list_documents":
            docs = client.list_documents()
            if not docs:
                return [TextContent(type="text", text="No documents open")]
            lines = ["Open documents:"]
            for doc in docs:
                status = " (modified)" if doc.modified else ""
                lines.append(f"  - {doc.name}{status}: {len(doc.objects)} objects")
            return [TextContent(type="text", text="\n".join(lines))]

        # Part Primitives
        elif name == "create_primitive":
            inp = CreatePrimitiveInput(**arguments)
            params = {}
            if inp.length is not None:
                params["length"] = inp.length
            if inp.width is not None:
                params["width"] = inp.width
            if inp.height is not None:
                params["height"] = inp.height
            if inp.radius is not None:
                params["radius"] = inp.radius
            if inp.radius1 is not None:
                params["radius1"] = inp.radius1
            if inp.radius2 is not None:
                params["radius2"] = inp.radius2

            obj_name = client.create_primitive(
                inp.primitive_type, inp.name, inp.doc_name, **params
            )
            return [TextContent(type="text", text=f"Created {inp.primitive_type}: {obj_name}")]

        elif name == "boolean_operation":
            inp = BooleanOperationInput(**arguments)
            result = client.boolean_operation(
                inp.operation, inp.obj1_name, inp.obj2_name, inp.result_name, inp.doc_name
            )
            return [TextContent(type="text", text=f"Boolean {inp.operation} result: {result}")]

        elif name == "transform_object":
            inp = TransformObjectInput(**arguments)
            client.transform_object(
                inp.obj_name,
                tuple(inp.translate) if inp.translate else None,
                tuple(inp.rotate) if inp.rotate else None,
                inp.scale,
                inp.doc_name,
            )
            return [TextContent(type="text", text=f"Transformed object: {inp.obj_name}")]

        elif name == "fillet_chamfer":
            inp = FilletChamferInput(**arguments)
            result = client.fillet_chamfer(
                inp.obj_name, inp.operation, inp.edges, inp.radius, inp.doc_name
            )
            return [TextContent(type="text", text=f"{inp.operation.title()} created: {result}")]

        # Part Design
        elif name == "create_body":
            inp = CreateBodyInput(**arguments)
            body_name = client.create_body(inp.name, inp.doc_name)
            return [TextContent(type="text", text=f"Created PartDesign Body: {body_name}")]

        elif name == "create_sketch":
            inp = CreateSketchInput(**arguments)
            sketch_name = client.create_sketch(inp.plane, inp.body_name, inp.name, inp.doc_name)
            return [TextContent(type="text", text=f"Created sketch on {inp.plane}: {sketch_name}")]

        elif name == "add_sketch_geometry":
            inp = AddSketchGeometryInput(**arguments)
            params = {}
            if inp.start is not None:
                params["start"] = tuple(inp.start)
            if inp.end is not None:
                params["end"] = tuple(inp.end)
            if inp.center is not None:
                params["center"] = tuple(inp.center)
            if inp.radius is not None:
                params["radius"] = inp.radius
            if inp.start_angle is not None:
                params["start_angle"] = inp.start_angle
            if inp.end_angle is not None:
                params["end_angle"] = inp.end_angle
            if inp.corner1 is not None:
                params["corner1"] = tuple(inp.corner1)
            if inp.corner2 is not None:
                params["corner2"] = tuple(inp.corner2)
            if inp.points is not None:
                params["points"] = [tuple(p) for p in inp.points]

            geo_idx = client.add_sketch_geometry(
                inp.sketch_name, inp.geometry_type, inp.doc_name, **params
            )
            return [TextContent(type="text", text=f"Added {inp.geometry_type} to sketch, index: {geo_idx}")]

        elif name == "add_sketch_constraint":
            inp = AddSketchConstraintInput(**arguments)
            params = {}
            if inp.geometry_index is not None:
                params["geometry_index"] = inp.geometry_index
            if inp.geometry_index2 is not None:
                params["geometry_index2"] = inp.geometry_index2
            if inp.point_index is not None:
                params["point_index"] = inp.point_index
            if inp.point_index2 is not None:
                params["point_index2"] = inp.point_index2
            if inp.value is not None:
                params["value"] = inp.value

            con_idx = client.add_sketch_constraint(
                inp.sketch_name, inp.constraint_type, inp.doc_name, **params
            )
            return [TextContent(type="text", text=f"Added {inp.constraint_type} constraint, index: {con_idx}")]

        elif name == "pad_sketch":
            inp = PadSketchInput(**arguments)
            feature = client.pad_sketch(
                inp.sketch_name, inp.length, inp.symmetric, inp.reversed, inp.name, inp.doc_name
            )
            return [TextContent(type="text", text=f"Created pad feature: {feature}")]

        elif name == "pocket_sketch":
            inp = PocketSketchInput(**arguments)
            feature = client.pocket_sketch(
                inp.sketch_name, inp.length, inp.through_all, inp.reversed, inp.name, inp.doc_name
            )
            return [TextContent(type="text", text=f"Created pocket feature: {feature}")]

        # Draft
        elif name == "draft_line":
            inp = DraftLineInput(**arguments)
            obj_name = client.draft_line(
                tuple(inp.start), tuple(inp.end), inp.name, inp.doc_name
            )
            return [TextContent(type="text", text=f"Created draft line: {obj_name}")]

        elif name == "draft_rectangle":
            inp = DraftRectangleInput(**arguments)
            obj_name = client.draft_rectangle(
                tuple(inp.corner), inp.width, inp.height, inp.name, inp.doc_name
            )
            return [TextContent(type="text", text=f"Created draft rectangle: {obj_name}")]

        elif name == "draft_circle":
            inp = DraftCircleInput(**arguments)
            obj_name = client.draft_circle(
                tuple(inp.center), inp.radius, inp.name, inp.doc_name
            )
            return [TextContent(type="text", text=f"Created draft circle: {obj_name}")]

        # Object Operations
        elif name == "get_objects":
            inp = GetObjectsInput(**arguments)
            objects = client.get_objects(inp.doc_name)
            if not objects:
                return [TextContent(type="text", text="No objects in document")]
            lines = ["Objects:"]
            for obj in objects:
                lines.append(f"  - {obj.name} ({obj.type})")
            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "get_object_info":
            inp = GetObjectInfoInput(**arguments)
            obj = client.get_object_info(inp.obj_name, inp.doc_name)
            return [TextContent(type="text", text=format_object_info(obj))]

        elif name == "edit_object":
            inp = EditObjectInput(**arguments)
            client.edit_object(inp.obj_name, inp.doc_name, **inp.properties)
            return [TextContent(type="text", text=f"Updated object: {inp.obj_name}")]

        elif name == "delete_object":
            inp = DeleteObjectInput(**arguments)
            client.delete_object(inp.obj_name, inp.doc_name)
            return [TextContent(type="text", text=f"Deleted object: {inp.obj_name}")]

        # Code Execution
        elif name == "execute_code":
            inp = ExecuteCodeInput(**arguments)
            result = client.execute_code(inp.code, inp.doc_name)
            lines = []
            if result.get("success"):
                lines.append("Code executed successfully")
                if result.get("result") is not None:
                    lines.append(f"Result: {result['result']}")
            else:
                lines.append("Code execution failed")
                if result.get("error"):
                    lines.append(f"Error: {result['error']}")
            if result.get("stdout"):
                lines.append(f"Output:\n{result['stdout']}")
            if result.get("stderr"):
                lines.append(f"Stderr:\n{result['stderr']}")
            return [TextContent(type="text", text="\n".join(lines))]

        # Import/Export
        elif name == "export_model":
            inp = ExportModelInput(**arguments)
            path = client.export_model(inp.file_path, inp.format, inp.objects, inp.doc_name)
            return [TextContent(type="text", text=f"Exported to: {path}")]

        elif name == "import_model":
            inp = ImportModelInput(**arguments)
            objects = client.import_model(inp.file_path, inp.doc_name)
            return [TextContent(type="text", text=f"Imported objects: {', '.join(objects)}")]

        # View/Rendering
        elif name == "get_view":
            inp = GetViewInput(**arguments)
            img = client.get_view(inp.view_angle, inp.width, inp.height, inp.doc_name)
            # Convert to base64 PNG
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            img_base64 = base64.standard_b64encode(buf.getvalue()).decode("utf-8")
            return [
                ImageContent(type="image", data=img_base64, mimeType="image/png"),
                TextContent(type="text", text=f"View: {inp.view_angle}, {inp.width}x{inp.height}"),
            ]

        elif name == "set_view":
            inp = SetViewInput(**arguments)
            client.set_view(inp.view_angle, inp.doc_name)
            return [TextContent(type="text", text=f"View set to: {inp.view_angle}")]

        elif name == "render_spinning_video":
            inp = RenderSpinningVideoInput(**arguments)
            from pathlib import Path
            import time as time_module

            # Generate output path if not specified
            if inp.output_path:
                output_path_host = inp.output_path
            else:
                from src.cache_manager import get_output_path
                output_path_host = str(get_output_path(f"spinning_{int(time_module.time())}.mp4", "videos"))

            # Translate paths from host to container
            # Cache: ./cache -> /data/cache
            # Trellis: ./data/trellis/outputs -> /data/trellis/outputs
            project_root = Path(__file__).parent.parent
            cache_host = str(project_root / "cache")
            trellis_host = str(project_root / "data" / "trellis" / "outputs")

            def translate_to_container(path: str) -> str:
                if path.startswith(cache_host):
                    return path.replace(cache_host, "/data/cache")
                if path.startswith(trellis_host):
                    return path.replace(trellis_host, "/data/trellis/outputs")
                return path

            model_path_container = translate_to_container(inp.model_path)
            output_path_container = translate_to_container(output_path_host)

            result = client.render_spinning_video(
                model_path=model_path_container,
                output_path=output_path_container,
                num_frames=inp.num_frames,
                width=inp.width,
                height=inp.height,
                fps=inp.fps,
            )

            if result.get("success"):
                # Translate output path back to host path for display
                output_container = result.get('output_path', '')
                output_display = output_container.replace("/data/cache", cache_host)
                frames = result.get('frames', inp.num_frames)
                duration = result.get('duration_seconds', frames / inp.fps if frames else 0)
                lines = [
                    f"Video rendered successfully!",
                    f"Output: {output_display}",
                    f"Frames: {frames}",
                    f"Duration: {duration:.1f} seconds",
                ]
                return [TextContent(type="text", text="\n".join(lines))]
            else:
                return [TextContent(type="text", text=f"Render failed: {result.get('error')}")]

        # Measurement
        elif name == "measure_distance":
            inp = MeasureDistanceInput(**arguments)
            dist = client.measure_distance(inp.obj1_name, inp.obj2_name, inp.doc_name)
            return [TextContent(type="text", text=f"Distance: {dist:.3f} mm")]

        elif name == "get_bounding_box":
            inp = GetBoundingBoxInput(**arguments)
            bbox = client.get_bounding_box(inp.obj_name, inp.doc_name)
            lines = [
                f"Bounding box of {inp.obj_name}:",
                f"  X: {bbox['xmin']:.3f} to {bbox['xmax']:.3f} mm",
                f"  Y: {bbox['ymin']:.3f} to {bbox['ymax']:.3f} mm",
                f"  Z: {bbox['zmin']:.3f} to {bbox['zmax']:.3f} mm",
                f"  Size: {bbox['xmax']-bbox['xmin']:.3f} x {bbox['ymax']-bbox['ymin']:.3f} x {bbox['zmax']-bbox['zmin']:.3f} mm",
            ]
            return [TextContent(type="text", text="\n".join(lines))]

        # 3D Generation (TRELLIS.2)
        elif name == "generate_3d_from_image":
            inp = Generate3DFromImageInput(**arguments)
            trellis = get_trellis_client()

            # Generate 3D mesh
            result = trellis.generate_3d(
                image=inp.image_path,
                image_base64=inp.image_base64,
                seed=inp.seed,
                resolution=inp.resolution,
            )

            if not result.success:
                return [TextContent(type="text", text=f"3D generation failed: {result.error}")]

            lines = [
                "3D mesh generated successfully:",
                f"  Path: {result.mesh_path}",
                f"  Format: {result.format}",
                f"  Vertices: {result.vertices}",
                f"  Faces: {result.faces}",
                f"  Generation time: {result.generation_time_seconds}s",
            ]

            # Import to FreeCAD if requested
            if inp.import_to_freecad and result.mesh_path:
                # Convert GLB to OBJ for FreeCAD import (using host path)
                conv_result = convert_glb_to_obj(result.mesh_path)
                if conv_result.success and conv_result.obj_path:
                    # Translate host path to FreeCAD container path
                    freecad_path = trellis.translate_host_to_freecad_path(conv_result.obj_path)
                    imported = client.import_model(freecad_path, inp.doc_name)
                    lines.append(f"  Imported to FreeCAD: {', '.join(imported)}")
                else:
                    lines.append(f"  FreeCAD import failed: {conv_result.error}")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "generate_3d_from_text":
            inp = Generate3DFromTextInput(**arguments)
            diffusion = get_diffusion_client()
            trellis = get_trellis_client()

            # Step 1: Generate image from text
            img_result = diffusion.generate_image_for_3d(
                subject=inp.prompt,
                seed=inp.seed,
            )

            if not img_result.success:
                return [TextContent(type="text", text=f"Image generation failed: {img_result.error}")]

            lines = [
                "Step 1: Image generated",
                f"  Prompt: {inp.prompt}",
                f"  Seed: {img_result.seed}",
            ]

            # Step 2: Generate 3D from image
            mesh_result = trellis.generate_3d(
                image_base64=img_result.image_base64,
                seed=inp.seed or img_result.seed,
                resolution=inp.resolution,
            )

            if not mesh_result.success:
                lines.append(f"Step 2: 3D generation failed: {mesh_result.error}")
                return [TextContent(type="text", text="\n".join(lines))]

            lines.extend([
                "Step 2: 3D mesh generated",
                f"  Path: {mesh_result.mesh_path}",
                f"  Vertices: {mesh_result.vertices}",
                f"  Faces: {mesh_result.faces}",
                f"  Generation time: {mesh_result.generation_time_seconds}s",
            ])

            # Step 3: Import to FreeCAD if requested
            if inp.import_to_freecad and mesh_result.mesh_path:
                conv_result = convert_glb_to_obj(mesh_result.mesh_path)
                if conv_result.success and conv_result.obj_path:
                    # Translate host path to FreeCAD container path
                    freecad_path = trellis.translate_host_to_freecad_path(conv_result.obj_path)
                    imported = client.import_model(freecad_path, inp.doc_name)
                    lines.append(f"Step 3: Imported to FreeCAD: {', '.join(imported)}")
                else:
                    lines.append(f"Step 3: FreeCAD import failed: {conv_result.error}")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "get_trellis_status":
            trellis = get_trellis_client()

            if not trellis.ping():
                return [TextContent(type="text", text="TRELLIS service is not running")]

            status = trellis.get_status()
            lines = [
                f"TRELLIS.2 Status:",
                f"  Model: {status.model}",
                f"  Loaded: {status.model_loaded}",
                f"  CUDA: {status.cuda_available}",
            ]

            for device in status.devices:
                lines.append(
                    f"  GPU {device['index']}: {device['name']} - "
                    f"{device['memory_free_gb']:.1f}/{device['memory_total_gb']:.1f} GB free"
                )

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "load_trellis_model":
            trellis = get_trellis_client()
            success = trellis.load_model()
            if success:
                return [TextContent(type="text", text="TRELLIS model loaded successfully")]
            else:
                return [TextContent(type="text", text="Failed to load TRELLIS model")]

        elif name == "unload_trellis_model":
            trellis = get_trellis_client()
            success = trellis.unload_model()
            if success:
                return [TextContent(type="text", text="TRELLIS model unloaded successfully")]
            else:
                return [TextContent(type="text", text="Failed to unload TRELLIS model")]

        elif name == "import_mesh":
            inp = ImportMeshInput(**arguments)
            mesh_path = inp.mesh_path
            trellis = get_trellis_client()

            # Translate container path to host path if needed
            if mesh_path.startswith("/storage/outputs"):
                mesh_path = trellis.translate_container_to_host_path(mesh_path)

            # Convert if needed
            if inp.convert_format or mesh_path.lower().endswith('.glb'):
                target_format = inp.convert_format or 'obj'
                if target_format == 'obj':
                    conv_result = convert_glb_to_obj(mesh_path)
                    if not conv_result.success:
                        return [TextContent(type="text", text=f"Conversion failed: {conv_result.error}")]
                    mesh_path = conv_result.obj_path
                elif target_format == 'stl':
                    conv_result = convert_glb_to_stl(mesh_path)
                    if not conv_result.success:
                        return [TextContent(type="text", text=f"Conversion failed: {conv_result.error}")]
                    mesh_path = conv_result.stl_path

            # Translate host path to FreeCAD container path for import
            freecad_path = trellis.translate_host_to_freecad_path(mesh_path)
            imported = client.import_model(freecad_path, inp.doc_name)
            return [TextContent(type="text", text=f"Imported mesh objects: {', '.join(imported)}")]

        # Docker Service Management
        elif name == "start_docker_service":
            inp = StartDockerServiceInput(**arguments)
            docker = get_docker_client()

            result = docker.start_service(
                name=inp.service_name,
                with_gui=inp.with_gui,
                timeout=inp.timeout,
                gpus=inp.gpus,
                rebuild=inp.rebuild,
            )

            if result.get("success"):
                msg = result.get("message", f"Service {inp.service_name} started")
                if inp.with_gui and inp.service_name == "freecad":
                    msg += "\nVNC GUI available at: http://localhost:3000 (web) or localhost:5900 (VNC client)"
                if result.get("port"):
                    msg += f"\nService port: {result.get('port')}"
                return [TextContent(type="text", text=msg)]
            else:
                return [TextContent(type="text", text=f"Failed to start service: {result.get('error')}")]

        elif name == "stop_docker_service":
            inp = StopDockerServiceInput(**arguments)
            docker = get_docker_client()

            result = docker.stop_service(
                name=inp.service_name,
                force=inp.force,
            )

            if result.get("success"):
                return [TextContent(type="text", text=result.get("message", f"Service {inp.service_name} stopped"))]
            else:
                return [TextContent(type="text", text=f"Failed to stop service: {result.get('error')}")]

        elif name == "get_docker_status":
            inp = GetDockerStatusInput(**arguments)
            docker = get_docker_client()

            statuses = docker.get_service_status(inp.service_name)

            if not statuses:
                return [TextContent(type="text", text="No services found or error getting status")]

            lines = ["Docker Service Status:"]
            for s in statuses:
                status_icon = "[running]" if s.running else "[stopped]"
                lines.append(f"  {s.name}: {status_icon} {s.status}")
                if s.ports:
                    lines.append(f"    Ports: {', '.join(s.ports)}")
                if s.health:
                    lines.append(f"    Health: {s.health}")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "list_docker_services":
            docker = get_docker_client()
            services = docker.list_available_services()

            lines = ["Available Docker Services:"]
            for svc in services:
                profile_note = f" (profile: {svc.profile})" if svc.profile else ""
                gui_note = " [supports GUI]" if svc.supports_gui else ""
                lines.append(f"  {svc.name}: {svc.description}{profile_note}{gui_note}")

            lines.append("\nUse start_docker_service to start a service.")
            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "get_docker_logs":
            inp = GetDockerLogsInput(**arguments)
            docker = get_docker_client()

            result = docker.get_service_logs(
                name=inp.service_name,
                lines=inp.lines,
            )

            if result.get("success"):
                logs = result.get("logs", "No logs available")
                return [TextContent(type="text", text=f"Logs for {inp.service_name}:\n{logs}")]
            else:
                return [TextContent(type="text", text=f"Failed to get logs: {result.get('error')}")]

        elif name == "screenshot_webpage":
            inp = ScreenshotWebpageInput(**arguments)
            try:
                from playwright.async_api import async_playwright
                from src.cache_manager import get_output_path
                import time

                # Generate unique filename in cache
                timestamp = int(time.time() * 1000)
                screenshot_path = str(get_output_path(f"screenshot_{timestamp}.png", "screenshots"))

                async def take_screenshot():
                    async with async_playwright() as p:
                        browser = await p.chromium.launch(headless=True)
                        page = await browser.new_page(viewport={"width": inp.width, "height": inp.height})
                        # Use "load" instead of "networkidle" to avoid timeout on websocket apps
                        await page.goto(inp.url, wait_until="load", timeout=30000)

                        # Wait for additional time to let dynamic content render
                        wait_time = max(inp.wait_seconds, 2)  # Minimum 2 second wait
                        await page.wait_for_timeout(wait_time * 1000)

                        screenshot_bytes = await page.screenshot(full_page=inp.full_page)
                        await browser.close()
                        return screenshot_bytes

                screenshot_bytes = await take_screenshot()

                # Save to file
                with open(screenshot_path, "wb") as f:
                    f.write(screenshot_bytes)

                # Encode as base64
                img_base64 = base64.b64encode(screenshot_bytes).decode("utf-8")

                return [
                    TextContent(type="text", text=f"Screenshot of {inp.url} ({inp.width}x{inp.height})\nSaved to: {screenshot_path}"),
                    ImageContent(type="image", data=img_base64, mimeType="image/png"),
                ]
            except Exception as e:
                return [TextContent(type="text", text=f"Screenshot failed: {str(e)}")]

        # Cloudflare Tunnel Tools
        elif name == "create_tunnel":
            inp = CreateTunnelInput(**arguments)
            tunnel = get_tunnel_client()

            if not tunnel.is_available():
                return [TextContent(
                    type="text",
                    text=f"cloudflared not installed.\n\n{tunnel.get_install_instructions()}"
                )]

            result = tunnel.create_tunnel(
                name=inp.name,
                local_port=inp.local_port,
                local_host=inp.local_host,
                protocol=inp.protocol,
            )

            if result.get("success"):
                return [TextContent(
                    type="text",
                    text=f"Tunnel '{inp.name}' created!\n\nPublic URL: {result.get('public_url')}\nLocal: {result.get('local_url')}"
                )]
            else:
                return [TextContent(type="text", text=f"Failed to create tunnel: {result.get('error')}")]

        elif name == "stop_tunnel":
            inp = StopTunnelInput(**arguments)
            tunnel = get_tunnel_client()
            result = tunnel.stop_tunnel(inp.name)

            if result.get("success"):
                return [TextContent(type="text", text=result.get("message", f"Tunnel '{inp.name}' stopped"))]
            else:
                return [TextContent(type="text", text=f"Failed to stop tunnel: {result.get('error')}")]

        elif name == "list_tunnels":
            tunnel = get_tunnel_client()

            if not tunnel.is_available():
                return [TextContent(type="text", text="cloudflared not installed")]

            tunnels = tunnel.list_tunnels()

            if not tunnels:
                return [TextContent(type="text", text="No active tunnels")]

            lines = ["Active Tunnels:"]
            for t in tunnels:
                status_icon = "[running]" if t.get("status") == "running" else f"[{t.get('status')}]"
                url = t.get("public_url") or "N/A"
                lines.append(f"  {t.get('name')}: {status_icon}")
                lines.append(f"    Local port: {t.get('local_port')}")
                lines.append(f"    Public URL: {url}")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "check_tunnel_health":
            inp = CheckTunnelHealthInput(**arguments)
            tunnel = get_tunnel_client()

            if not tunnel.is_available():
                return [TextContent(type="text", text="cloudflared not installed")]

            import requests

            # Get tunnels to check
            tunnels = tunnel.list_tunnels()
            if inp.name:
                tunnels = [t for t in tunnels if t.get("name") == inp.name]
                if not tunnels:
                    return [TextContent(type="text", text=f"Tunnel '{inp.name}' not found")]

            if not tunnels:
                return [TextContent(type="text", text="No active tunnels to check")]

            results = []
            for t in tunnels:
                name = t.get("name")
                url = t.get("public_url")
                local_port = t.get("local_port")

                if not url:
                    results.append(f"  {name}: No public URL available")
                    continue

                try:
                    response = requests.get(url, timeout=inp.timeout, allow_redirects=True)
                    if response.status_code == 200:
                        results.append(f"  {name}: [healthy] {url} (HTTP 200)")
                    else:
                        results.append(f"  {name}: [unhealthy] {url} (HTTP {response.status_code})")
                        if inp.auto_recreate:
                            # Stop and recreate
                            tunnel.stop_tunnel(name)
                            new_result = tunnel.create_tunnel(name, local_port)
                            if new_result.get("success"):
                                results.append(f"    -> Recreated: {new_result.get('public_url')}")
                            else:
                                results.append(f"    -> Failed to recreate: {new_result.get('error')}")
                except requests.exceptions.Timeout:
                    results.append(f"  {name}: [unhealthy] {url} (timeout)")
                    if inp.auto_recreate:
                        tunnel.stop_tunnel(name)
                        new_result = tunnel.create_tunnel(name, local_port)
                        if new_result.get("success"):
                            results.append(f"    -> Recreated: {new_result.get('public_url')}")
                        else:
                            results.append(f"    -> Failed to recreate: {new_result.get('error')}")
                except requests.exceptions.ConnectionError as e:
                    results.append(f"  {name}: [unhealthy] {url} (connection error)")
                    if inp.auto_recreate:
                        tunnel.stop_tunnel(name)
                        new_result = tunnel.create_tunnel(name, local_port)
                        if new_result.get("success"):
                            results.append(f"    -> Recreated: {new_result.get('public_url')}")
                        else:
                            results.append(f"    -> Failed to recreate: {new_result.get('error')}")
                except Exception as e:
                    results.append(f"  {name}: [error] {str(e)}")

            return [TextContent(type="text", text="Tunnel Health Check:\n" + "\n".join(results))]

        elif name == "analyze_video":
            inp = AnalyzeVideoInput(**arguments)
            try:
                import subprocess
                import tempfile
                from PIL import Image
                from pathlib import Path
                from src.cache_manager import get_output_path

                video_path = Path(inp.video_path)
                if not video_path.exists():
                    return [TextContent(type="text", text=f"Video not found: {inp.video_path}")]

                # Extract frames using ffmpeg
                with tempfile.TemporaryDirectory() as tmpdir:
                    frame_pattern = f"{tmpdir}/frame_%03d.png"

                    # Get video duration and extract evenly spaced frames
                    probe_cmd = [
                        "ffprobe", "-v", "error",
                        "-select_streams", "v:0",
                        "-count_frames",
                        "-show_entries", "stream=nb_read_frames",
                        "-of", "csv=p=0",
                        str(video_path)
                    ]
                    probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
                    total_frames = int(probe_result.stdout.strip()) if probe_result.returncode == 0 else 100

                    # Calculate frame interval
                    interval = max(1, total_frames // inp.num_frames)

                    # Extract frames
                    extract_cmd = [
                        "ffmpeg", "-y",
                        "-i", str(video_path),
                        "-vf", f"select='not(mod(n\\,{interval}))'",
                        "-vsync", "vfr",
                        "-frames:v", str(inp.num_frames),
                        frame_pattern
                    ]
                    subprocess.run(extract_cmd, capture_output=True)

                    # Load extracted frames
                    frames = []
                    for i in range(inp.num_frames):
                        frame_path = f"{tmpdir}/frame_{i+1:03d}.png"
                        if Path(frame_path).exists():
                            frames.append(Image.open(frame_path).copy())

                    if not frames:
                        return [TextContent(type="text", text="Failed to extract frames from video")]

                    # Create a collage of all frames
                    # Determine grid size (e.g., 2x4 for 8 frames)
                    n_frames = len(frames)
                    cols = min(4, n_frames)
                    rows = (n_frames + cols - 1) // cols

                    # Resize frames to fit in collage
                    frame_w, frame_h = frames[0].size
                    max_collage_size = 1600
                    scale = min(1.0, max_collage_size / (cols * frame_w), max_collage_size / (rows * frame_h))
                    thumb_w = int(frame_w * scale)
                    thumb_h = int(frame_h * scale)

                    collage = Image.new("RGB", (cols * thumb_w, rows * thumb_h), (255, 255, 255))

                    for idx, frame in enumerate(frames):
                        row = idx // cols
                        col = idx % cols
                        thumb = frame.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
                        collage.paste(thumb, (col * thumb_w, row * thumb_h))

                    # Save collage for reference
                    collage_path = get_output_path(f"video_collage_{video_path.stem}.png", "screenshots")
                    collage.save(collage_path)

                    # Analyze with VLM
                    inference = get_inference_client()

                    # Enhance prompt to indicate this is a multi-frame view
                    enhanced_prompt = (
                        f"This image shows {n_frames} frames extracted from a video of a 3D model rotating. "
                        f"The frames are arranged in a {rows}x{cols} grid, showing the model from different angles. "
                        f"\n\nQuestion: {inp.question}"
                    )

                    result = inference.analyze_image(collage, enhanced_prompt, inp.max_tokens)

                    response = result.get("response", "No response")
                    thinking = result.get("thinking")

                    lines = [f"Analyzed {n_frames} frames from: {video_path.name}", "", response]
                    if thinking:
                        lines.append(f"\nReasoning: {thinking}")
                    lines.append(f"\nCollage saved: {collage_path}")

                    return [TextContent(type="text", text="\n".join(lines))]

            except Exception as e:
                return [TextContent(type="text", text=f"Video analysis failed: {str(e)}")]

        # Inference Model Tools
        elif name == "load_vlm":
            try:
                inference = get_inference_client()
                success = inference.load_vlm()
                if success:
                    return [TextContent(type="text", text="VLM (Cosmos) loaded successfully on GPU")]
                else:
                    return [TextContent(type="text", text="Failed to load VLM")]
            except Exception as e:
                return [TextContent(type="text", text=f"Error loading VLM: {str(e)}")]

        elif name == "unload_vlm":
            try:
                inference = get_inference_client()
                success = inference.unload_vlm()
                if success:
                    return [TextContent(type="text", text="VLM unloaded, GPU memory freed")]
                else:
                    return [TextContent(type="text", text="Failed to unload VLM")]
            except Exception as e:
                return [TextContent(type="text", text=f"Error unloading VLM: {str(e)}")]

        elif name == "load_sam":
            try:
                inference = get_inference_client()
                success = inference.load_sam()
                if success:
                    return [TextContent(type="text", text="SAM3 loaded successfully on GPU")]
                else:
                    return [TextContent(type="text", text="Failed to load SAM3")]
            except Exception as e:
                return [TextContent(type="text", text=f"Error loading SAM3: {str(e)}")]

        elif name == "unload_sam":
            try:
                inference = get_inference_client()
                success = inference.unload_sam()
                if success:
                    return [TextContent(type="text", text="SAM3 unloaded, GPU memory freed")]
                else:
                    return [TextContent(type="text", text="Failed to unload SAM3")]
            except Exception as e:
                return [TextContent(type="text", text=f"Error unloading SAM3: {str(e)}")]

        elif name == "get_inference_status":
            try:
                inference = get_inference_client()
                if not inference.ping():
                    return [TextContent(type="text", text="Inference container not running or not responding")]

                status = inference.get_status()
                lines = [
                    "Inference Status:",
                    f"  GPUs available: {status.get('gpus', 0)}",
                    f"  VLM loaded: {'Yes' if status.get('vlm_loaded') else 'No'}",
                    f"  SAM loaded: {'Yes' if status.get('sam_loaded') else 'No'}",
                ]
                return [TextContent(type="text", text="\n".join(lines))]
            except Exception as e:
                return [TextContent(type="text", text=f"Error getting inference status: {str(e)}")]

        elif name == "analyze_image":
            inp = AnalyzeImageInput(**arguments)
            try:
                from PIL import Image

                inference = get_inference_client()

                # Load image
                img = Image.open(inp.image_path)

                # Analyze with VLM
                result = inference.analyze_image(img, inp.question, inp.max_tokens)

                response = result.get("response", "No response")
                thinking = result.get("thinking")

                lines = [response]
                if thinking:
                    lines.append(f"\nReasoning: {thinking}")

                return [TextContent(type="text", text="\n".join(lines))]
            except Exception as e:
                return [TextContent(type="text", text=f"Image analysis failed: {str(e)}")]

        # Segmentation Pipeline Tools
        elif name == "segment_grid":
            inp = SegmentGridInput(**arguments)
            try:
                from PIL import Image as PILImage
                from src.cache_manager import get_output_path
                img = PILImage.open(inp.image_path)

                pipeline = SegmentationPipeline(auto_manage_services=True)
                result = pipeline.segment_grid(
                    img,
                    grid_size=inp.grid_size,
                    min_area_percent=inp.min_area_percent,
                )

                # Save outputs to cache
                if inp.output_dir:
                    output_dir = Path(inp.output_dir)
                    output_dir.mkdir(parents=True, exist_ok=True)
                    colorized_path = str(output_dir / "segmented_colorized.png")
                    combined_path = str(output_dir / "segmented_combined.png")
                    legend_path = str(output_dir / "segmented_legend.png")
                else:
                    colorized_path = str(get_output_path("segmented_colorized.png", "segmentation"))
                    combined_path = str(get_output_path("segmented_combined.png", "segmentation"))
                    legend_path = str(get_output_path("segmented_legend.png", "segmentation"))

                result.colorized_image.save(colorized_path)
                result.combined_image.save(combined_path)
                if result.legend_image:
                    result.legend_image.save(legend_path)

                # Format response
                lines = [f"Segmented image into {len(result.regions)} regions"]
                for region in result.regions:
                    color_str = f"RGB({region.color[0]},{region.color[1]},{region.color[2]})"
                    lines.append(f"  {region.label}: {color_str}, {region.area_percent:.1f}% area, confidence={region.confidence:.2f}")

                lines.append(f"\nOutput files:")
                lines.append(f"  Colorized: {colorized_path}")
                lines.append(f"  Combined: {combined_path}")
                if result.legend_image:
                    lines.append(f"  Legend: {legend_path}")

                # Return with image
                with open(combined_path, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode()

                return [
                    TextContent(type="text", text="\n".join(lines)),
                    ImageContent(type="image", data=img_data, mimeType="image/png"),
                ]
            except Exception as e:
                return [TextContent(type="text", text=f"Grid segmentation failed: {str(e)}")]

        elif name == "segment_points":
            inp = SegmentPointsInput(**arguments)
            try:
                from PIL import Image as PILImage
                from src.cache_manager import get_output_path
                img = PILImage.open(inp.image_path)

                # Convert points to tuples
                points = [(p[0], p[1]) for p in inp.points]

                pipeline = SegmentationPipeline(auto_manage_services=True)
                result = pipeline.segment_points(img, points, inp.labels)

                # Save outputs to cache
                if inp.output_dir:
                    output_dir = Path(inp.output_dir)
                    output_dir.mkdir(parents=True, exist_ok=True)
                    colorized_path = str(output_dir / "points_colorized.png")
                    combined_path = str(output_dir / "points_combined.png")
                else:
                    colorized_path = str(get_output_path("points_colorized.png", "segmentation"))
                    combined_path = str(get_output_path("points_combined.png", "segmentation"))

                result.colorized_image.save(colorized_path)
                result.combined_image.save(combined_path)

                # Format response
                lines = [f"Segmented {len(result.regions)} points"]
                for region in result.regions:
                    color_str = f"RGB({region.color[0]},{region.color[1]},{region.color[2]})"
                    lines.append(f"  {region.label}: {color_str}, {region.area_percent:.1f}% area")

                lines.append(f"\nOutput: {combined_path}")

                with open(combined_path, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode()

                return [
                    TextContent(type="text", text="\n".join(lines)),
                    ImageContent(type="image", data=img_data, mimeType="image/png"),
                ]
            except Exception as e:
                return [TextContent(type="text", text=f"Point segmentation failed: {str(e)}")]

        elif name == "segment_and_analyze":
            inp = SegmentAndAnalyzeInput(**arguments)
            try:
                from PIL import Image as PILImage
                from src.cache_manager import get_output_path
                img = PILImage.open(inp.image_path)

                pipeline = SegmentAndAnalyzePipeline(auto_manage_services=True)
                result = pipeline.segment_and_analyze(
                    img,
                    question=inp.question,
                    grid_size=inp.grid_size,
                )

                # Save outputs to cache
                if inp.output_dir:
                    output_dir = Path(inp.output_dir)
                    output_dir.mkdir(parents=True, exist_ok=True)
                    colorized_path = str(output_dir / "analyzed_colorized.png")
                    combined_path = str(output_dir / "analyzed_combined.png")
                else:
                    colorized_path = str(get_output_path("analyzed_colorized.png", "segmentation"))
                    combined_path = str(get_output_path("analyzed_combined.png", "segmentation"))

                seg = result["segmentation"]
                seg.colorized_image.save(colorized_path)
                seg.combined_image.save(combined_path)

                # Format response
                lines = [
                    f"Segmentation: {result['num_regions']} regions identified",
                    "",
                    "Regions:",
                ]
                for region in seg.regions:
                    color_str = f"RGB({region.color[0]},{region.color[1]},{region.color[2]})"
                    lines.append(f"  {region.label}: {color_str}, {region.area_percent:.1f}%")

                lines.extend([
                    "",
                    "VLM Analysis:",
                    result["vlm_response"],
                ])

                if result.get("vlm_thinking"):
                    lines.extend(["", "Reasoning:", result["vlm_thinking"]])

                lines.append(f"\nOutput: {combined_path}")

                with open(combined_path, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode()

                return [
                    TextContent(type="text", text="\n".join(lines)),
                    ImageContent(type="image", data=img_data, mimeType="image/png"),
                ]
            except Exception as e:
                return [TextContent(type="text", text=f"Segment and analyze failed: {str(e)}")]

        elif name == "colorize_region":
            inp = ColorizeRegionInput(**arguments)
            try:
                from PIL import Image as PILImage
                from src.cache_manager import get_output_path
                img = PILImage.open(inp.image_path)

                pipeline = SegmentationPipeline(auto_manage_services=True)
                pipeline._ensure_ready(need_sam=True)
                client = pipeline._get_client()

                # Segment at point
                point = (inp.point[0], inp.point[1])
                seg_result = client.segment_point(img, point, foreground=True)

                # Colorize
                color = tuple(inp.color)
                colorized = pipeline.colorize_mask(img, seg_result["mask"], color, inp.alpha)

                # Save to cache
                if inp.output_path:
                    output_path = inp.output_path
                else:
                    output_path = str(get_output_path("colorized.png", "segmentation"))
                colorized.save(output_path)

                with open(output_path, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode()

                return [
                    TextContent(type="text", text=f"Colorized region at {point}, saved to {output_path}"),
                    ImageContent(type="image", data=img_data, mimeType="image/png"),
                ]
            except Exception as e:
                return [TextContent(type="text", text=f"Colorize region failed: {str(e)}")]

        elif name == "identify_and_segment":
            inp = IdentifyAndSegmentInput(**arguments)
            try:
                from PIL import Image as PILImage
                from src.cache_manager import get_output_path
                img = PILImage.open(inp.image_path)

                pipeline = SegmentAndAnalyzePipeline(auto_manage_services=True)
                result = pipeline.identify_and_segment(img, grid_size=inp.grid_size)

                # Save outputs to cache
                if inp.output_dir:
                    output_dir = Path(inp.output_dir)
                    output_dir.mkdir(parents=True, exist_ok=True)
                    colorized_path = str(output_dir / "identified_colorized.png")
                    combined_path = str(output_dir / "identified_combined.png")
                else:
                    colorized_path = str(get_output_path("identified_colorized.png", "segmentation"))
                    combined_path = str(get_output_path("identified_combined.png", "segmentation"))

                seg = result["segmentation"]
                seg.colorized_image.save(colorized_path)
                seg.combined_image.save(combined_path)

                # Format response
                lines = [
                    "=== Initial Feature Identification ===",
                    result["initial_identification"],
                    "",
                    f"=== Segmentation: {len(seg.regions)} regions ===",
                ]
                for region in seg.regions:
                    color_str = f"RGB({region.color[0]},{region.color[1]},{region.color[2]})"
                    lines.append(f"  {region.label}: {color_str}, {region.area_percent:.1f}%")

                lines.extend([
                    "",
                    "=== Detailed Analysis ===",
                    result["detailed_analysis"],
                ])

                lines.append(f"\nOutput: {combined_path}")

                with open(combined_path, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode()

                return [
                    TextContent(type="text", text="\n".join(lines)),
                    ImageContent(type="image", data=img_data, mimeType="image/png"),
                ]
            except Exception as e:
                return [TextContent(type="text", text=f"Identify and segment failed: {str(e)}")]

        # GPU Status Tools
        elif name == "get_gpu_status":
            docker = get_docker_client()
            gpus = docker.get_gpu_status()

            if not gpus:
                return [TextContent(type="text", text="No GPUs found or nvidia-smi not available")]

            lines = ["GPU Status:"]
            for gpu in gpus:
                used = gpu.get("memory_used_mb", 0)
                total = gpu.get("memory_total_mb", 1)
                free = gpu.get("memory_free_mb", 0)
                util = gpu.get("utilization_percent")
                util_str = f", {util}% utilization" if util is not None else ""

                lines.append(f"  GPU {gpu.get('index')}: {gpu.get('name')}")
                lines.append(f"    Memory: {used} / {total} MB ({free} MB free){util_str}")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "get_full_status":
            docker = get_docker_client()
            status = docker.get_full_status()

            lines = ["=== Full System Status ===\n"]

            # Services
            lines.append("Docker Services:")
            for svc in status.get("services", []):
                icon = "[running]" if svc.get("running") else "[stopped]"
                gpu_note = " (GPU)" if svc.get("uses_gpu") else ""
                lines.append(f"  {svc.get('name')}: {icon}{gpu_note}")
                if svc.get("ports"):
                    lines.append(f"    Ports: {', '.join(svc.get('ports'))}")
                if svc.get("health"):
                    lines.append(f"    Health: {svc.get('health')}")

            # GPUs
            lines.append("\nGPU Status:")
            for gpu in status.get("gpus", []):
                used = gpu.get("memory_used_mb", 0)
                total = gpu.get("memory_total_mb", 1)
                free = gpu.get("memory_free_mb", 0)
                lines.append(f"  GPU {gpu.get('index')}: {gpu.get('name')}")
                lines.append(f"    Memory: {used}/{total} MB ({free} MB free)")

            # Summary
            summary = status.get("summary", {})
            lines.append(f"\nSummary: {summary.get('running_count', 0)}/{summary.get('total_services', 0)} services running")

            # Check tunnels
            try:
                tunnel = get_tunnel_client()
                tunnels = tunnel.list_tunnels()
                if tunnels:
                    lines.append("\nActive Tunnels:")
                    for t in tunnels:
                        if t.get("status") == "running":
                            lines.append(f"  {t.get('name')}: {t.get('public_url')}")
            except Exception:
                pass

            return [TextContent(type="text", text="\n".join(lines))]

        # Gallery Interface
        elif name == "launch_gallery":
            inp = LaunchGalleryInput(**arguments)

            import subprocess
            import time
            from pathlib import Path

            # Start the gallery interface in background
            gallery_cmd = [
                "python3", "-m", "src.gallery_interface",
                "--port", str(inp.port),
                "--host", "0.0.0.0",
            ]

            # Start the process
            process = subprocess.Popen(
                gallery_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(Path(__file__).parent.parent),
            )

            # Wait for it to start
            time.sleep(3)

            lines = [f"Gallery interface started on port {inp.port}"]
            lines.append(f"Local URL: http://localhost:{inp.port}")

            # Create tunnel if requested
            if inp.create_tunnel:
                try:
                    tunnel = get_tunnel_client()
                    result = tunnel.create_tunnel("gallery", inp.port)
                    if result.get("public_url"):
                        lines.append(f"Public URL: {result['public_url']}")
                    else:
                        lines.append("Tunnel creation failed - check cloudflared installation")
                except Exception as e:
                    lines.append(f"Tunnel error: {str(e)}")

            # Get session info
            cache = get_cache_manager()
            status = cache.get_status()
            lines.append(f"\nCache: {status['session_count']} sessions, {status['total_size_mb']:.1f} MB")
            lines.append(f"Current session: {status['current_session']}")

            return [TextContent(type="text", text="\n".join(lines))]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        logger.exception(f"Error in tool {name}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


def main():
    """Run the MCP server."""
    import sys

    # Initialize cache and run cleanup on startup
    cache = init_cache(max_size_mb=1024)  # 1GB limit
    cache_status = cache.get_status()
    logger.info(
        f"Cache initialized: {cache_status['session_count']} sessions, "
        f"{cache_status['total_size_mb']:.1f}MB / {cache_status['max_size_mb']:.0f}MB"
    )

    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(run())


if __name__ == "__main__":
    main()
