#!/usr/bin/env python3
"""Render spinning video of a 3D model using VTK for high-quality offscreen rendering."""

import os
import sys
import subprocess
from pathlib import Path

import numpy as np


def render_spinning_video(
    model_path: str,
    output_path: str,
    num_frames: int = 36,
    width: int = 640,
    height: int = 480,
    fps: int = 30,
) -> dict:
    """Render a spinning video of a 3D model using VTK.

    Args:
        model_path: Path to GLB/OBJ/STL file
        output_path: Output video path (.mp4)
        num_frames: Number of frames for full rotation (default 36 = 10 deg steps)
        width: Frame width in pixels
        height: Frame height in pixels
        fps: Frames per second

    Returns:
        Dict with success status and output path
    """
    import trimesh
    import vtk
    from vtk.util import numpy_support
    from PIL import Image

    # Create temp directory for frames
    frames_dir = Path("/tmp/render_frames")
    frames_dir.mkdir(exist_ok=True)

    # Clean old frames
    for f in frames_dir.glob("frame_*.png"):
        f.unlink()

    print(f"Loading model: {model_path}")
    scene_or_mesh = trimesh.load(model_path)

    # Handle Scene vs Mesh
    if isinstance(scene_or_mesh, trimesh.Scene):
        mesh = scene_or_mesh.to_geometry()
    else:
        mesh = scene_or_mesh

    print(f"Original mesh: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces")

    # Get bounds for camera positioning
    bounds = mesh.bounds
    center = mesh.centroid
    size = np.max(bounds[1] - bounds[0])

    # Convert texture to vertex colors if needed
    if hasattr(mesh.visual, 'kind') and mesh.visual.kind == 'texture':
        try:
            mesh.visual = mesh.visual.to_color()
            print("Converted texture to vertex colors")
        except Exception as e:
            print(f"Could not convert texture: {e}")

    # Simplify mesh if too large
    max_faces = 200000  # VTK handles larger meshes well
    if len(mesh.faces) > max_faces:
        print(f"Simplifying from {len(mesh.faces)} to ~{max_faces} faces...")
        indices = np.random.choice(len(mesh.faces), max_faces, replace=False)
        mesh = mesh.submesh([indices], append=True)
        print(f"After simplification: {len(mesh.faces)} faces")

    # Create VTK polydata from trimesh
    vtk_points = vtk.vtkPoints()
    for v in mesh.vertices:
        vtk_points.InsertNextPoint(v)

    vtk_cells = vtk.vtkCellArray()
    for face in mesh.faces:
        vtk_cells.InsertNextCell(3)
        for idx in face:
            vtk_cells.InsertCellPoint(idx)

    polydata = vtk.vtkPolyData()
    polydata.SetPoints(vtk_points)
    polydata.SetPolys(vtk_cells)

    # Add vertex colors if available
    if hasattr(mesh.visual, 'vertex_colors') and mesh.visual.vertex_colors is not None:
        colors = vtk.vtkUnsignedCharArray()
        colors.SetNumberOfComponents(3)
        colors.SetName("Colors")
        vc = mesh.visual.vertex_colors[:, :3]  # RGB only
        for c in vc:
            colors.InsertNextTuple3(c[0], c[1], c[2])
        polydata.GetPointData().SetScalars(colors)
        print("Using vertex colors")
    else:
        print("Using default material color")

    # Compute normals for smooth shading
    normals = vtk.vtkPolyDataNormals()
    normals.SetInputData(polydata)
    normals.ComputePointNormalsOn()
    normals.ComputeCellNormalsOff()
    normals.SplittingOff()
    normals.Update()

    # Create mapper
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(normals.GetOutputPort())

    # Create actor
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)

    # If no vertex colors, set a nice default material
    if not (hasattr(mesh.visual, 'vertex_colors') and mesh.visual.vertex_colors is not None):
        actor.GetProperty().SetColor(0.7, 0.7, 0.8)  # Light blue-gray

    actor.GetProperty().SetInterpolationToPhong()

    # Create renderer
    renderer = vtk.vtkRenderer()
    renderer.AddActor(actor)
    renderer.SetBackground(1.0, 1.0, 1.0)  # White background

    # Add lighting
    renderer.RemoveAllLights()

    # Key light
    key_light = vtk.vtkLight()
    key_light.SetLightTypeToSceneLight()
    key_light.SetPosition(size * 2, size * 2, size * 2)
    key_light.SetFocalPoint(*center)
    key_light.SetIntensity(1.0)
    key_light.SetColor(1.0, 1.0, 1.0)
    renderer.AddLight(key_light)

    # Fill light
    fill_light = vtk.vtkLight()
    fill_light.SetLightTypeToSceneLight()
    fill_light.SetPosition(-size * 2, size, size * 2)
    fill_light.SetFocalPoint(*center)
    fill_light.SetIntensity(0.5)
    fill_light.SetColor(1.0, 1.0, 1.0)
    renderer.AddLight(fill_light)

    # Rim light
    rim_light = vtk.vtkLight()
    rim_light.SetLightTypeToSceneLight()
    rim_light.SetPosition(0, -size, -size * 2)
    rim_light.SetFocalPoint(*center)
    rim_light.SetIntensity(0.3)
    rim_light.SetColor(1.0, 1.0, 1.0)
    renderer.AddLight(rim_light)

    # Create render window (offscreen)
    render_window = vtk.vtkRenderWindow()
    render_window.SetOffScreenRendering(1)
    render_window.AddRenderer(renderer)
    render_window.SetSize(width, height)

    # Set up camera
    camera = renderer.GetActiveCamera()
    camera_distance = size * 2.5

    # Window to image filter for capturing frames
    window_to_image = vtk.vtkWindowToImageFilter()
    window_to_image.SetInput(render_window)
    window_to_image.SetInputBufferTypeToRGB()
    window_to_image.ReadFrontBufferOff()

    print(f"Rendering {num_frames} frames...")

    for i in range(num_frames):
        # Calculate camera position for this frame (rotate around Y axis)
        angle = (2 * np.pi * i) / num_frames

        # Camera position: rotate around the object
        cam_x = center[0] + camera_distance * np.sin(angle)
        cam_y = center[1] + camera_distance * 0.3  # Slight elevation
        cam_z = center[2] + camera_distance * np.cos(angle)

        camera.SetPosition(cam_x, cam_y, cam_z)
        camera.SetFocalPoint(*center)
        camera.SetViewUp(0, 1, 0)

        # Render
        render_window.Render()

        # Capture frame
        window_to_image.Modified()
        window_to_image.Update()

        # Convert to numpy array
        vtk_image = window_to_image.GetOutput()
        vtk_array = vtk_image.GetPointData().GetScalars()
        numpy_array = numpy_support.vtk_to_numpy(vtk_array)
        numpy_array = numpy_array.reshape(height, width, 3)
        numpy_array = np.flipud(numpy_array)  # Flip vertically

        # Save frame
        frame_path = frames_dir / f"frame_{i:03d}.png"
        Image.fromarray(numpy_array).save(frame_path)

        if i % 10 == 0:
            print(f"  Frame {i}/{num_frames}")

    print(f"Rendered {num_frames} frames")

    # Combine frames into video using ffmpeg
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", str(frames_dir / "frame_%03d.png"),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "23",
        str(output_path)
    ]

    print(f"Creating video: {output_path}")
    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        return {
            "success": False,
            "error": f"ffmpeg failed: {result.stderr}"
        }

    # Clean up frames
    for f in frames_dir.glob("frame_*.png"):
        f.unlink()

    print(f"Video saved: {output_path}")

    return {
        "success": True,
        "output_path": str(output_path),
        "frames": num_frames,
        "duration_seconds": num_frames / fps
    }


