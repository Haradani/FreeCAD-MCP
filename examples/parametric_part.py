#!/usr/bin/env python3
"""Parametric part example using PartDesign workflow.

This example creates a parametric flange using sketches and
PartDesign features (pad, pocket, etc.).
"""

import sys
sys.path.insert(0, "..")

from src.freecad_client import FreeCADClient
import math


def create_flange(
    client: FreeCADClient,
    outer_diameter: float = 100,
    inner_diameter: float = 50,
    thickness: float = 10,
    bolt_circle_diameter: float = 80,
    num_bolts: int = 6,
    bolt_hole_diameter: float = 8,
):
    """Create a parametric flange.

    Args:
        client: FreeCAD client
        outer_diameter: Outer diameter in mm
        inner_diameter: Inner diameter (center hole) in mm
        thickness: Flange thickness in mm
        bolt_circle_diameter: Bolt circle diameter in mm
        num_bolts: Number of bolt holes
        bolt_hole_diameter: Diameter of bolt holes in mm
    """
    print(f"Creating flange: OD={outer_diameter}, ID={inner_diameter}, t={thickness}")
    print(f"  Bolt circle: {bolt_circle_diameter} with {num_bolts}x ∅{bolt_hole_diameter} holes")

    # Create document
    doc_name = client.create_document("Flange")

    # Create PartDesign body
    body = client.create_body("FlangeBody")
    print(f"Created body: {body}")

    # Create base sketch on XY plane
    sketch = client.create_sketch("XY", body, "BaseSketch")
    print(f"Created sketch: {sketch}")

    # Add outer circle
    client.add_sketch_geometry(
        sketch,
        "circle",
        center=(0, 0),
        radius=outer_diameter / 2,
    )

    # Add inner circle (will be used for pocket)
    client.add_sketch_geometry(
        sketch,
        "circle",
        center=(0, 0),
        radius=inner_diameter / 2,
    )

    # Close sketch and pad
    client.close_sketch(sketch)

    # Pad the outer circle
    pad = client.pad_sketch(sketch, thickness, name="FlangePad")
    print(f"Created pad: {pad}")

    # Create sketch for center hole
    hole_sketch = client.create_sketch("XY", body, "HoleSketch")
    client.add_sketch_geometry(
        hole_sketch,
        "circle",
        center=(0, 0),
        radius=inner_diameter / 2,
    )
    client.close_sketch(hole_sketch)

    # Pocket through all for center hole
    pocket = client.pocket_sketch(hole_sketch, thickness, through_all=True, name="CenterHole")
    print(f"Created center hole: {pocket}")

    # Create bolt holes
    for i in range(num_bolts):
        angle = 2 * math.pi * i / num_bolts
        x = (bolt_circle_diameter / 2) * math.cos(angle)
        y = (bolt_circle_diameter / 2) * math.sin(angle)

        # Create sketch for this bolt hole
        bolt_sketch = client.create_sketch("XY", body, f"BoltSketch{i+1}")
        client.add_sketch_geometry(
            bolt_sketch,
            "circle",
            center=(x, y),
            radius=bolt_hole_diameter / 2,
        )
        client.close_sketch(bolt_sketch)

        # Pocket through all
        bolt_pocket = client.pocket_sketch(
            bolt_sketch,
            thickness,
            through_all=True,
            name=f"BoltHole{i+1}",
        )
        print(f"Created bolt hole {i+1}: {bolt_pocket}")

    # Recompute
    print("\nFinalizing model...")

    # Get view
    try:
        img = client.get_view("isometric", 800, 600)
        img.save("flange_output.png")
        print("Saved view to: flange_output.png")
    except Exception as e:
        print(f"View capture failed: {e}")

    # Save
    path = client.save_document(file_path="/data/exports/flange.FCStd")
    print(f"Saved document to: {path}")

    return doc_name


def main():
    """Run parametric part example."""
    client = FreeCADClient(host="localhost", port=9875)

    if not client.ping():
        print("ERROR: FreeCAD not responding")
        return

    print("Connected to FreeCAD\n")

    # Create a standard flange
    create_flange(
        client,
        outer_diameter=150,
        inner_diameter=60,
        thickness=15,
        bolt_circle_diameter=120,
        num_bolts=8,
        bolt_hole_diameter=12,
    )

    print("\nDone!")


if __name__ == "__main__":
    main()
