"""Segmentation pipeline combining SAM and VLM with colorization.

This module provides:
- Multi-region segmentation using point-based SAM
- Semantic colorization of segmented regions
- Color legend generation
- Combined SAM + VLM analysis pipelines
- Automatic service management
"""

import colorsys
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .docker_client import DockerClient
from .inference_client import InferenceClient, get_inference_client

logger = logging.getLogger(__name__)


# Distinct colors for segmentation (colorblind-friendly palette)
SEGMENT_COLORS = [
    (230, 25, 75),    # Red
    (60, 180, 75),    # Green
    (255, 225, 25),   # Yellow
    (0, 130, 200),    # Blue
    (245, 130, 48),   # Orange
    (145, 30, 180),   # Purple
    (70, 240, 240),   # Cyan
    (240, 50, 230),   # Magenta
    (210, 245, 60),   # Lime
    (250, 190, 212),  # Pink
    (0, 128, 128),    # Teal
    (220, 190, 255),  # Lavender
    (170, 110, 40),   # Brown
    (255, 250, 200),  # Beige
    (128, 0, 0),      # Maroon
    (170, 255, 195),  # Mint
]


@dataclass
class SegmentedRegion:
    """A segmented region with its mask and metadata."""

    mask: Image.Image
    color: tuple[int, int, int]
    label: str
    confidence: float
    area_pixels: int
    area_percent: float
    center: tuple[int, int]
    source_point: tuple[int, int] | None = None


@dataclass
class SegmentationResult:
    """Complete segmentation result with all regions."""

    original_image: Image.Image
    colorized_image: Image.Image
    legend_image: Image.Image | None
    combined_image: Image.Image  # Original + colorized + legend
    regions: list[SegmentedRegion] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ServiceManager:
    """Manages inference service lifecycle for segmentation operations."""

    def __init__(self):
        self.docker = DockerClient()
        self._inference_client: InferenceClient | None = None

    def ensure_inference_running(self, timeout: int = 120) -> bool:
        """Ensure inference container is running.

        Args:
            timeout: Maximum wait time in seconds

        Returns:
            True if service is ready
        """
        statuses = self.docker.get_service_status("inference")

        # Check if inference service is in the list and running
        is_running = False
        for status in statuses:
            if status.name == "inference" and status.running:
                is_running = True
                break

        if is_running:
            logger.info("Inference service already running")
            return self._wait_for_ready(timeout=30)

        logger.info("Starting inference service...")
        result = self.docker.start_service("inference", timeout=timeout)

        if not result.get("success"):
            raise RuntimeError(f"Failed to start inference: {result.get('error')}")

        return self._wait_for_ready(timeout=timeout)

    def _wait_for_ready(self, timeout: int = 60) -> bool:
        """Wait for inference service to be ready."""
        client = self.get_client()
        start = time.time()

        while time.time() - start < timeout:
            try:
                if client.ping():
                    return True
            except Exception:
                pass
            time.sleep(2)

        return False

    def get_client(self) -> InferenceClient:
        """Get inference client, creating if needed."""
        if self._inference_client is None:
            self._inference_client = get_inference_client()
        return self._inference_client

    def ensure_sam_loaded(self) -> bool:
        """Ensure SAM model is loaded."""
        client = self.get_client()
        status = client.get_status()

        if not status.get("sam_loaded"):
            logger.info("Loading SAM model...")
            return client.load_sam()
        return True

    def ensure_vlm_loaded(self) -> bool:
        """Ensure VLM model is loaded."""
        client = self.get_client()
        status = client.get_status()

        if not status.get("vlm_loaded"):
            logger.info("Loading VLM model...")
            return client.load_vlm()
        return True

    def unload_sam(self) -> bool:
        """Unload SAM to free GPU memory."""
        return self.get_client().unload_sam()

    def unload_vlm(self) -> bool:
        """Unload VLM to free GPU memory."""
        return self.get_client().unload_vlm()


