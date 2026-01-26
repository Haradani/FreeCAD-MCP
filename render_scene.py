#!/usr/bin/env python3
"""Render a 3D scene with truck and chair."""
import trimesh
import numpy as np
from pathlib import Path

# Paths to meshes
TRUCK_GLB = Path("data/trellis/outputs/mesh_1769254558232.glb")
CHAIR_GLB = Path("data/trellis/outputs/mesh_1769221942704.glb")
OUTPUT_PATH = Path("/tmp/truck_with_chair.png")

def load_and_combine():
    """Load meshes and create combined scene."""
    print("Loading truck mesh...")
    truck_scene = trimesh.load(str(TRUCK_GLB))

    print("Loading chair mesh...")
    chair_scene = trimesh.load(str(CHAIR_GLB))

    # Convert scenes to single meshes if needed
    if isinstance(truck_scene, trimesh.Scene):
        truck_mesh = truck_scene.dump(concatenate=True)
    else:
        truck_mesh = truck_scene

    if isinstance(chair_scene, trimesh.Scene):
        chair_mesh = chair_scene.dump(concatenate=True)
    else:
        chair_mesh = chair_scene

    print(f"Truck: {len(truck_mesh.vertices)} vertices")
    print(f"Chair: {len(chair_mesh.vertices)} vertices")

    # Get bounding boxes
    truck_bounds = truck_mesh.bounds
    chair_bounds = chair_mesh.bounds

    truck_size = truck_bounds[1] - truck_bounds[0]
    chair_size = chair_bounds[1] - chair_bounds[0]

    print(f"Truck size: {truck_size}")
    print(f"Chair size: {chair_size}")

    # Scale truck to be larger than chair (truck should be ~3x chair width)
    target_truck_width = chair_size[0] * 4.0
    current_truck_width = truck_size[0]
    truck_scale = target_truck_width / current_truck_width

    truck_mesh.apply_scale(truck_scale)
    truck_bounds = truck_mesh.bounds
    truck_size = truck_bounds[1] - truck_bounds[0]

    print(f"Scaled truck size: {truck_size}")

    # Position chair on truck bed (back of truck, elevated)
    # Note: Based on the mesh, the truck's axes are:
    #   X = width (left-right)
    #   Y = height (up-down)
    #   Z = length (front-back, with high Z being the back/flatbed)
    truck_center = (truck_bounds[0] + truck_bounds[1]) / 2

    # The flatbed is at high Z (back of truck)
    # Cab is at negative Z, flatbed extends to positive Z
    # The actual flatbed area is in the rear 40% of the truck
    # Put chair at 85% to be clearly on the flatbed
    flatbed_center_z = truck_bounds[0][2] + truck_size[2] * 0.85  # 85% from front

    # The flatbed surface Y - needs to be high enough to sit ON the bed
    # Based on visual inspection, flatbed surface is around 65% up from truck bottom
    flatbed_surface_y = truck_bounds[0][1] + truck_size[1] * 0.65  # 65% up from bottom

    # Position chair so its BOTTOM sits at the flatbed surface
    # Chair target Y = flatbed_surface_y + half of chair height
    chair_height = chair_bounds[1][1] - chair_bounds[0][1]
    chair_target_y = flatbed_surface_y + chair_height / 2

    chair_pos = np.array([
        truck_center[0],  # Centered width-wise (X)
        chair_target_y,   # Chair center Y, positioned so bottom sits on flatbed
        flatbed_center_z, # Center of the flatbed area (Z is length)
    ])

    print(f"Chair target position: {chair_pos}")

    # Center chair and move to position
    chair_center = (chair_bounds[0] + chair_bounds[1]) / 2
    translation = chair_pos - chair_center
    chair_mesh.apply_translation(translation)

    print(f"Chair final bounds: {chair_mesh.bounds}")

    # Create combined scene
    scene = trimesh.Scene()
    scene.add_geometry(truck_mesh, node_name="truck")
    scene.add_geometry(chair_mesh, node_name="chair")

    return scene


def render_scene(scene, output_path):
    """Render scene to image."""
    try:
        # Try pyrender for better quality
        import pyrender
        import PIL.Image

        # Convert trimesh scene to pyrender scene
        pr_scene = pyrender.Scene.from_trimesh_scene(scene)

        # Add lighting
        light = pyrender.DirectionalLight(color=[1.0, 1.0, 1.0], intensity=3.0)
        pr_scene.add(light, pose=np.eye(4))

        # Set up camera
        camera = pyrender.PerspectiveCamera(yfov=np.pi / 3.0)

        # Position camera to see the scene
        bounds = scene.bounds
        center = (bounds[0] + bounds[1]) / 2
        size = np.max(bounds[1] - bounds[0])

        camera_pose = np.array([
            [1, 0, 0, center[0] + size * 1.5],
            [0, 1, 0, center[1] + size * 0.5],
            [0, 0, 1, center[2] + size * 1.0],
            [0, 0, 0, 1]
        ])

        pr_scene.add(camera, pose=camera_pose)

        # Render
        r = pyrender.OffscreenRenderer(1280, 720)
        color, _ = r.render(pr_scene)
        r.delete()

        # Save image
        img = PIL.Image.fromarray(color)
        img.save(output_path)
        print(f"Rendered to {output_path}")

    except Exception as e:
        print(f"Pyrender failed: {e}")
        print("Falling back to trimesh built-in render...")

        # Fallback to trimesh's built-in rendering
        try:
            png = scene.save_image(resolution=[1280, 720])
            with open(output_path, 'wb') as f:
                f.write(png)
            print(f"Rendered to {output_path}")
        except Exception as e2:
            print(f"Trimesh render also failed: {e2}")
            # Save as GLB instead
            glb_path = output_path.with_suffix('.glb')
            scene.export(str(glb_path))
            print(f"Exported scene to {glb_path}")


if __name__ == "__main__":
    scene = load_and_combine()
    render_scene(scene, OUTPUT_PATH)

    # Also export the combined scene as GLB
    scene.export("/tmp/truck_with_chair.glb")
    print("Exported combined scene to /tmp/truck_with_chair.glb")
