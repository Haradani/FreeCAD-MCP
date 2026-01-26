#!/usr/bin/env python3
"""Vision AI analysis example.

This example demonstrates how to use the Vision AI features
(Cosmos VLM and SAM) to analyze CAD models.
"""

import sys
sys.path.insert(0, "..")

from PIL import Image

from src.inference_client import InferenceClient
from src.cosmos_vlm import (
    analyze_cad_image,
    validate_design,
    suggest_improvements,
    identify_features,
)
from src.sam_segmentation import (
    segment_at_point,
    segment_feature_by_name,
    find_holes,
    highlight_feature,
)


def analyze_model(image_path: str):
    """Analyze a CAD model image with VLM.

    Args:
        image_path: Path to CAD model image
    """
    print(f"Analyzing: {image_path}")
    image = Image.open(image_path)

    # Basic analysis
    print("\n1. General Analysis")
    print("-" * 40)
    result = analyze_cad_image(image)
    print(result["response"])

    if result.get("thinking"):
        print("\n   [Chain of Thought]")
        print(f"   {result['thinking'][:200]}...")

    # Identify features
    print("\n2. Feature Identification")
    print("-" * 40)
    features = identify_features(image)
    for i, feature in enumerate(features, 1):
        print(f"   {i}. {feature.get('name', 'Unknown')}")
        if feature.get("type"):
            print(f"      Type: {feature['type']}")
        if feature.get("description"):
            print(f"      Description: {feature['description']}")

    # Validate against requirements
    print("\n3. Design Validation")
    print("-" * 40)
    requirements = [
        "Must have center mounting hole",
        "Should include bolt holes for assembly",
        "Edges should be filleted for safety",
    ]
    validation = validate_design(image, requirements)
    print(f"   Valid: {validation['valid']}")
    print(f"   Score: {validation['score']*100:.0f}%")
    if validation["issues"]:
        print("   Issues:")
        for issue in validation["issues"]:
            print(f"     - {issue}")

    # Get improvement suggestions
    print("\n4. Improvement Suggestions")
    print("-" * 40)
    suggestions = suggest_improvements(image)
    for i, suggestion in enumerate(suggestions[:5], 1):
        print(f"   {i}. {suggestion}")


def segment_model(image_path: str):
    """Segment features in a CAD model image with SAM.

    Args:
        image_path: Path to CAD model image
    """
    print(f"\nSegmenting: {image_path}")
    image = Image.open(image_path)

    # Segment by clicking center of image
    print("\n1. Point-based Segmentation (center)")
    print("-" * 40)
    cx, cy = image.width // 2, image.height // 2
    result = segment_at_point(image, cx, cy)
    print(f"   Score: {result['score']:.3f}")
    print(f"   Area: {result['area_percent']:.1f}% of image")
    result["mask"].save("segment_center.png")
    print("   Saved mask to: segment_center.png")

    # Segment holes
    print("\n2. Finding Holes")
    print("-" * 40)
    holes = find_holes(image)
    print(f"   Found {len(holes)} hole region(s)")
    for i, hole in enumerate(holes, 1):
        print(f"   Hole {i}: center={hole['center']}, radius≈{hole['approximate_radius']}px")

    # Segment by text description
    print("\n3. Text-based Segmentation")
    print("-" * 40)
    result = segment_feature_by_name(image, "bolt holes")
    if result["found"]:
        print("   Found bolt holes region")
        result["mask"].save("segment_boltholes.png")
        print("   Saved mask to: segment_boltholes.png")
    else:
        print("   No bolt holes found")

    # Highlight feature
    print("\n4. Feature Highlighting")
    print("-" * 40)
    highlighted = highlight_feature(image, "mounting surface", color=(0, 255, 0))
    highlighted.save("highlighted_surface.png")
    print("   Saved highlighted image to: highlighted_surface.png")


def main():
    """Run vision analysis example."""
    # Check inference server
    client = InferenceClient(host="localhost", port=5555)

    print("Checking inference server connection...")
    if not client.ping():
        print("ERROR: Inference server not responding")
        print("Make sure to start the inference container:")
        print("  docker compose --profile vision up -d")
        return

    status = client.get_status()
    print(f"Connected! GPUs: {status.get('gpus', 'unknown')}")
    print(f"VLM loaded: {status.get('vlm_loaded', False)}")
    print(f"SAM loaded: {status.get('sam_loaded', False)}")

    # Use example image or create one
    import os
    example_image = "example_output.png"

    if not os.path.exists(example_image):
        print(f"\nNo example image found. Creating one...")
        # Run basic example first to generate image
        from basic_usage import main as create_example
        create_example()

    if os.path.exists(example_image):
        # Run analysis
        analyze_model(example_image)
        segment_model(example_image)
    else:
        print("Could not find or create example image")

    print("\nDone!")


if __name__ == "__main__":
    main()