class SegmentationPipeline:
    """Pipeline for semantic segmentation with colorization."""

    def __init__(self, auto_manage_services: bool = True):
        """Initialize pipeline.

        Args:
            auto_manage_services: Automatically start/manage inference services
        """
        self.auto_manage = auto_manage_services
        self.service_manager = ServiceManager() if auto_manage_services else None
        self._client: InferenceClient | None = None

    def _get_client(self) -> InferenceClient:
        """Get inference client."""
        if self.service_manager:
            return self.service_manager.get_client()
        if self._client is None:
            self._client = get_inference_client()
        return self._client

    def _ensure_ready(self, need_sam: bool = True, need_vlm: bool = False):
        """Ensure required services are ready."""
        if not self.service_manager:
            return

        self.service_manager.ensure_inference_running()

        if need_sam:
            self.service_manager.ensure_sam_loaded()
        if need_vlm:
            self.service_manager.ensure_vlm_loaded()

    def segment_grid(
        self,
        image: Image.Image,
        grid_size: int = 5,
        min_area_percent: float = 1.0,
        merge_similar: bool = True,
        similarity_threshold: float = 0.7,
    ) -> SegmentationResult:
        """Segment image using a grid of sample points.

        Args:
            image: Input image
            grid_size: Number of points per dimension (grid_size x grid_size)
            min_area_percent: Minimum region area as percentage of image
            merge_similar: Merge similar overlapping regions
            similarity_threshold: IoU threshold for merging

        Returns:
            SegmentationResult with all detected regions
        """
        self._ensure_ready(need_sam=True)
        client = self._get_client()

        width, height = image.size
        regions: list[SegmentedRegion] = []
        used_masks: list[np.ndarray] = []

        # Generate grid points
        x_step = width // (grid_size + 1)
        y_step = height // (grid_size + 1)

        color_idx = 0

        for i in range(1, grid_size + 1):
            for j in range(1, grid_size + 1):
                x = i * x_step
                y = j * y_step

                try:
                    result = client.segment_point(image, (x, y), foreground=True)
                    mask = result["mask"]
                    mask_array = np.array(mask.convert("L"))
                    binary_mask = mask_array > 127

                    # Calculate area
                    area = np.sum(binary_mask)
                    area_percent = (area / binary_mask.size) * 100

                    if area_percent < min_area_percent:
                        continue

                    # Check if this region overlaps significantly with existing ones
                    is_new = True
                    if merge_similar and used_masks:
                        for existing_mask in used_masks:
                            iou = self._calculate_iou(binary_mask, existing_mask)
                            if iou > similarity_threshold:
                                is_new = False
                                break

                    if is_new:
                        # Find center of mass
                        y_coords, x_coords = np.where(binary_mask)
                        center_x = int(np.mean(x_coords)) if len(x_coords) > 0 else x
                        center_y = int(np.mean(y_coords)) if len(y_coords) > 0 else y

                        color = SEGMENT_COLORS[color_idx % len(SEGMENT_COLORS)]

                        region = SegmentedRegion(
                            mask=mask,
                            color=color,
                            label=f"Region {color_idx + 1}",
                            confidence=result["score"],
                            area_pixels=int(area),
                            area_percent=area_percent,
                            center=(center_x, center_y),
                            source_point=(x, y),
                        )
                        regions.append(region)
                        used_masks.append(binary_mask)
                        color_idx += 1

                except Exception as e:
                    logger.warning(f"Segmentation failed at ({x}, {y}): {e}")
                    continue

        # Create colorized image
        colorized = self._colorize_regions(image, regions)

        # Create legend
        legend = self._create_legend(regions, height)

        # Create combined image
        combined = self._create_combined_image(image, colorized, legend)

        return SegmentationResult(
            original_image=image,
            colorized_image=colorized,
            legend_image=legend,
            combined_image=combined,
            regions=regions,
            metadata={
                "grid_size": grid_size,
                "num_regions": len(regions),
                "min_area_percent": min_area_percent,
            }
        )

    def segment_points(
        self,
        image: Image.Image,
        points: list[tuple[int, int]],
        labels: list[str] | None = None,
    ) -> SegmentationResult:
        """Segment image at specific points.

        Args:
            image: Input image
            points: List of (x, y) points to segment at
            labels: Optional labels for each point

        Returns:
            SegmentationResult with regions for each point
        """
        self._ensure_ready(need_sam=True)
        client = self._get_client()

        regions: list[SegmentedRegion] = []

        for idx, point in enumerate(points):
            try:
                result = client.segment_point(image, point, foreground=True)
                mask = result["mask"]
                mask_array = np.array(mask.convert("L"))
                binary_mask = mask_array > 127

                area = np.sum(binary_mask)
                area_percent = (area / binary_mask.size) * 100

                # Find center
                y_coords, x_coords = np.where(binary_mask)
                center_x = int(np.mean(x_coords)) if len(x_coords) > 0 else point[0]
                center_y = int(np.mean(y_coords)) if len(y_coords) > 0 else point[1]

                color = SEGMENT_COLORS[idx % len(SEGMENT_COLORS)]
                label = labels[idx] if labels and idx < len(labels) else f"Region {idx + 1}"

                region = SegmentedRegion(
                    mask=mask,
                    color=color,
                    label=label,
                    confidence=result["score"],
                    area_pixels=int(area),
                    area_percent=area_percent,
                    center=(center_x, center_y),
                    source_point=point,
                )
                regions.append(region)

            except Exception as e:
                logger.warning(f"Segmentation failed at {point}: {e}")
                continue

        colorized = self._colorize_regions(image, regions)
        legend = self._create_legend(regions, image.height)
        combined = self._create_combined_image(image, colorized, legend)

        return SegmentationResult(
            original_image=image,
            colorized_image=colorized,
            legend_image=legend,
            combined_image=combined,
            regions=regions,
            metadata={"num_points": len(points), "num_regions": len(regions)}
        )

    def colorize_mask(
        self,
        image: Image.Image,
        mask: Image.Image,
        color: tuple[int, int, int],
        alpha: float = 0.5,
    ) -> Image.Image:
        """Apply color overlay to masked region.

        Args:
            image: Original image
            mask: Binary mask (white = region)
            color: RGB color for overlay
            alpha: Transparency (0-1)

        Returns:
            Image with colored overlay
        """
        mask_array = np.array(mask.convert("L"))
        binary_mask = (mask_array > 127).astype(np.uint8)

        # Create RGBA image
        rgba = image.convert("RGBA")
        rgba_array = np.array(rgba)

        # Create overlay
        overlay = np.zeros_like(rgba_array)
        overlay[..., 0] = color[0]
        overlay[..., 1] = color[1]
        overlay[..., 2] = color[2]
        overlay[..., 3] = (binary_mask * int(255 * alpha)).astype(np.uint8)

        # Composite
        overlay_img = Image.fromarray(overlay, mode="RGBA")
        result = Image.alpha_composite(rgba, overlay_img)

        return result.convert("RGB")

    def _colorize_regions(
        self,
        image: Image.Image,
        regions: list[SegmentedRegion],
        alpha: float = 0.5,
    ) -> Image.Image:
        """Apply color overlay for all regions."""
        result = image.convert("RGBA")

        for region in regions:
            mask_array = np.array(region.mask.convert("L"))
            binary_mask = (mask_array > 127).astype(np.uint8)

            overlay = np.zeros((*mask_array.shape, 4), dtype=np.uint8)
            overlay[..., 0] = region.color[0]
            overlay[..., 1] = region.color[1]
            overlay[..., 2] = region.color[2]
            overlay[..., 3] = (binary_mask * int(255 * alpha)).astype(np.uint8)

            overlay_img = Image.fromarray(overlay, mode="RGBA")
            result = Image.alpha_composite(result, overlay_img)

        return result.convert("RGB")

    def _create_legend(
        self,
        regions: list[SegmentedRegion],
        image_height: int,
        width: int = 200,
    ) -> Image.Image:
        """Create a color legend for the regions."""
        if not regions:
            return Image.new("RGB", (width, image_height), (255, 255, 255))

        # Calculate dimensions
        item_height = 40
        padding = 10
        total_height = max(len(regions) * item_height + 2 * padding, image_height)

        legend = Image.new("RGB", (width, total_height), (255, 255, 255))
        draw = ImageDraw.Draw(legend)

        # Try to load a font, fall back to default
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        except Exception:
            font = ImageFont.load_default()

        y = padding
        for region in regions:
            # Draw color box
            box_size = 20
            draw.rectangle(
                [padding, y, padding + box_size, y + box_size],
                fill=region.color,
                outline=(0, 0, 0),
            )

            # Draw label and area
            text = f"{region.label}"
            area_text = f"({region.area_percent:.1f}%)"
            draw.text((padding + box_size + 10, y), text, fill=(0, 0, 0), font=font)
            draw.text((padding + box_size + 10, y + 18), area_text, fill=(100, 100, 100), font=font)

            y += item_height

        return legend

    def _create_combined_image(
        self,
        original: Image.Image,
        colorized: Image.Image,
        legend: Image.Image | None,
    ) -> Image.Image:
        """Create combined image with original, colorized, and legend."""
        width = original.width
        height = original.height

        # Calculate total width
        legend_width = legend.width if legend else 0
        total_width = width * 2 + legend_width + 20  # 20px spacing

        combined = Image.new("RGB", (total_width, height), (240, 240, 240))

        # Paste original
        combined.paste(original, (0, 0))

        # Paste colorized
        combined.paste(colorized, (width + 10, 0))

        # Paste legend
        if legend:
            # Resize legend to match image height
            legend_resized = legend.resize((legend_width, height), Image.Resampling.LANCZOS)
            combined.paste(legend_resized, (width * 2 + 20, 0))

        return combined

    def _calculate_iou(self, mask1: np.ndarray, mask2: np.ndarray) -> float:
        """Calculate Intersection over Union between two masks."""
        intersection = np.logical_and(mask1, mask2).sum()
        union = np.logical_or(mask1, mask2).sum()
        return intersection / union if union > 0 else 0


