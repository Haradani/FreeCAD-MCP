"""SAM segmentation integration for CAD analysis.

This module provides high-level functions for using SAM3
to segment CAD model images and identify specific features.
"""

import logging
from typing import Any

import numpy as np
from PIL import Image

from .inference_client import get_inference_client

logger = logging.getLogger(__name__)


def segment_at_point(
    image: Image.Image,
    x: int,
    y: int,
    foreground: bool = True,
) -> dict[str, Any]:
    """Segment the region containing a specific point.

    Args:
        image: CAD model image
        x: X coordinate of point
        y: Y coordinate of point
        foreground: True for foreground selection

    Returns:
        Dict with 'mask' (PIL Image), 'score', 'area'
    """
    client = get_inference_client()

    result = client.segment_point(image, (x, y), foreground)

    # Calculate mask area
    mask_array = np.array(result["mask"])
    area = np.sum(mask_array > 127)
    total = mask_array.size
    area_percent = (area / total) * 100

    return {
        "mask": result["mask"],
        "score": result["score"],
        "area_pixels": area,
        "area_percent": area_percent,
    }


def segment_feature_by_name(
    image: Image.Image,
    feature_name: str,
) -> dict[str, Any]:
    """Segment a feature by its name/description.

    Args:
        image: CAD model image
        feature_name: Name of feature (e.g., "bolt hole", "fillet", "chamfer")

    Returns:
        Dict with 'mask', 'regions', 'found'
    """
    client = get_inference_client()

    result = client.segment_text(image, feature_name)

    found = len(result.get("regions", [])) > 0

    return {
        "mask": result["mask"],
        "regions": result.get("regions", []),
        "found": found,
    }


def find_holes(image: Image.Image) -> list[dict[str, Any]]:
    """Find all holes in a CAD model image.

    Args:
        image: CAD model image

    Returns:
        List of hole dicts with 'mask', 'center', 'approximate_radius'
    """
    result = segment_feature_by_name(image, "holes circular openings")

    if not result["found"]:
        return []

    # For now, return the combined mask
    # In a more sophisticated implementation, we'd separate individual holes
    mask_array = np.array(result["mask"])
    holes = []

    # Find connected components (simplified)
    if np.any(mask_array > 127):
        y_coords, x_coords = np.where(mask_array > 127)
        center_x = int(np.mean(x_coords))
        center_y = int(np.mean(y_coords))

        # Estimate radius from area
        area = len(x_coords)
        radius = int(np.sqrt(area / np.pi))

        holes.append({
            "mask": result["mask"],
            "center": (center_x, center_y),
            "approximate_radius": radius,
        })

    return holes


def find_edges(image: Image.Image) -> Image.Image:
    """Find edges/boundaries in a CAD model image.

    Args:
        image: CAD model image

    Returns:
        Edge mask image
    """
    # Use SAM to segment the main part, then extract edges
    client = get_inference_client()

    # Segment from center of image
    center_x = image.width // 2
    center_y = image.height // 2

    result = client.segment_point(image, (center_x, center_y), foreground=True)
    mask = result["mask"]

    # Convert to numpy and find edges
    mask_array = np.array(mask.convert("L"))

    # Simple edge detection using gradient
    from PIL import ImageFilter
    edges = mask.filter(ImageFilter.FIND_EDGES)

    return edges


def measure_feature_area(
    image: Image.Image,
    feature_name: str,
    pixel_to_mm_ratio: float = 1.0,
) -> dict[str, float]:
    """Measure the area of a feature in the image.

    Args:
        image: CAD model image
        feature_name: Name of feature to measure
        pixel_to_mm_ratio: Conversion factor (pixels per mm)

    Returns:
        Dict with 'area_pixels', 'area_mm2', 'percentage'
    """
    result = segment_feature_by_name(image, feature_name)

    if not result["found"]:
        return {
            "area_pixels": 0,
            "area_mm2": 0.0,
            "percentage": 0.0,
        }

    mask_array = np.array(result["mask"])
    area_pixels = np.sum(mask_array > 127)
    total_pixels = mask_array.size

    return {
        "area_pixels": int(area_pixels),
        "area_mm2": area_pixels / (pixel_to_mm_ratio ** 2),
        "percentage": (area_pixels / total_pixels) * 100,
    }


def highlight_feature(
    image: Image.Image,
    feature_name: str,
    color: tuple[int, int, int] = (255, 0, 0),
    alpha: float = 0.5,
) -> Image.Image:
    """Highlight a feature in the image with a color overlay.

    Args:
        image: CAD model image
        feature_name: Name of feature to highlight
        color: RGB color for highlight
        alpha: Transparency (0-1)

    Returns:
        Image with highlighted feature
    """
    result = segment_feature_by_name(image, feature_name)

    if not result["found"]:
        return image

    # Create colored overlay
    mask = result["mask"].convert("L")
    mask_array = np.array(mask)

    # Create RGBA image
    image_rgba = image.convert("RGBA")
    image_array = np.array(image_rgba)

    # Create overlay
    overlay = np.zeros_like(image_array)
    overlay[..., 0] = color[0]
    overlay[..., 1] = color[1]
    overlay[..., 2] = color[2]
    overlay[..., 3] = (mask_array * alpha).astype(np.uint8)

    # Composite
    from PIL import Image as PILImage
    overlay_img = PILImage.fromarray(overlay, mode="RGBA")
    result_img = PILImage.alpha_composite(image_rgba, overlay_img)

    return result_img.convert("RGB")


def compare_masks(
    mask1: Image.Image,
    mask2: Image.Image,
) -> dict[str, float]:
    """Compare two segmentation masks.

    Args:
        mask1: First mask
        mask2: Second mask

    Returns:
        Dict with 'iou', 'dice', 'overlap_percent'
    """
    arr1 = np.array(mask1.convert("L")) > 127
    arr2 = np.array(mask2.convert("L")) > 127

    intersection = np.logical_and(arr1, arr2).sum()
    union = np.logical_or(arr1, arr2).sum()

    iou = intersection / union if union > 0 else 0
    dice = 2 * intersection / (arr1.sum() + arr2.sum()) if (arr1.sum() + arr2.sum()) > 0 else 0

    return {
        "iou": float(iou),
        "dice": float(dice),
        "overlap_percent": float(intersection / arr1.sum() * 100) if arr1.sum() > 0 else 0,
    }
