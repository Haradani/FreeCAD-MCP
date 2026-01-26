#!/usr/bin/env python3
"""Basic usage example for FreeCAD MCP client.

This example demonstrates how to use the FreeCAD client directly
(outside of the MCP server) for testing and development.
"""

import sys
sys.path.insert(0, "..")

from src.freecad_client import FreeCADClient


def main():
    """Run basic FreeCAD operations."""
    # Connect to FreeCAD (assumes container is running)
    client = FreeCADClient(host="localhost", port=9875)

    # Check connection
    print("Checking FreeCAD connection...")
    if not client.ping():
        print("ERROR: FreeCAD not responding. Make sure the container is running:")
        print("  docker compose up freecad -d")
        return

    print("Connected to FreeCAD!")

    # Create a new document
    print("\n1. Creating document...")
    doc_name = client.create_document("Example")
    print(f"   Created: {doc_name}")

    # Create a box
    print("\n2. Creating box primitive...")
    box = client.create_primitive(
        "box",
        name="BaseBox",
        length=100,
        width=60,
        height=20,
    )
    print(f"   Created: {box}")

    # Create a cylinder
    print("\n3. Creating cylinder primitive...")
    cyl = client.create_primitive(
        "cylinder",
        name="Hole",
        radius=10,
        height=30,
    )
    print(f"   Created: {cyl}")

    # Move the cylinder to center of box
    print("\n4. Moving cylinder to center...")
    client.transform_object(
        cyl,
        translate=(50, 30, -5),  # Center of box, slightly below
    )
    print("   Cylinder moved")

    # Boolean cut
    print("\n5. Performing boolean cut...")
    result = client.boolean_operation(
        "cut",
        box,
        cyl,
        result_name="BoxWithHole",
    )
    print(f"   Created: {result}")

    # List objects
    print("\n6. Listing objects...")
    objects = client.get_objects()
    for obj in objects:
        print(f"   - {obj.name} ({obj.type})")

    # Get object info
    print("\n7. Getting detailed info...")
    info = client.get_object_info(result)
    print(f"   Name: {info.name}")
    print(f"   Type: {info.type}")
    if info.placement:
        print(f"   Position: ({info.placement['x']}, {info.placement['y']}, {info.placement['z']})")

    # Get bounding box
    print("\n8. Getting bounding box...")
    bbox = client.get_bounding_box(result)
    print(f"   X: {bbox['xmin']:.1f} to {bbox['xmax']:.1f}")
    print(f"   Y: {bbox['ymin']:.1f} to {bbox['ymax']:.1f}")
    print(f"   Z: {bbox['zmin']:.1f} to {bbox['zmax']:.1f}")

    # Capture view
    print("\n9. Capturing view...")
    try:
        img = client.get_view("isometric", 800, 600)
        img.save("example_output.png")
        print("   Saved to: example_output.png")
    except Exception as e:
        print(f"   View capture failed: {e}")

    # Save document
    print("\n10. Saving document...")
    path = client.save_document(file_path="/data/exports/example.FCStd")
    print(f"    Saved to: {path}")

    # Export to STEP
    print("\n11. Exporting to STEP...")
    try:
        step_path = client.export_model(
            "/data/exports/example.step",
            format="step",
            objects=[result],
        )
        print(f"    Exported to: {step_path}")
    except Exception as e:
        print(f"    Export failed: {e}")

    print("\nDone!")


if __name__ == "__main__":
    main()