class SegmentAndAnalyzePipeline:
    """Combined SAM segmentation + VLM analysis pipeline."""

    def __init__(self, auto_manage_services: bool = True):
        """Initialize combined pipeline.

        Args:
            auto_manage_services: Automatically manage inference services
        """
        self.segmentation = SegmentationPipeline(auto_manage_services)
        self.service_manager = self.segmentation.service_manager

    def segment_and_analyze(
        self,
        image: Image.Image,
        question: str | None = None,
        grid_size: int = 5,
        analyze_colorized: bool = True,
    ) -> dict[str, Any]:
        """Segment image and analyze with VLM.

        Args:
            image: Input image
            question: Question for VLM (default: describe the segmented regions)
            grid_size: Grid size for segmentation
            analyze_colorized: Use colorized image for VLM (vs original)

        Returns:
            Dict with segmentation result and VLM analysis
        """
        # Ensure both SAM and VLM are ready
        if self.service_manager:
            self.service_manager.ensure_inference_running()
            self.service_manager.ensure_sam_loaded()

        # Perform segmentation
        seg_result = self.segmentation.segment_grid(image, grid_size=grid_size)

        # Now load VLM (may unload SAM on low-memory systems)
        if self.service_manager:
            self.service_manager.ensure_vlm_loaded()

        # Prepare VLM query
        client = self.segmentation._get_client()

        if question is None:
            # Generate question based on segmentation
            region_desc = ", ".join([
                f"{r.label} ({r.color[0]},{r.color[1]},{r.color[2]} color, {r.area_percent:.1f}% area)"
                for r in seg_result.regions
            ])
            question = (
                f"This image has been segmented into colored regions. "
                f"The regions are: {region_desc}. "
                f"Describe what each colored region represents and "
                f"how they relate to each other in this 3D model."
            )

        # Analyze with VLM
        analysis_image = seg_result.colorized_image if analyze_colorized else image
        vlm_result = client.analyze_image(analysis_image, question)

        return {
            "segmentation": seg_result,
            "vlm_response": vlm_result["response"],
            "vlm_thinking": vlm_result.get("thinking"),
            "question": question,
            "num_regions": len(seg_result.regions),
        }

    def analyze_specific_regions(
        self,
        image: Image.Image,
        points: list[tuple[int, int]],
        labels: list[str],
        question: str | None = None,
    ) -> dict[str, Any]:
        """Segment specific regions and analyze.

        Args:
            image: Input image
            points: Points to segment at
            labels: Labels for each region
            question: Question for VLM

        Returns:
            Dict with segmentation and analysis
        """
        if self.service_manager:
            self.service_manager.ensure_inference_running()
            self.service_manager.ensure_sam_loaded()

        seg_result = self.segmentation.segment_points(image, points, labels)

        if self.service_manager:
            self.service_manager.ensure_vlm_loaded()

        client = self.segmentation._get_client()

        if question is None:
            label_desc = ", ".join(labels)
            question = (
                f"This image shows a 3D model with highlighted regions: {label_desc}. "
                f"Each region is shown in a different color. "
                f"Describe the relationship between these components and "
                f"assess if the assembly looks correct."
            )

        vlm_result = client.analyze_image(seg_result.colorized_image, question)

        return {
            "segmentation": seg_result,
            "vlm_response": vlm_result["response"],
            "vlm_thinking": vlm_result.get("thinking"),
            "question": question,
            "labels": labels,
        }

    def identify_and_segment(
        self,
        image: Image.Image,
        grid_size: int = 5,
    ) -> dict[str, Any]:
        """First use VLM to identify features, then segment them.

        Args:
            image: Input image
            grid_size: Grid size for initial segmentation

        Returns:
            Dict with identified features and segmentation
        """
        if self.service_manager:
            self.service_manager.ensure_inference_running()

        # First, ask VLM to identify interesting points
        if self.service_manager:
            self.service_manager.ensure_vlm_loaded()

        client = self.segmentation._get_client()

        # Get feature identification
        identify_prompt = (
            "Identify the main components or features in this 3D model. "
            "For each feature, describe it and estimate its approximate position "
            "in the image as (x%, y%) from top-left. "
            "List up to 5 most important features."
        )

        identify_result = client.analyze_image(image, identify_prompt)

        # Now do grid segmentation
        if self.service_manager:
            self.service_manager.ensure_sam_loaded()

        seg_result = self.segmentation.segment_grid(image, grid_size=grid_size)

        # Re-analyze with colorized version
        if self.service_manager:
            self.service_manager.ensure_vlm_loaded()

        analysis_prompt = (
            "The image has been segmented into colored regions. "
            "Match the previously identified features to the colored regions "
            "and provide a detailed analysis of each component."
        )

        analysis_result = client.analyze_image(seg_result.colorized_image, analysis_prompt)

        return {
            "initial_identification": identify_result["response"],
            "segmentation": seg_result,
            "detailed_analysis": analysis_result["response"],
            "vlm_thinking": analysis_result.get("thinking"),
        }


