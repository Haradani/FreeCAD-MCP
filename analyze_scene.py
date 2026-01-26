#!/usr/bin/env python3
"""Scene analyzer with VLM and SAM3 integration."""
import gradio as gr
import numpy as np
from pathlib import Path
from PIL import Image
import io
import base64
import time

import os

from src.inference_client import InferenceClient

# Initialize inference client
inference = InferenceClient(host="localhost", port=5555)

# Scene viewer URL - set via environment variable or use default local URL
SCENE_VIEWER_URL = os.environ.get("SCENE_VIEWER_URL", "http://localhost:7865")
SCENE_GLB = "data/trellis/outputs/truck_with_chair.glb"


def capture_scene_frame(angle: int = 0) -> Image.Image | None:
    """Capture a frame of the 3D scene at a given rotation angle.

    Uses playwright to render the scene and capture a screenshot.
    """
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={'width': 800, 'height': 600})
            page = context.new_page()

            # Load the scene viewer
            page.goto(SCENE_VIEWER_URL, wait_until='networkidle')
            page.wait_for_timeout(5000)

            # Try to rotate the 3D model by simulating mouse drag
            # The Model3D component uses mouse drag to rotate
            canvas = page.locator('canvas').first
            if canvas:
                box = canvas.bounding_box()
                if box:
                    center_x = box['x'] + box['width'] / 2
                    center_y = box['y'] + box['height'] / 2

                    # Simulate drag to rotate based on angle
                    drag_x = 100 * np.sin(np.radians(angle))
                    page.mouse.move(center_x, center_y)
                    page.mouse.down()
                    page.mouse.move(center_x + drag_x, center_y)
                    page.mouse.up()
                    page.wait_for_timeout(500)

            # Capture screenshot
            screenshot = page.screenshot()
            context.close()
            browser.close()

            return Image.open(io.BytesIO(screenshot))
    except Exception as e:
        print(f"Frame capture failed: {e}")
        return None


def analyze_with_vlm(image: Image.Image, question: str) -> tuple[str, str | None]:
    """Analyze image with VLM.

    Returns:
        Tuple of (response, thinking)
    """
    try:
        result = inference.analyze_image(image, question, max_tokens=512)
        return result.get("response", "No response"), result.get("thinking")
    except Exception as e:
        return f"VLM Error: {str(e)}", None


def segment_object(image: Image.Image, description: str) -> tuple[Image.Image | None, str]:
    """Segment an object using SAM3.

    Returns:
        Tuple of (highlighted_image, info_message)
    """
    try:
        result = inference.segment_text(image, description)
        mask = result.get("mask")
        regions = result.get("regions", [])

        if mask is None:
            return None, f"No '{description}' found in image"

        # Create highlighted image by overlaying mask
        img_array = np.array(image)
        mask_array = np.array(mask.convert('L'))

        # Create red highlight overlay
        highlight = img_array.copy()
        mask_bool = mask_array > 128
        highlight[mask_bool] = highlight[mask_bool] * 0.5 + np.array([255, 0, 0]) * 0.5

        highlighted = Image.fromarray(highlight.astype(np.uint8))
        return highlighted, f"Found {len(regions)} region(s) for '{description}'"
    except Exception as e:
        return None, f"SAM Error: {str(e)}"


def full_scene_analysis(question: str = "Is the chair loaded on the back of the truck?") -> tuple[str, list, str]:
    """Capture multiple views and analyze with VLM.

    Returns:
        Tuple of (analysis_result, gallery_images, progress_log)
    """
    log_lines = []
    gallery = []

    log_lines.append("Starting scene analysis...")

    # Capture frames at different angles
    angles = [0, 45, 90, 135, 180]
    frames = []

    for i, angle in enumerate(angles):
        log_lines.append(f"Capturing frame at {angle} degrees...")
        frame = capture_scene_frame(angle)
        if frame:
            frames.append((frame, f"View at {angle}°"))
            gallery.append((frame, f"{angle}°"))

    if not frames:
        return "Failed to capture any frames", gallery, "\n".join(log_lines)

    log_lines.append(f"Captured {len(frames)} frames")
    log_lines.append(f"Analyzing with VLM: '{question}'")

    # Analyze the best frame (front view)
    best_frame = frames[0][0]
    response, thinking = analyze_with_vlm(best_frame, question)

    log_lines.append("Analysis complete!")

    result = f"**Question:** {question}\n\n**Answer:** {response}"
    if thinking:
        result += f"\n\n**Reasoning:** {thinking}"

    return result, gallery, "\n".join(log_lines)


def quick_analyze(image: Image.Image, question: str) -> str:
    """Quick analyze an uploaded image."""
    if image is None:
        return "Please upload an image first"

    response, thinking = analyze_with_vlm(image, question)
    result = f"**Answer:** {response}"
    if thinking:
        result += f"\n\n**Reasoning:** {thinking}"
    return result


