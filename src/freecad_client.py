"""XML-RPC client for communicating with FreeCAD container."""

import base64
import io
import logging
import xmlrpc.client
from dataclasses import dataclass, field
from typing import Any

from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class ObjectInfo:
    """Information about a FreeCAD object."""

    name: str
    type: str
    label: str
    properties: dict[str, Any] = field(default_factory=dict)
    placement: dict[str, float] | None = None


@dataclass
class DocumentInfo:
    """Information about a FreeCAD document."""

    name: str
    file_path: str | None
    objects: list[str]
    modified: bool


class FreeCADClient:
    """XML-RPC client for FreeCAD operations."""

    def __init__(self, host: str = "localhost", port: int = 9875):
        """Initialize connection to FreeCAD XML-RPC server.

        Args:
            host: FreeCAD server hostname
            port: XML-RPC port (default 9875)
        """
        self.host = host
        self.port = port
        self._url = f"http://{host}:{port}"
        self._proxy: xmlrpc.client.ServerProxy | None = None

    @property
    def proxy(self) -> xmlrpc.client.ServerProxy:
        """Get or create XML-RPC proxy connection."""
        if self._proxy is None:
            self._proxy = xmlrpc.client.ServerProxy(self._url, allow_none=True)
        return self._proxy

    def ping(self) -> bool:
        """Check if FreeCAD server is responsive."""
        try:
            result = self.proxy.ping()
            return result == "pong"
        except Exception as e:
            logger.warning(f"FreeCAD ping failed: {e}")
            return False

    def reconnect(self) -> bool:
        """Force reconnection to FreeCAD server."""
        self._proxy = None
        return self.ping()

    # =========================================================================
    # Document Management
    # =========================================================================

    def create_document(self, name: str = "Unnamed") -> str:
        """Create a new FreeCAD document.

        Args:
            name: Document name

        Returns:
            Document name
        """
        return self.proxy.create_document(name)

    def open_document(self, file_path: str) -> str:
        """Open an existing FreeCAD document.

        Args:
            file_path: Path to .FCStd file

        Returns:
            Document name
        """
        return self.proxy.open_document(file_path)

    def save_document(self, doc_name: str | None = None, file_path: str | None = None) -> str:
        """Save a FreeCAD document.

        Args:
            doc_name: Document name (uses active if None)
            file_path: Save path (uses existing if None)

        Returns:
            Saved file path
        """
        return self.proxy.save_document(doc_name, file_path)

    def close_document(self, doc_name: str | None = None) -> bool:
        """Close a FreeCAD document.

        Args:
            doc_name: Document name (uses active if None)

        Returns:
            True if closed successfully
        """
        return self.proxy.close_document(doc_name)

    def list_documents(self) -> list[DocumentInfo]:
        """List all open documents.

        Returns:
            List of document info
        """
        docs = self.proxy.list_documents()
        return [
            DocumentInfo(
                name=d["name"],
                file_path=d.get("file_path"),
                objects=d.get("objects", []),
                modified=d.get("modified", False),
            )
            for d in docs
        ]

    def get_active_document(self) -> str | None:
        """Get name of active document."""
        return self.proxy.get_active_document()

    def set_active_document(self, doc_name: str) -> bool:
        """Set active document.

        Args:
            doc_name: Document to activate

        Returns:
            True if successful
        """
        return self.proxy.set_active_document(doc_name)

    # =========================================================================
    # Part Primitives
    # =========================================================================

    def create_primitive(
        self,
        primitive_type: str,
        name: str | None = None,
        doc_name: str | None = None,
        **params: Any,
    ) -> str:
        """Create a Part primitive shape.

        Args:
            primitive_type: One of 'box', 'cylinder', 'sphere', 'cone', 'torus'
            name: Object name (auto-generated if None)
            doc_name: Document name (uses active if None)
            **params: Primitive-specific parameters:
                - box: length, width, height
                - cylinder: radius, height
                - sphere: radius
                - cone: radius1, radius2, height
                - torus: radius1, radius2

        Returns:
            Created object name
        """
        return self.proxy.create_primitive(primitive_type, name, doc_name, params)

    def boolean_operation(
        self,
        operation: str,
        obj1_name: str,
        obj2_name: str,
        result_name: str | None = None,
        doc_name: str | None = None,
    ) -> str:
        """Perform boolean operation on two objects.

        Args:
            operation: One of 'union', 'cut', 'intersect'
            obj1_name: First object name
            obj2_name: Second object name
            result_name: Result object name (auto-generated if None)
            doc_name: Document name (uses active if None)

        Returns:
            Result object name
        """
        return self.proxy.boolean_operation(operation, obj1_name, obj2_name, result_name, doc_name)

    def transform_object(
        self,
        obj_name: str,
        translate: tuple[float, float, float] | None = None,
        rotate: tuple[float, float, float] | None = None,
        scale: float | tuple[float, float, float] | None = None,
        doc_name: str | None = None,
    ) -> bool:
        """Transform an object (move, rotate, scale).

        Args:
            obj_name: Object to transform
            translate: (x, y, z) translation in mm
            rotate: (roll, pitch, yaw) rotation in degrees
            scale: Uniform scale factor or (x, y, z) scale factors
            doc_name: Document name (uses active if None)

        Returns:
            True if successful
        """
        return self.proxy.transform_object(
            obj_name,
            list(translate) if translate else None,
            list(rotate) if rotate else None,
            scale if isinstance(scale, (int, float)) else list(scale) if scale else None,
            doc_name,
        )

    def fillet_chamfer(
        self,
        obj_name: str,
        operation: str,
        edges: list[int] | str,
        radius: float,
        doc_name: str | None = None,
    ) -> str:
        """Add fillet or chamfer to edges.

        Args:
            obj_name: Object to modify
            operation: 'fillet' or 'chamfer'
            edges: Edge indices or 'all'
            radius: Fillet/chamfer radius in mm
            doc_name: Document name (uses active if None)

        Returns:
            Result object name
        """
        return self.proxy.fillet_chamfer(obj_name, operation, edges, radius, doc_name)

    # =========================================================================
    # Part Design (Parametric)
    # =========================================================================

    def create_body(self, name: str | None = None, doc_name: str | None = None) -> str:
        """Create a PartDesign Body container.

        Args:
            name: Body name
            doc_name: Document name (uses active if None)

        Returns:
            Created body name
        """
        return self.proxy.create_body(name, doc_name)

    def create_sketch(
        self,
        plane: str = "XY",
        body_name: str | None = None,
        name: str | None = None,
        doc_name: str | None = None,
    ) -> str:
        """Create a parametric sketch on a plane or face.

        Args:
            plane: 'XY', 'XZ', 'YZ' or face reference
            body_name: PartDesign Body to attach to
            name: Sketch name
            doc_name: Document name (uses active if None)

        Returns:
            Created sketch name
        """
        return self.proxy.create_sketch(plane, body_name, name, doc_name)

    def add_sketch_geometry(
        self,
        sketch_name: str,
        geometry_type: str,
        doc_name: str | None = None,
        **params: Any,
    ) -> int:
        """Add geometry to a sketch.

        Args:
            sketch_name: Sketch to add to
            geometry_type: 'line', 'circle', 'arc', 'rectangle', 'polygon'
            doc_name: Document name (uses active if None)
            **params: Geometry-specific parameters:
                - line: start=(x,y), end=(x,y)
                - circle: center=(x,y), radius=r
                - arc: center=(x,y), radius=r, start_angle=a1, end_angle=a2
                - rectangle: corner1=(x,y), corner2=(x,y)
                - polygon: points=[(x1,y1), (x2,y2), ...]

        Returns:
            Geometry index in sketch
        """
        return self.proxy.add_sketch_geometry(sketch_name, geometry_type, doc_name, params)

    def add_sketch_constraint(
        self,
        sketch_name: str,
        constraint_type: str,
        doc_name: str | None = None,
        **params: Any,
    ) -> int:
        """Add constraint to a sketch.

        Args:
            sketch_name: Sketch to constrain
            constraint_type: 'coincident', 'horizontal', 'vertical', 'parallel',
                           'perpendicular', 'distance', 'angle', 'radius', 'equal'
            doc_name: Document name (uses active if None)
            **params: Constraint-specific parameters

        Returns:
            Constraint index
        """
        return self.proxy.add_sketch_constraint(sketch_name, constraint_type, doc_name, params)

    def close_sketch(self, sketch_name: str, doc_name: str | None = None) -> bool:
        """Close sketch editing mode.

        Args:
            sketch_name: Sketch to close
            doc_name: Document name

        Returns:
            True if successful
        """
        return self.proxy.close_sketch(sketch_name, doc_name)

    def pad_sketch(
        self,
        sketch_name: str,
        length: float,
        symmetric: bool = False,
        reversed: bool = False,
        name: str | None = None,
        doc_name: str | None = None,
    ) -> str:
        """Extrude (pad) a sketch into solid.

        Args:
            sketch_name: Sketch to extrude
            length: Extrusion length in mm
            symmetric: Extrude symmetrically
            reversed: Reverse direction
            name: Feature name
            doc_name: Document name (uses active if None)

        Returns:
            Created feature name
        """
        return self.proxy.pad_sketch(sketch_name, length, symmetric, reversed, name, doc_name)

    def pocket_sketch(
        self,
        sketch_name: str,
        length: float,
        through_all: bool = False,
        reversed: bool = False,
        name: str | None = None,
        doc_name: str | None = None,
    ) -> str:
        """Cut a pocket from a sketch.

        Args:
            sketch_name: Sketch defining pocket
            length: Pocket depth in mm
            through_all: Cut through entire part
            reversed: Reverse direction
            name: Feature name
            doc_name: Document name (uses active if None)

        Returns:
            Created feature name
        """
        return self.proxy.pocket_sketch(
            sketch_name, length, through_all, reversed, name, doc_name
        )

    def revolve_sketch(
        self,
        sketch_name: str,
        angle: float = 360.0,
        axis: str = "X",
        name: str | None = None,
        doc_name: str | None = None,
    ) -> str:
        """Revolve a sketch around an axis.

        Args:
            sketch_name: Sketch to revolve
            angle: Rotation angle in degrees (default 360)
            axis: Rotation axis ('X', 'Y', 'Z' or axis reference)
            name: Feature name
            doc_name: Document name

        Returns:
            Created feature name
        """
        return self.proxy.revolve_sketch(sketch_name, angle, axis, name, doc_name)

    # =========================================================================
    # Draft (2D Drawing)
    # =========================================================================

    def draft_line(
        self,
        start: tuple[float, float, float],
        end: tuple[float, float, float],
        name: str | None = None,
        doc_name: str | None = None,
    ) -> str:
        """Create a 2D draft line.

        Args:
            start: (x, y, z) start point
            end: (x, y, z) end point
            name: Object name
            doc_name: Document name

        Returns:
            Created object name
        """
        return self.proxy.draft_line(list(start), list(end), name, doc_name)

    def draft_rectangle(
        self,
        corner: tuple[float, float, float],
        width: float,
        height: float,
        name: str | None = None,
        doc_name: str | None = None,
    ) -> str:
        """Create a 2D draft rectangle.

        Args:
            corner: (x, y, z) corner point
            width: Rectangle width
            height: Rectangle height
            name: Object name
            doc_name: Document name

        Returns:
            Created object name
        """
        return self.proxy.draft_rectangle(list(corner), width, height, name, doc_name)

    def draft_circle(
        self,
        center: tuple[float, float, float],
        radius: float,
        name: str | None = None,
        doc_name: str | None = None,
    ) -> str:
        """Create a 2D draft circle.

        Args:
            center: (x, y, z) center point
            radius: Circle radius
            name: Object name
            doc_name: Document name

        Returns:
            Created object name
        """
        return self.proxy.draft_circle(list(center), radius, name, doc_name)

    def draft_text(
        self,
        text: str,
        position: tuple[float, float, float],
        size: float = 10.0,
        name: str | None = None,
        doc_name: str | None = None,
    ) -> str:
        """Create text annotation.

        Args:
            text: Text content
            position: (x, y, z) position
            size: Font size
            name: Object name
            doc_name: Document name

        Returns:
            Created object name
        """
        return self.proxy.draft_text(text, list(position), size, name, doc_name)

    # =========================================================================
    # General Object Operations
    # =========================================================================

    def get_objects(self, doc_name: str | None = None) -> list[ObjectInfo]:
        """List all objects in document.

        Args:
            doc_name: Document name (uses active if None)

        Returns:
            List of object info
        """
        objects = self.proxy.get_objects(doc_name)
        return [
            ObjectInfo(
                name=o["name"],
                type=o["type"],
                label=o.get("label", o["name"]),
                properties=o.get("properties", {}),
                placement=o.get("placement"),
            )
            for o in objects
        ]

    def get_object_info(self, obj_name: str, doc_name: str | None = None) -> ObjectInfo:
        """Get detailed information about an object.

        Args:
            obj_name: Object name
            doc_name: Document name (uses active if None)

        Returns:
            Detailed object info
        """
        o = self.proxy.get_object_info(obj_name, doc_name)
        return ObjectInfo(
            name=o["name"],
            type=o["type"],
            label=o.get("label", o["name"]),
            properties=o.get("properties", {}),
            placement=o.get("placement"),
        )

    def edit_object(
        self, obj_name: str, doc_name: str | None = None, **properties: Any
    ) -> bool:
        """Modify object properties.

        Args:
            obj_name: Object to modify
            doc_name: Document name (uses active if None)
            **properties: Properties to set

        Returns:
            True if successful
        """
        return self.proxy.edit_object(obj_name, doc_name, properties)

    def delete_object(self, obj_name: str, doc_name: str | None = None) -> bool:
        """Delete an object.

        Args:
            obj_name: Object to delete
            doc_name: Document name (uses active if None)

        Returns:
            True if deleted
        """
        return self.proxy.delete_object(obj_name, doc_name)

    def copy_object(
        self,
        obj_name: str,
        new_name: str | None = None,
        doc_name: str | None = None,
    ) -> str:
        """Copy an object.

        Args:
            obj_name: Object to copy
            new_name: Name for copy
            doc_name: Document name

        Returns:
            New object name
        """
        return self.proxy.copy_object(obj_name, new_name, doc_name)

    # =========================================================================
    # Code Execution (Sandboxed)
    # =========================================================================

    def execute_code(self, code: str, doc_name: str | None = None) -> dict[str, Any]:
        """Execute Python code in FreeCAD context.

        WARNING: This executes arbitrary code. Use with caution.

        Args:
            code: Python code to execute
            doc_name: Document context (uses active if None)

        Returns:
            Dict with 'success', 'result', 'error', 'stdout', 'stderr'
        """
        return self.proxy.execute_code(code, doc_name)

    # =========================================================================
    # Import/Export
    # =========================================================================

    def export_model(
        self,
        file_path: str,
        format: str | None = None,
        objects: list[str] | None = None,
        doc_name: str | None = None,
    ) -> str:
        """Export model to file.

        Args:
            file_path: Output file path
            format: 'step', 'stl', 'obj', 'iges', 'brep' (auto-detect from extension if None)
            objects: Objects to export (all if None)
            doc_name: Document name (uses active if None)

        Returns:
            Exported file path
        """
        return self.proxy.export_model(file_path, format, objects, doc_name)

    def import_model(
        self, file_path: str, doc_name: str | None = None
    ) -> list[str]:
        """Import model from file.

        Args:
            file_path: Input file path
            doc_name: Target document (uses active if None)

        Returns:
            List of imported object names
        """
        return self.proxy.import_model(file_path, doc_name)

    def import_mesh(
        self, file_path: str, doc_name: str | None = None
    ) -> list[str]:
        """Import mesh file (OBJ, STL, PLY) into document.

        Args:
            file_path: Path to mesh file
            doc_name: Target document (uses active if None)

        Returns:
            List of imported object names
        """
        return self.proxy.import_mesh(file_path, doc_name)

    # =========================================================================
    # View and Rendering
    # =========================================================================

    def get_view(
        self,
        view_angle: str = "isometric",
        width: int = 800,
        height: int = 600,
        doc_name: str | None = None,
    ) -> Image.Image:
        """Capture viewport screenshot.

        Args:
            view_angle: 'front', 'back', 'top', 'bottom', 'left', 'right', 'isometric'
            width: Image width in pixels
            height: Image height in pixels
            doc_name: Document name (uses active if None)

        Returns:
            PIL Image of the viewport
        """
        result = self.proxy.get_view(view_angle, width, height, doc_name)
        # Result is base64-encoded PNG
        img_data = base64.b64decode(result)
        return Image.open(io.BytesIO(img_data))

    def set_view(self, view_angle: str, doc_name: str | None = None) -> bool:
        """Set camera view angle.

        Args:
            view_angle: 'front', 'back', 'top', 'bottom', 'left', 'right', 'isometric'
            doc_name: Document name (uses active if None)

        Returns:
            True if successful
        """
        return self.proxy.set_view(view_angle, doc_name)

    def fit_view(self, doc_name: str | None = None) -> bool:
        """Fit view to show all objects.

        Args:
            doc_name: Document name

        Returns:
            True if successful
        """
        return self.proxy.fit_view(doc_name)

    def render_scene(
        self,
        width: int = 1920,
        height: int = 1080,
        renderer: str = "povray",
        doc_name: str | None = None,
    ) -> Image.Image | None:
        """Render high-quality image (requires Render workbench).

        Args:
            width: Image width
            height: Image height
            renderer: 'povray', 'luxcore', 'cycles'
            doc_name: Document name

        Returns:
            Rendered image or None if renderer unavailable
        """
        result = self.proxy.render_scene(width, height, renderer, doc_name)
        if result is None:
            return None
        img_data = base64.b64decode(result)
        return Image.open(io.BytesIO(img_data))

    # =========================================================================
    # Measurement
    # =========================================================================

    def measure_distance(
        self,
        obj1_name: str,
        obj2_name: str,
        doc_name: str | None = None,
    ) -> float:
        """Measure distance between two objects.

        Args:
            obj1_name: First object
            obj2_name: Second object
            doc_name: Document name

        Returns:
            Distance in mm
        """
        return self.proxy.measure_distance(obj1_name, obj2_name, doc_name)

    def get_bounding_box(
        self, obj_name: str, doc_name: str | None = None
    ) -> dict[str, float]:
        """Get object bounding box.

        Args:
            obj_name: Object name
            doc_name: Document name

        Returns:
            Dict with xmin, xmax, ymin, ymax, zmin, zmax
        """
        return self.proxy.get_bounding_box(obj_name, doc_name)

    def get_volume(self, obj_name: str, doc_name: str | None = None) -> float:
        """Get object volume.

        Args:
            obj_name: Object name
            doc_name: Document name

        Returns:
            Volume in mm^3
        """
        return self.proxy.get_volume(obj_name, doc_name)

    def get_surface_area(self, obj_name: str, doc_name: str | None = None) -> float:
        """Get object surface area.

        Args:
            obj_name: Object name
            doc_name: Document name

        Returns:
            Surface area in mm^2
        """
        return self.proxy.get_surface_area(obj_name, doc_name)

    def render_spinning_video(
        self,
        model_path: str,
        output_path: str,
        num_frames: int = 60,
        width: int = 640,
        height: int = 480,
        fps: int = 30,
    ) -> dict:
        """Render a spinning video of a 3D model.

        Args:
            model_path: Path to 3D model file (GLB, OBJ, STL)
            output_path: Output video path (.mp4)
            num_frames: Number of frames for full rotation
            width: Frame width in pixels
            height: Frame height in pixels
            fps: Frames per second

        Returns:
            Dict with success status, output_path, frames, duration_seconds
        """
        return self.proxy.render_spinning_video(
            model_path, output_path, num_frames, width, height, fps
        )