def generate_distinct_colors(n: int) -> list[tuple[int, int, int]]:
    """Generate n visually distinct colors.

    Args:
        n: Number of colors needed

    Returns:
        List of RGB tuples
    """
    colors = []
    for i in range(n):
        # Use golden ratio to space hues evenly
        hue = (i * 0.618033988749895) % 1.0
        saturation = 0.7 + (i % 3) * 0.1  # Vary saturation slightly
        value = 0.9 - (i % 2) * 0.1  # Vary brightness slightly

        r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
        colors.append((int(r * 255), int(g * 255), int(b * 255)))

    return colors


def create_annotation_image(
    image: Image.Image,
    regions: list[SegmentedRegion],
    show_labels: bool = True,
    show_centers: bool = True,
) -> Image.Image:
    """Create annotated image with region labels and centers.

    Args:
        image: Base image
        regions: Segmented regions
        show_labels: Show text labels
        show_centers: Show center markers

    Returns:
        Annotated image
    """
    annotated = image.copy()
    draw = ImageDraw.Draw(annotated)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    except Exception:
        font = ImageFont.load_default()

    for region in regions:
        cx, cy = region.center

        if show_centers:
            # Draw crosshair
            size = 10
            draw.line([(cx - size, cy), (cx + size, cy)], fill=region.color, width=2)
            draw.line([(cx, cy - size), (cx, cy + size)], fill=region.color, width=2)

            # Draw circle
            draw.ellipse(
                [(cx - 5, cy - 5), (cx + 5, cy + 5)],
                outline=region.color,
                width=2,
            )

        if show_labels:
            # Draw label with background
            text = region.label
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # Position label below center
            label_x = cx - text_width // 2
            label_y = cy + 15

            # Draw background rectangle
            padding = 2
            draw.rectangle(
                [label_x - padding, label_y - padding,
                 label_x + text_width + padding, label_y + text_height + padding],
                fill=(255, 255, 255, 200),
                outline=region.color,
            )

            # Draw text
            draw.text((label_x, label_y), text, fill=(0, 0, 0), font=font)

    return annotated