def highlight_and_ask(image: Image.Image, object_desc: str, question: str) -> tuple[Image.Image | None, str]:
    """Highlight object with SAM and ask VLM about it."""
    if image is None:
        return None, "Please upload an image first"

    # First segment the object
    highlighted, seg_info = segment_object(image, object_desc)

    if highlighted is None:
        return image, seg_info

    # Ask VLM about the highlighted object
    full_question = f"Looking at the highlighted (red) {object_desc}: {question}"
    response, thinking = analyze_with_vlm(highlighted, full_question)

    result = f"**Segmentation:** {seg_info}\n\n**Question:** {question}\n\n**Answer:** {response}"
    if thinking:
        result += f"\n\n**Reasoning:** {thinking}"

    return highlighted, result


def check_inference_status() -> str:
    """Check VLM and SAM status."""
    try:
        status = inference.get_status()
        vlm_loaded = status.get("vlm_loaded", False)
        sam_loaded = status.get("sam_loaded", False)
        gpu_count = status.get("gpu_count", 0)

        return f"""**Inference Status:**
- GPUs: {gpu_count}
- VLM Loaded: {'Yes' if vlm_loaded else 'No'}
- SAM Loaded: {'Yes' if sam_loaded else 'No'}
"""
    except Exception as e:
        return f"Failed to get status: {e}"


def load_models() -> str:
    """Load VLM and SAM models."""
    try:
        vlm_ok = inference.load_vlm()
        sam_ok = inference.load_sam()
        return f"VLM: {'Loaded' if vlm_ok else 'Failed'}, SAM: {'Loaded' if sam_ok else 'Failed'}"
    except Exception as e:
        return f"Error loading models: {e}"


def create_interface():
    """Create the Gradio interface."""
    with gr.Blocks(title="Scene Analyzer with VLM + SAM") as demo:
        gr.Markdown("# 3D Scene Analyzer")
        gr.Markdown("Analyze 3D scenes using Vision Language Model (VLM) and Segment Anything (SAM3)")

        with gr.Row():
            status_btn = gr.Button("Check Status")
            load_btn = gr.Button("Load Models")
            status_text = gr.Textbox(label="Status", interactive=False)

        status_btn.click(check_inference_status, outputs=status_text)
        load_btn.click(load_models, outputs=status_text)

        with gr.Tab("Full Scene Analysis"):
            gr.Markdown("Capture multiple views of the truck+chair scene and analyze")

            scene_question = gr.Textbox(
                value="Is the chair loaded on the back of the truck? Describe its position.",
                label="Question"
            )
            analyze_btn = gr.Button("Analyze Scene", variant="primary")

            with gr.Row():
                scene_gallery = gr.Gallery(label="Captured Views", columns=5, height=200)

            scene_result = gr.Markdown(label="Analysis Result")
            scene_log = gr.Textbox(label="Progress Log", lines=10)

            analyze_btn.click(
                full_scene_analysis,
                inputs=[scene_question],
                outputs=[scene_result, scene_gallery, scene_log]
            )

        with gr.Tab("Quick Image Analysis"):
            gr.Markdown("Upload any image and ask questions")

            with gr.Row():
                quick_image = gr.Image(type="pil", label="Upload Image")
                quick_question = gr.Textbox(
                    value="Describe what you see in this image.",
                    label="Question"
                )

            quick_btn = gr.Button("Analyze")
            quick_result = gr.Markdown(label="Result")

            quick_btn.click(
                quick_analyze,
                inputs=[quick_image, quick_question],
                outputs=quick_result
            )

        with gr.Tab("Highlight + Ask (SAM + VLM)"):
            gr.Markdown("Segment an object and ask about it specifically")

            with gr.Row():
                sam_image = gr.Image(type="pil", label="Upload Image")
                with gr.Column():
                    object_desc = gr.Textbox(value="chair", label="Object to highlight")
                    sam_question = gr.Textbox(
                        value="What color is this object?",
                        label="Question about the object"
                    )

            sam_btn = gr.Button("Highlight and Ask")

            with gr.Row():
                highlighted_image = gr.Image(label="Highlighted")
                sam_result = gr.Markdown(label="Result")

            sam_btn.click(
                highlight_and_ask,
                inputs=[sam_image, object_desc, sam_question],
                outputs=[highlighted_image, sam_result]
            )

        gr.Markdown("---")
        gr.Markdown("*Using Cosmos-Reason VLM and Segment Anything 3*")

    return demo


if __name__ == "__main__":
    demo = create_interface()
    demo.launch(server_name="0.0.0.0", server_port=7863)