def render_spinning_video_matplotlib(
    model_path: str,
    output_path: str,
    num_frames: int = 36,
    width: int = 640,
    height: int = 480,
    fps: int = 30,
) -> dict:
    """Fallback renderer using matplotlib (lower quality but always works).

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
    import matplotlib
    matplotlib.use('Agg')  # Headless backend
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    import trimesh

    # Create temp directory for frames
    frames_dir = Path("/tmp/render_frames")
    frames_dir.mkdir(exist_ok=True)

    # Clean old frames
    for f in frames_dir.glob("frame_*.png"):
        f.unlink()

    print(f"Loading model: {model_path}")
    scene = trimesh.load(model_path, force='mesh')

    # Convert to single mesh if scene
    if isinstance(scene, trimesh.Scene):
        mesh = scene.dump(concatenate=True)
    else:
        mesh = scene

    print(f"Original mesh: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces")

    # Get bounds for scaling before any modifications
    bounds = mesh.bounds
    size = np.max(bounds[1] - bounds[0])

    # Subsample faces for faster rendering
    max_faces = 10000
    face_indices = None
    if len(mesh.faces) > max_faces:
        print(f"Subsampling from {len(mesh.faces)} to {max_faces} faces...")
        face_indices = np.random.choice(len(mesh.faces), max_faces, replace=False)
        faces = mesh.faces[face_indices]
    else:
        faces = mesh.faces

    vertices = mesh.vertices

    # Get face colors - handle different visual types
    face_colors = None

    # Try to convert texture to vertex colors first
    if hasattr(mesh.visual, 'kind') and mesh.visual.kind == 'texture':
        try:
            mesh.visual = mesh.visual.to_color()
            print("Converted texture to vertex colors")
        except Exception as e:
            print(f"Could not convert texture: {e}")

    # Now try to get colors
    if face_colors is None and hasattr(mesh.visual, 'vertex_colors') and mesh.visual.vertex_colors is not None:
        try:
            vc = mesh.visual.vertex_colors[:, :3] / 255.0
            face_colors = vc[mesh.faces].mean(axis=1)
            if face_indices is not None:
                face_colors = face_colors[face_indices]
            face_colors = np.column_stack([face_colors, np.ones(len(faces))])
            print(f"Using vertex colors")
        except Exception as e:
            print(f"Vertex color error: {e}")

    if face_colors is None and hasattr(mesh.visual, 'face_colors') and mesh.visual.face_colors is not None:
        try:
            fc = mesh.visual.face_colors[:, :4] / 255.0
            if face_indices is not None:
                face_colors = fc[face_indices]
            else:
                face_colors = fc
            print(f"Using face colors")
        except Exception as e:
            print(f"Face color error: {e}")

    if face_colors is None:
        face_colors = np.ones((len(faces), 4)) * [0.7, 0.7, 0.8, 1.0]
        print("Using default gray color")

    print(f"Rendering {num_frames} frames...")

    # Pre-compute vertex positions for all faces once
    verts = vertices[faces]

    # Set up figure once
    dpi = 100
    fig = plt.figure(figsize=(width/dpi, height/dpi), dpi=dpi)
    ax = fig.add_subplot(111, projection='3d')

    # Set fixed axis limits
    margin = size * 0.1
    ax.set_xlim(bounds[0][0] - margin, bounds[1][0] + margin)
    ax.set_ylim(bounds[0][1] - margin, bounds[1][1] + margin)
    ax.set_zlim(bounds[0][2] - margin, bounds[1][2] + margin)
    ax.set_axis_off()
    ax.set_box_aspect([1, 1, 1])

    # Create polygon collection once with depth sorting
    poly = Poly3DCollection(verts, facecolors=face_colors, edgecolors='none', linewidths=0, zsort='average')
    ax.add_collection3d(poly)

    for i in range(num_frames):
        # Rotate view
        angle = (360 * i) / num_frames
        ax.view_init(elev=20, azim=angle)

        # Save frame
        frame_path = frames_dir / f"frame_{i:03d}.png"
        fig.savefig(frame_path, dpi=dpi, facecolor='white', edgecolor='none')

        if i % 10 == 0:
            print(f"  Frame {i}/{num_frames}")

    plt.close(fig)
    print(f"Rendered {num_frames} frames")

    # Combine frames into video using ffmpeg
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", str(frames_dir / "frame_%03d.png"),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "23",
        str(output_path)
    ]

    print(f"Creating video: {output_path}")
    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        return {
            "success": False,
            "error": f"ffmpeg failed: {result.stderr}"
        }

    # Clean up frames
    for f in frames_dir.glob("frame_*.png"):
        f.unlink()

    print(f"Video saved: {output_path}")

    return {
        "success": True,
        "output_path": str(output_path),
        "frames": num_frames,
        "duration_seconds": num_frames / fps
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: render_video.py <model_path> <output_path> [num_frames] [width] [height] [fps]")
        sys.exit(1)

    model_path = sys.argv[1]
    output_path = sys.argv[2]
    num_frames = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    width = int(sys.argv[4]) if len(sys.argv) > 4 else 640
    height = int(sys.argv[5]) if len(sys.argv) > 5 else 480
    fps = int(sys.argv[6]) if len(sys.argv) > 6 else 30

    # Try VTK first, fall back to matplotlib
    try:
        result = render_spinning_video(
            model_path=model_path,
            output_path=output_path,
            num_frames=num_frames,
            width=width,
            height=height,
            fps=fps
        )
    except Exception as e:
        print(f"VTK failed ({e}), falling back to matplotlib...")
        result = render_spinning_video_matplotlib(
            model_path=model_path,
            output_path=output_path,
            num_frames=num_frames,
            width=width,
            height=height,
            fps=fps
        )

    print(result)
    sys.exit(0 if result["success"] else 1)
