"""GLB to OBJ/STL converter for FreeCAD import."""

import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ConversionResult:
    """Result from mesh format conversion."""

    success: bool
    obj_path: str | None = None
    mtl_path: str | None = None
    texture_paths: list[str] | None = None
    stl_path: str | None = None
    vertices: int = 0
    faces: int = 0
    error: str | None = None


def convert_glb_to_obj(
    glb_path: str | Path,
    output_dir: str | Path | None = None,
    output_name: str | None = None,
    export_textures: bool = True,
) -> ConversionResult:
    """Convert GLB file to OBJ format with materials.

    Args:
        glb_path: Path to input GLB file
        output_dir: Output directory (defaults to same as input)
        output_name: Output filename without extension (defaults to input name)
        export_textures: Whether to export PBR textures

    Returns:
        ConversionResult with output paths
    """
    try:
        import trimesh
    except ImportError:
        return ConversionResult(
            success=False,
            error="trimesh library not installed. Install with: pip install trimesh"
        )

    glb_path = Path(glb_path)
    if not glb_path.exists():
        return ConversionResult(success=False, error=f"GLB file not found: {glb_path}")

    # Determine output paths
    if output_dir is None:
        output_dir = glb_path.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    if output_name is None:
        output_name = glb_path.stem

    obj_path = output_dir / f"{output_name}.obj"
    mtl_path = output_dir / f"{output_name}.mtl"

    try:
        # Load GLB file
        logger.info(f"Loading GLB: {glb_path}")
        scene = trimesh.load(str(glb_path))

        # Handle both single mesh and scene
        if isinstance(scene, trimesh.Scene):
            # Combine all meshes in scene
            meshes = []
            for name, geometry in scene.geometry.items():
                if isinstance(geometry, trimesh.Trimesh):
                    meshes.append(geometry)

            if not meshes:
                return ConversionResult(success=False, error="No meshes found in GLB")

            if len(meshes) == 1:
                mesh = meshes[0]
            else:
                mesh = trimesh.util.concatenate(meshes)
        else:
            mesh = scene

        # Export OBJ with MTL
        logger.info(f"Exporting OBJ: {obj_path}")
        mesh.export(
            str(obj_path),
            file_type='obj',
            include_normals=True,
            include_texture=export_textures,
        )

        # Collect texture paths
        texture_paths = []
        if export_textures and hasattr(mesh, 'visual') and hasattr(mesh.visual, 'material'):
            material = mesh.visual.material
            if hasattr(material, 'image') and material.image is not None:
                texture_path = output_dir / f"{output_name}_texture.png"
                material.image.save(str(texture_path))
                texture_paths.append(str(texture_path))

        return ConversionResult(
            success=True,
            obj_path=str(obj_path),
            mtl_path=str(mtl_path) if mtl_path.exists() else None,
            texture_paths=texture_paths if texture_paths else None,
            vertices=len(mesh.vertices),
            faces=len(mesh.faces),
        )

    except Exception as e:
        logger.exception(f"GLB conversion failed: {e}")
        return ConversionResult(success=False, error=str(e))


def convert_glb_to_stl(
    glb_path: str | Path,
    output_dir: str | Path | None = None,
    output_name: str | None = None,
    binary: bool = True,
) -> ConversionResult:
    """Convert GLB file to STL format.

    Args:
        glb_path: Path to input GLB file
        output_dir: Output directory (defaults to same as input)
        output_name: Output filename without extension
        binary: Whether to export as binary STL (smaller file size)

    Returns:
        ConversionResult with output path
    """
    try:
        import trimesh
    except ImportError:
        return ConversionResult(
            success=False,
            error="trimesh library not installed. Install with: pip install trimesh"
        )

    glb_path = Path(glb_path)
    if not glb_path.exists():
        return ConversionResult(success=False, error=f"GLB file not found: {glb_path}")

    # Determine output paths
    if output_dir is None:
        output_dir = glb_path.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    if output_name is None:
        output_name = glb_path.stem

    stl_path = output_dir / f"{output_name}.stl"

    try:
        # Load GLB file
        logger.info(f"Loading GLB: {glb_path}")
        scene = trimesh.load(str(glb_path))

        # Handle both single mesh and scene
        if isinstance(scene, trimesh.Scene):
            meshes = [g for g in scene.geometry.values() if isinstance(g, trimesh.Trimesh)]
            if not meshes:
                return ConversionResult(success=False, error="No meshes found in GLB")
            mesh = trimesh.util.concatenate(meshes) if len(meshes) > 1 else meshes[0]
        else:
            mesh = scene

        # Export STL
        logger.info(f"Exporting STL: {stl_path}")
        file_type = 'stl' if binary else 'stl_ascii'
        mesh.export(str(stl_path), file_type=file_type)

        return ConversionResult(
            success=True,
            stl_path=str(stl_path),
            vertices=len(mesh.vertices),
            faces=len(mesh.faces),
        )

    except Exception as e:
        logger.exception(f"GLB to STL conversion failed: {e}")
        return ConversionResult(success=False, error=str(e))


def get_mesh_info(mesh_path: str | Path) -> dict[str, Any]:
    """Get information about a mesh file.

    Args:
        mesh_path: Path to mesh file (GLB, OBJ, STL, etc.)

    Returns:
        Dict with mesh information
    """
    try:
        import trimesh
    except ImportError:
        return {"error": "trimesh library not installed"}

    mesh_path = Path(mesh_path)
    if not mesh_path.exists():
        return {"error": f"File not found: {mesh_path}"}

    try:
        scene = trimesh.load(str(mesh_path))

        if isinstance(scene, trimesh.Scene):
            meshes = [g for g in scene.geometry.values() if isinstance(g, trimesh.Trimesh)]
            mesh = trimesh.util.concatenate(meshes) if meshes else None
        else:
            mesh = scene

        if mesh is None:
            return {"error": "No mesh data found"}

        bounds = mesh.bounds
        return {
            "format": mesh_path.suffix.lower(),
            "vertices": len(mesh.vertices),
            "faces": len(mesh.faces),
            "bounds": {
                "min": bounds[0].tolist(),
                "max": bounds[1].tolist(),
            },
            "dimensions": (bounds[1] - bounds[0]).tolist(),
            "volume": float(mesh.volume) if mesh.is_watertight else None,
            "is_watertight": mesh.is_watertight,
            "center_of_mass": mesh.center_mass.tolist() if mesh.is_watertight else None,
        }

    except Exception as e:
        return {"error": str(e)}
