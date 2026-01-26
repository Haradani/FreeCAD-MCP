#!/usr/bin/env python3
"""XML-RPC server for FreeCAD remote control.

This script runs inside the FreeCAD container and exposes FreeCAD
functionality via XML-RPC for the MCP server to consume.
"""

import base64
import io
import logging
import os
import sys
import tempfile
import traceback
from typing import Any
from xmlrpc.server import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler

# FreeCAD imports (available when running in FreeCAD context)
try:
    import FreeCAD
    import FreeCADGui
    import Part
    import Draft

    FREECAD_AVAILABLE = True
except ImportError:
    FREECAD_AVAILABLE = False
    print("Warning: FreeCAD not available, running in mock mode")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class RequestHandler(SimpleXMLRPCRequestHandler):
    """Custom request handler allowing CORS and larger requests."""

    rpc_paths = ("/", "/RPC2")


class FreeCADRPCServer:
    """XML-RPC server exposing FreeCAD operations."""

    def __init__(self):
        """Initialize the RPC server."""
        self.temp_dir = tempfile.mkdtemp(prefix="freecad_mcp_")
        logger.info(f"Temp directory: {self.temp_dir}")

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def ping(self) -> str:
        """Health check."""
        return "pong"

    def get_version(self) -> dict[str, str]:
        """Get FreeCAD version info."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")
        return {
            "version": FreeCAD.Version()[0] + "." + FreeCAD.Version()[1],
            "build": FreeCAD.Version()[2],
        }

    def _get_doc(self, doc_name: str | None = None) -> Any:
        """Get document by name or active document."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        if doc_name:
            if doc_name not in FreeCAD.listDocuments():
                raise ValueError(f"Document not found: {doc_name}")
            return FreeCAD.getDocument(doc_name)

        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise ValueError("No active document")
        return doc

    def _get_obj(self, obj_name: str, doc_name: str | None = None) -> Any:
        """Get object by name from document."""
        doc = self._get_doc(doc_name)
        obj = doc.getObject(obj_name)
        if obj is None:
            raise ValueError(f"Object not found: {obj_name}")
        return obj

    # =========================================================================
    # Document Management
    # =========================================================================

    def create_document(self, name: str = "Unnamed") -> str:
        """Create a new document."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        doc = FreeCAD.newDocument(name)
        return doc.Name

    def open_document(self, file_path: str) -> str:
        """Open an existing document."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        doc = FreeCAD.openDocument(file_path)
        return doc.Name

    def save_document(self, doc_name: str | None = None, file_path: str | None = None) -> str:
        """Save a document.

        Args:
            doc_name: Document name (uses active document if None)
            file_path: Path to save to (uses existing path or generates one if None)

        Returns:
            Path to the saved file

        Raises:
            RuntimeError: If save fails or file not created
        """
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        doc = self._get_doc(doc_name)

        try:
            if file_path:
                # Ensure parent directory exists
                parent_dir = os.path.dirname(os.path.abspath(file_path))
                os.makedirs(parent_dir, exist_ok=True)
                logger.info(f"Saving document to: {file_path}")
                doc.saveAs(file_path)
            else:
                if not doc.FileName:
                    # Generate default path in temp directory
                    os.makedirs(self.temp_dir, exist_ok=True)
                    file_path = os.path.join(self.temp_dir, f"{doc.Name}.FCStd")
                    logger.info(f"Saving document to generated path: {file_path}")
                    doc.saveAs(file_path)
                else:
                    logger.info(f"Saving document to existing path: {doc.FileName}")
                    doc.save()

            # Verify save succeeded
            final_path = doc.FileName
            if not final_path:
                raise RuntimeError("Save failed: doc.FileName not set after save")

            if not os.path.exists(final_path):
                raise RuntimeError(f"Save failed: file not created at {final_path}")

            logger.info(f"Document saved successfully: {final_path}")
            return final_path

        except Exception as e:
            logger.error(f"Failed to save document: {e}")
            raise

    def close_document(self, doc_name: str | None = None) -> bool:
        """Close a document."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        doc = self._get_doc(doc_name)
        FreeCAD.closeDocument(doc.Name)
        return True

    def list_documents(self) -> list[dict]:
        """List all open documents."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        docs = []
        for name in FreeCAD.listDocuments():
            doc = FreeCAD.getDocument(name)
            docs.append({
                "name": doc.Name,
                "file_path": doc.FileName or None,
                "objects": [obj.Name for obj in doc.Objects],
                "modified": doc.Touched,
            })
        return docs

    def get_active_document(self) -> str | None:
        """Get name of active document."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        doc = FreeCAD.ActiveDocument
        return doc.Name if doc else None

    def set_active_document(self, doc_name: str) -> bool:
        """Set active document."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        FreeCAD.setActiveDocument(doc_name)
        return True

    # =========================================================================
    # Part Primitives
    # =========================================================================

    def create_primitive(
        self,
        primitive_type: str,
        name: str | None,
        doc_name: str | None,
        params: dict,
    ) -> str:
        """Create a Part primitive."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        doc = self._get_doc(doc_name)
        primitive_type = primitive_type.lower()

        if primitive_type == "box":
            obj = doc.addObject("Part::Box", name or "Box")
            obj.Length = params.get("length", 10.0)
            obj.Width = params.get("width", 10.0)
            obj.Height = params.get("height", 10.0)

        elif primitive_type == "cylinder":
            obj = doc.addObject("Part::Cylinder", name or "Cylinder")
            obj.Radius = params.get("radius", 5.0)
            obj.Height = params.get("height", 10.0)

        elif primitive_type == "sphere":
            obj = doc.addObject("Part::Sphere", name or "Sphere")
            obj.Radius = params.get("radius", 5.0)

        elif primitive_type == "cone":
            obj = doc.addObject("Part::Cone", name or "Cone")
            obj.Radius1 = params.get("radius1", 5.0)
            obj.Radius2 = params.get("radius2", 0.0)
            obj.Height = params.get("height", 10.0)

        elif primitive_type == "torus":
            obj = doc.addObject("Part::Torus", name or "Torus")
            obj.Radius1 = params.get("radius1", 10.0)
            obj.Radius2 = params.get("radius2", 2.0)

        else:
            raise ValueError(f"Unknown primitive type: {primitive_type}")

        doc.recompute()
        return obj.Name

    def boolean_operation(
        self,
        operation: str,
        obj1_name: str,
        obj2_name: str,
        result_name: str | None,
        doc_name: str | None,
    ) -> str:
        """Perform boolean operation."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        doc = self._get_doc(doc_name)
        obj1 = self._get_obj(obj1_name, doc_name)
        obj2 = self._get_obj(obj2_name, doc_name)

        operation = operation.lower()

        if operation == "union":
            result = doc.addObject("Part::Fuse", result_name or "Fusion")
            result.Base = obj1
            result.Tool = obj2

        elif operation == "cut":
            result = doc.addObject("Part::Cut", result_name or "Cut")
            result.Base = obj1
            result.Tool = obj2

        elif operation == "intersect":
            result = doc.addObject("Part::Common", result_name or "Common")
            result.Base = obj1
            result.Tool = obj2

        else:
            raise ValueError(f"Unknown operation: {operation}")

        doc.recompute()
        return result.Name

    def transform_object(
        self,
        obj_name: str,
        translate: list[float] | None,
        rotate: list[float] | None,
        scale: float | list[float] | None,
        doc_name: str | None,
    ) -> bool:
        """Transform an object."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        obj = self._get_obj(obj_name, doc_name)

        if translate:
            placement = obj.Placement
            placement.Base.x += translate[0]
            placement.Base.y += translate[1]
            placement.Base.z += translate[2]
            obj.Placement = placement

        if rotate:
            import FreeCAD
            placement = obj.Placement
            # Apply rotation (roll, pitch, yaw in degrees)
            from FreeCAD import Rotation
            r = Rotation(rotate[2], rotate[1], rotate[0])  # yaw, pitch, roll
            placement.Rotation = placement.Rotation.multiply(r)
            obj.Placement = placement

        if scale is not None:
            # FreeCAD doesn't have native scaling, use matrix transform
            if isinstance(scale, (int, float)):
                scale = [scale, scale, scale]
            # This requires creating a scaled copy
            logger.warning("Scale operation requires shape copy, not fully supported")

        self._get_doc(doc_name).recompute()
        return True

    def fillet_chamfer(
        self,
        obj_name: str,
        operation: str,
        edges: list[int] | str,
        radius: float,
        doc_name: str | None,
    ) -> str:
        """Add fillet or chamfer to edges."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        doc = self._get_doc(doc_name)
        obj = self._get_obj(obj_name, doc_name)

        # Get edges
        if edges == "all":
            edge_refs = [(obj, f"Edge{i+1}") for i in range(len(obj.Shape.Edges))]
        else:
            edge_refs = [(obj, f"Edge{i}") for i in edges]

        operation = operation.lower()

        if operation == "fillet":
            result = doc.addObject("Part::Fillet", f"Fillet_{obj_name}")
            result.Base = obj
            result.Edges = edge_refs
            result.Radius = radius

        elif operation == "chamfer":
            result = doc.addObject("Part::Chamfer", f"Chamfer_{obj_name}")
            result.Base = obj
            result.Edges = edge_refs
            result.ChamferSize = radius

        else:
            raise ValueError(f"Unknown operation: {operation}")

        doc.recompute()
        return result.Name

    # =========================================================================
    # Part Design (Parametric)
    # =========================================================================

    def create_body(self, name: str | None, doc_name: str | None) -> str:
        """Create a PartDesign Body."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        doc = self._get_doc(doc_name)
        body = doc.addObject("PartDesign::Body", name or "Body")
        return body.Name

    def create_sketch(
        self,
        plane: str,
        body_name: str | None,
        name: str | None,
        doc_name: str | None,
    ) -> str:
        """Create a sketch on a plane."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        doc = self._get_doc(doc_name)

        # Create sketch
        sketch = doc.addObject("Sketcher::SketchObject", name or "Sketch")

        # Set support plane
        plane = plane.upper()
        if plane == "XY":
            sketch.Support = (doc.getObject("XY_Plane"), [""])
            sketch.MapMode = "FlatFace"
        elif plane == "XZ":
            sketch.Support = (doc.getObject("XZ_Plane"), [""])
            sketch.MapMode = "FlatFace"
        elif plane == "YZ":
            sketch.Support = (doc.getObject("YZ_Plane"), [""])
            sketch.MapMode = "FlatFace"
        else:
            # Assume it's a face reference
            logger.warning(f"Custom plane support not fully implemented: {plane}")

        # Attach to body if specified
        if body_name:
            body = self._get_obj(body_name, doc_name)
            body.addObject(sketch)

        doc.recompute()
        return sketch.Name

    def add_sketch_geometry(
        self,
        sketch_name: str,
        geometry_type: str,
        doc_name: str | None,
        params: dict,
    ) -> int:
        """Add geometry to a sketch."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        sketch = self._get_obj(sketch_name, doc_name)
        geometry_type = geometry_type.lower()

        if geometry_type == "line":
            start = params.get("start", (0, 0))
            end = params.get("end", (10, 0))
            import Part
            line = Part.LineSegment(
                FreeCAD.Vector(start[0], start[1], 0),
                FreeCAD.Vector(end[0], end[1], 0),
            )
            idx = sketch.addGeometry(line)

        elif geometry_type == "circle":
            center = params.get("center", (0, 0))
            radius = params.get("radius", 5)
            import Part
            circle = Part.Circle(
                FreeCAD.Vector(center[0], center[1], 0),
                FreeCAD.Vector(0, 0, 1),
                radius,
            )
            idx = sketch.addGeometry(circle)

        elif geometry_type == "arc":
            center = params.get("center", (0, 0))
            radius = params.get("radius", 5)
            start_angle = params.get("start_angle", 0)
            end_angle = params.get("end_angle", 90)
            import Part
            import math
            arc = Part.ArcOfCircle(
                Part.Circle(
                    FreeCAD.Vector(center[0], center[1], 0),
                    FreeCAD.Vector(0, 0, 1),
                    radius,
                ),
                math.radians(start_angle),
                math.radians(end_angle),
            )
            idx = sketch.addGeometry(arc)

        elif geometry_type == "rectangle":
            corner1 = params.get("corner1", (0, 0))
            corner2 = params.get("corner2", (10, 10))
            import Part
            # Create 4 lines
            lines = [
                Part.LineSegment(FreeCAD.Vector(corner1[0], corner1[1], 0), FreeCAD.Vector(corner2[0], corner1[1], 0)),
                Part.LineSegment(FreeCAD.Vector(corner2[0], corner1[1], 0), FreeCAD.Vector(corner2[0], corner2[1], 0)),
                Part.LineSegment(FreeCAD.Vector(corner2[0], corner2[1], 0), FreeCAD.Vector(corner1[0], corner2[1], 0)),
                Part.LineSegment(FreeCAD.Vector(corner1[0], corner2[1], 0), FreeCAD.Vector(corner1[0], corner1[1], 0)),
            ]
            for line in lines:
                idx = sketch.addGeometry(line)

        elif geometry_type == "polygon":
            points = params.get("points", [(0, 0), (10, 0), (5, 10)])
            import Part
            for i in range(len(points)):
                p1 = points[i]
                p2 = points[(i + 1) % len(points)]
                line = Part.LineSegment(
                    FreeCAD.Vector(p1[0], p1[1], 0),
                    FreeCAD.Vector(p2[0], p2[1], 0),
                )
                idx = sketch.addGeometry(line)

        else:
            raise ValueError(f"Unknown geometry type: {geometry_type}")

        self._get_doc(doc_name).recompute()
        return idx

    def add_sketch_constraint(
        self,
        sketch_name: str,
        constraint_type: str,
        doc_name: str | None,
        params: dict,
    ) -> int:
        """Add constraint to a sketch."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        sketch = self._get_obj(sketch_name, doc_name)
        constraint_type = constraint_type.lower()

        geo_idx = params.get("geometry_index", 0)
        geo_idx2 = params.get("geometry_index2")
        pt_idx = params.get("point_index")
        pt_idx2 = params.get("point_index2")
        value = params.get("value")

        if constraint_type == "coincident":
            idx = sketch.addConstraint(
                Sketcher.Constraint("Coincident", geo_idx, pt_idx or 1, geo_idx2 or -1, pt_idx2 or 1)
            )

        elif constraint_type == "horizontal":
            idx = sketch.addConstraint(Sketcher.Constraint("Horizontal", geo_idx))

        elif constraint_type == "vertical":
            idx = sketch.addConstraint(Sketcher.Constraint("Vertical", geo_idx))

        elif constraint_type == "parallel":
            idx = sketch.addConstraint(Sketcher.Constraint("Parallel", geo_idx, geo_idx2))

        elif constraint_type == "perpendicular":
            idx = sketch.addConstraint(Sketcher.Constraint("Perpendicular", geo_idx, geo_idx2))

        elif constraint_type == "distance":
            if geo_idx2 is not None:
                idx = sketch.addConstraint(
                    Sketcher.Constraint("Distance", geo_idx, pt_idx or 0, geo_idx2, pt_idx2 or 0, value or 10)
                )
            else:
                idx = sketch.addConstraint(Sketcher.Constraint("Distance", geo_idx, value or 10))

        elif constraint_type == "angle":
            idx = sketch.addConstraint(Sketcher.Constraint("Angle", geo_idx, geo_idx2, value or 90))

        elif constraint_type == "radius":
            idx = sketch.addConstraint(Sketcher.Constraint("Radius", geo_idx, value or 5))

        elif constraint_type == "equal":
            idx = sketch.addConstraint(Sketcher.Constraint("Equal", geo_idx, geo_idx2))

        else:
            raise ValueError(f"Unknown constraint type: {constraint_type}")

        self._get_doc(doc_name).recompute()
        return idx

    def close_sketch(self, sketch_name: str, doc_name: str | None) -> bool:
        """Close sketch editing."""
        # In headless mode, sketches don't need closing
        return True

    def pad_sketch(
        self,
        sketch_name: str,
        length: float,
        symmetric: bool,
        reversed: bool,
        name: str | None,
        doc_name: str | None,
    ) -> str:
        """Pad (extrude) a sketch."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        doc = self._get_doc(doc_name)
        sketch = self._get_obj(sketch_name, doc_name)

        pad = doc.addObject("PartDesign::Pad", name or "Pad")
        pad.Profile = sketch
        pad.Length = length
        pad.Symmetric = symmetric
        pad.Reversed = reversed

        doc.recompute()
        return pad.Name

    def pocket_sketch(
        self,
        sketch_name: str,
        length: float,
        through_all: bool,
        reversed: bool,
        name: str | None,
        doc_name: str | None,
    ) -> str:
        """Create a pocket from a sketch."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        doc = self._get_doc(doc_name)
        sketch = self._get_obj(sketch_name, doc_name)

        pocket = doc.addObject("PartDesign::Pocket", name or "Pocket")
        pocket.Profile = sketch
        pocket.Length = length
        pocket.Type = "ThroughAll" if through_all else "Length"
        pocket.Reversed = reversed

        doc.recompute()
        return pocket.Name

    def revolve_sketch(
        self,
        sketch_name: str,
        angle: float,
        axis: str,
        name: str | None,
        doc_name: str | None,
    ) -> str:
        """Revolve a sketch around an axis."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        doc = self._get_doc(doc_name)
        sketch = self._get_obj(sketch_name, doc_name)

        rev = doc.addObject("PartDesign::Revolution", name or "Revolution")
        rev.Profile = sketch
        rev.Angle = angle

        # Set axis
        if axis.upper() == "X":
            rev.Axis = (FreeCAD.Vector(1, 0, 0),)
        elif axis.upper() == "Y":
            rev.Axis = (FreeCAD.Vector(0, 1, 0),)
        elif axis.upper() == "Z":
            rev.Axis = (FreeCAD.Vector(0, 0, 1),)

        doc.recompute()
        return rev.Name

    # =========================================================================
    # Draft (2D)
    # =========================================================================

    def draft_line(
        self,
        start: list[float],
        end: list[float],
        name: str | None,
        doc_name: str | None,
    ) -> str:
        """Create a draft line."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        self._get_doc(doc_name)  # Ensure doc is active
        line = Draft.makeLine(
            FreeCAD.Vector(start[0], start[1], start[2]),
            FreeCAD.Vector(end[0], end[1], end[2]),
        )
        if name:
            line.Label = name
        return line.Name

    def draft_rectangle(
        self,
        corner: list[float],
        width: float,
        height: float,
        name: str | None,
        doc_name: str | None,
    ) -> str:
        """Create a draft rectangle."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        self._get_doc(doc_name)
        rect = Draft.makeRectangle(width, height)
        rect.Placement.Base = FreeCAD.Vector(corner[0], corner[1], corner[2])
        if name:
            rect.Label = name
        return rect.Name

    def draft_circle(
        self,
        center: list[float],
        radius: float,
        name: str | None,
        doc_name: str | None,
    ) -> str:
        """Create a draft circle."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        self._get_doc(doc_name)
        circle = Draft.makeCircle(radius)
        circle.Placement.Base = FreeCAD.Vector(center[0], center[1], center[2])
        if name:
            circle.Label = name
        return circle.Name

    def draft_text(
        self,
        text: str,
        position: list[float],
        size: float,
        name: str | None,
        doc_name: str | None,
    ) -> str:
        """Create text annotation."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        self._get_doc(doc_name)
        text_obj = Draft.makeText([text], FreeCAD.Vector(position[0], position[1], position[2]))
        text_obj.ViewObject.FontSize = size
        if name:
            text_obj.Label = name
        return text_obj.Name

    # =========================================================================
    # Object Operations
    # =========================================================================

    def get_objects(self, doc_name: str | None) -> list[dict]:
        """Get all objects in document."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        doc = self._get_doc(doc_name)
        objects = []
        for obj in doc.Objects:
            obj_info = {
                "name": obj.Name,
                "type": obj.TypeId,
                "label": obj.Label,
            }

            # Add placement if available
            if hasattr(obj, "Placement"):
                p = obj.Placement
                obj_info["placement"] = {
                    "x": p.Base.x,
                    "y": p.Base.y,
                    "z": p.Base.z,
                }

            objects.append(obj_info)

        return objects

    def get_object_info(self, obj_name: str, doc_name: str | None) -> dict:
        """Get detailed object information."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        obj = self._get_obj(obj_name, doc_name)

        info = {
            "name": obj.Name,
            "type": obj.TypeId,
            "label": obj.Label,
            "properties": {},
        }

        # Get common properties
        for prop in obj.PropertiesList:
            try:
                value = getattr(obj, prop)
                # Convert to serializable format
                if hasattr(value, "Value"):
                    value = value.Value
                elif hasattr(value, "__iter__") and not isinstance(value, str):
                    value = list(value)
                info["properties"][prop] = str(value)[:100]  # Truncate long values
            except Exception:
                pass

        # Add placement
        if hasattr(obj, "Placement"):
            p = obj.Placement
            info["placement"] = {
                "x": p.Base.x,
                "y": p.Base.y,
                "z": p.Base.z,
            }

        return info

    def edit_object(self, obj_name: str, doc_name: str | None, properties: dict) -> bool:
        """Edit object properties."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        obj = self._get_obj(obj_name, doc_name)

        for prop, value in properties.items():
            if hasattr(obj, prop):
                setattr(obj, prop, value)

        self._get_doc(doc_name).recompute()
        return True

    def delete_object(self, obj_name: str, doc_name: str | None) -> bool:
        """Delete an object."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        doc = self._get_doc(doc_name)
        doc.removeObject(obj_name)
        return True

    def copy_object(self, obj_name: str, new_name: str | None, doc_name: str | None) -> str:
        """Copy an object."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        doc = self._get_doc(doc_name)
        obj = self._get_obj(obj_name, doc_name)

        # Simple copy using Draft
        copy = Draft.clone(obj)
        if new_name:
            copy.Label = new_name

        doc.recompute()
        return copy.Name

    # =========================================================================
    # Code Execution
    # =========================================================================

    def execute_code(self, code: str, doc_name: str | None) -> dict:
        """Execute Python code in FreeCAD context."""
        result = {
            "success": False,
            "result": None,
            "error": None,
            "stdout": "",
            "stderr": "",
        }

        if not FREECAD_AVAILABLE:
            result["error"] = "FreeCAD not available"
            return result

        # Capture stdout/stderr
        import io
        import sys

        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = captured_stdout = io.StringIO()
        sys.stderr = captured_stderr = io.StringIO()

        try:
            # Set up execution context
            if doc_name:
                FreeCAD.setActiveDocument(doc_name)

            exec_globals = {
                "FreeCAD": FreeCAD,
                "App": FreeCAD,
                "Part": Part,
                "Draft": Draft,
                "__builtins__": __builtins__,
            }

            try:
                exec_globals["FreeCADGui"] = FreeCADGui
                exec_globals["Gui"] = FreeCADGui
            except Exception:
                pass

            # Execute
            exec(code, exec_globals)

            result["success"] = True
            result["result"] = exec_globals.get("__result__")

        except Exception as e:
            result["error"] = f"{type(e).__name__}: {str(e)}"
            result["traceback"] = traceback.format_exc()

        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            result["stdout"] = captured_stdout.getvalue()
            result["stderr"] = captured_stderr.getvalue()

        return result

    # =========================================================================
    # Import/Export
    # =========================================================================

    def export_model(
        self,
        file_path: str,
        format: str | None,
        objects: list[str] | None,
        doc_name: str | None,
    ) -> str:
        """Export model to file."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        doc = self._get_doc(doc_name)

        # Determine format from extension if not specified
        if format is None:
            ext = os.path.splitext(file_path)[1].lower()
            format_map = {
                ".step": "step",
                ".stp": "step",
                ".stl": "stl",
                ".obj": "obj",
                ".iges": "iges",
                ".igs": "iges",
                ".brep": "brep",
            }
            format = format_map.get(ext, "step")

        # Get objects to export
        if objects:
            export_objs = [self._get_obj(name, doc_name) for name in objects]
        else:
            export_objs = [obj for obj in doc.Objects if hasattr(obj, "Shape")]

        # Export based on format
        format = format.lower()
        if format == "step":
            Part.export(export_objs, file_path)
        elif format == "stl":
            import Mesh
            meshes = []
            for obj in export_objs:
                mesh = Mesh.Mesh(obj.Shape.tessellate(0.1))
                meshes.append(mesh)
            Mesh.export(meshes, file_path)
        elif format == "obj":
            import Mesh
            meshes = []
            for obj in export_objs:
                mesh = Mesh.Mesh(obj.Shape.tessellate(0.1))
                meshes.append(mesh)
            Mesh.export(meshes, file_path)
        elif format == "iges":
            Part.export(export_objs, file_path)
        elif format == "brep":
            Part.export(export_objs, file_path)
        else:
            raise ValueError(f"Unknown export format: {format}")

        return file_path

    def import_model(self, file_path: str, doc_name: str | None) -> list[str]:
        """Import model from file."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        doc = self._get_doc(doc_name)
        existing_names = set(obj.Name for obj in doc.Objects)

        # Determine file type and import appropriately
        ext = os.path.splitext(file_path)[1].lower()
        mesh_formats = {'.stl', '.obj', '.ply', '.off', '.bms'}
        part_formats = {'.step', '.stp', '.iges', '.igs', '.brep', '.brp'}

        if ext in mesh_formats:
            # Use Mesh module for mesh files
            import Mesh
            Mesh.insert(file_path, doc.Name)
        elif ext in part_formats:
            # Use Part module for CAD files
            Part.insert(file_path, doc.Name)
        else:
            # Try Part first, fall back to Mesh
            try:
                Part.insert(file_path, doc.Name)
            except Exception:
                import Mesh
                Mesh.insert(file_path, doc.Name)

        doc.recompute()

        # Find new objects
        new_names = []
        for obj in doc.Objects:
            if obj.Name not in existing_names:
                new_names.append(obj.Name)

        return new_names

    def import_mesh(self, file_path: str, doc_name: str | None) -> list[str]:
        """Import mesh file (OBJ, STL, PLY) into document.

        Args:
            file_path: Path to mesh file
            doc_name: Document name (uses active if None)

        Returns:
            List of imported object names
        """
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        doc = self._get_doc(doc_name)
        existing_names = set(obj.Name for obj in doc.Objects)

        import Mesh
        Mesh.insert(file_path, doc.Name)
        doc.recompute()

        # Find new objects
        new_names = []
        for obj in doc.Objects:
            if obj.Name not in existing_names:
                new_names.append(obj.Name)

        return new_names

    # =========================================================================
    # View and Rendering
    # =========================================================================

    def get_view(
        self,
        view_angle: str,
        width: int,
        height: int,
        doc_name: str | None,
    ) -> str:
        """Capture viewport screenshot."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        doc = self._get_doc(doc_name)

        # Set view angle
        self.set_view(view_angle, doc_name)

        # Capture image
        try:
            view = FreeCADGui.ActiveDocument.ActiveView
            view.fitAll()

            # Save to temp file
            temp_path = os.path.join(self.temp_dir, f"view_{view_angle}.png")
            view.saveImage(temp_path, width, height, "White")

            # Read and encode
            with open(temp_path, "rb") as f:
                img_data = f.read()

            return base64.b64encode(img_data).decode()

        except Exception as e:
            logger.error(f"Failed to capture view: {e}")
            raise RuntimeError(f"Failed to capture view: {e}")

    def set_view(self, view_angle: str, doc_name: str | None) -> bool:
        """Set camera view angle."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        try:
            view = FreeCADGui.ActiveDocument.ActiveView

            view_angle = view_angle.lower()
            if view_angle == "front":
                view.viewFront()
            elif view_angle == "back":
                view.viewRear()
            elif view_angle == "top":
                view.viewTop()
            elif view_angle == "bottom":
                view.viewBottom()
            elif view_angle == "left":
                view.viewLeft()
            elif view_angle == "right":
                view.viewRight()
            elif view_angle == "isometric":
                view.viewIsometric()
            else:
                logger.warning(f"Unknown view angle: {view_angle}")
                return False

            return True

        except Exception as e:
            logger.error(f"Failed to set view: {e}")
            return False

    def fit_view(self, doc_name: str | None) -> bool:
        """Fit view to show all objects."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        try:
            view = FreeCADGui.ActiveDocument.ActiveView
            view.fitAll()
            return True
        except Exception as e:
            logger.error(f"Failed to fit view: {e}")
            return False

    def render_scene(
        self,
        width: int,
        height: int,
        renderer: str,
        doc_name: str | None,
    ) -> str:
        """Render high-quality image."""
        raise NotImplementedError(
            "render_scene requires the Render workbench which is not installed. "
            "Use get_view() for basic viewport screenshots instead."
        )

    # =========================================================================
    # Measurement
    # =========================================================================

    def measure_distance(
        self,
        obj1_name: str,
        obj2_name: str,
        doc_name: str | None,
    ) -> float:
        """Measure distance between two objects."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        obj1 = self._get_obj(obj1_name, doc_name)
        obj2 = self._get_obj(obj2_name, doc_name)

        # Use bounding box centers
        bb1 = obj1.Shape.BoundBox
        bb2 = obj2.Shape.BoundBox

        center1 = FreeCAD.Vector(
            (bb1.XMin + bb1.XMax) / 2,
            (bb1.YMin + bb1.YMax) / 2,
            (bb1.ZMin + bb1.ZMax) / 2,
        )
        center2 = FreeCAD.Vector(
            (bb2.XMin + bb2.XMax) / 2,
            (bb2.YMin + bb2.YMax) / 2,
            (bb2.ZMin + bb2.ZMax) / 2,
        )

        return center1.distanceToPoint(center2)

    def get_bounding_box(self, obj_name: str, doc_name: str | None) -> dict:
        """Get object bounding box."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        obj = self._get_obj(obj_name, doc_name)
        bb = obj.Shape.BoundBox

        return {
            "xmin": bb.XMin,
            "xmax": bb.XMax,
            "ymin": bb.YMin,
            "ymax": bb.YMax,
            "zmin": bb.ZMin,
            "zmax": bb.ZMax,
        }

    def get_volume(self, obj_name: str, doc_name: str | None) -> float:
        """Get object volume."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        obj = self._get_obj(obj_name, doc_name)
        return obj.Shape.Volume

    def get_surface_area(self, obj_name: str, doc_name: str | None) -> float:
        """Get object surface area."""
        if not FREECAD_AVAILABLE:
            raise RuntimeError("FreeCAD not available")

        obj = self._get_obj(obj_name, doc_name)
        return obj.Shape.Area

    # =========================================================================
    # Video Rendering
    # =========================================================================

    def render_spinning_video(
        self,
        model_path: str,
        output_path: str,
        num_frames: int = 60,
        width: int = 640,
        height: int = 480,
        fps: int = 30,
    ) -> dict:
        """Render a spinning video of a 3D model using OSMesa.

        Args:
            model_path: Path to GLB/OBJ/STL file
            output_path: Output video path (.mp4)
            num_frames: Number of frames for full rotation
            width: Frame width in pixels
            height: Frame height in pixels
            fps: Frames per second

        Returns:
            Dict with success status and output path
        """
        import subprocess

        try:
            # Call the render_video.py script
            cmd = [
                "/lsiopy/bin/python3", "/app/render_video.py",
                model_path,
                output_path,
                str(num_frames),
                str(width),
                str(height),
                str(fps),
            ]

            logger.info(f"Rendering spinning video: {' '.join(cmd)}")

            # Create clean environment without FreeCAD's PYTHONPATH/PYTHONHOME
            # which would break the system Python subprocess
            clean_env = {
                k: v for k, v in os.environ.items()
                if not k.startswith("PYTHON") and k != "LD_PRELOAD"
            }
            clean_env["PYOPENGL_PLATFORM"] = "osmesa"
            clean_env["PATH"] = "/lsiopy/bin:/usr/local/bin:/usr/bin:/bin"

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                env=clean_env,
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": result.stderr or result.stdout,
                }

            # Read video file and return as base64
            if os.path.exists(output_path):
                with open(output_path, "rb") as f:
                    video_data = f.read()

                return {
                    "success": True,
                    "output_path": output_path,
                    "frames": num_frames,
                    "duration_seconds": num_frames / fps,
                    "video_base64": base64.b64encode(video_data).decode(),
                    "stdout": result.stdout,
                }
            else:
                return {
                    "success": False,
                    "error": f"Video file not created: {output_path}",
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Rendering timed out after 5 minutes",
            }
        except Exception as e:
            logger.exception(f"Failed to render video: {e}")
            return {
                "success": False,
                "error": str(e),
            }


def main():
    """Start the XML-RPC server."""
    host = os.environ.get("RPC_HOST", "0.0.0.0")
    port = int(os.environ.get("RPC_PORT", "9875"))

    server = SimpleXMLRPCServer(
        (host, port),
        requestHandler=RequestHandler,
        allow_none=True,
    )
    server.register_introspection_functions()

    rpc = FreeCADRPCServer()
    server.register_instance(rpc)

    logger.info(f"FreeCAD XML-RPC server listening on {host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
