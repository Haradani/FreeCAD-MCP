#!/usr/bin/env python3
"""Gradio gallery interface for viewing cached images, 3D models, and VLM analyses.

This interface provides a web-based viewer for all content generated during
MCP sessions, including screenshots, segmentation results, and 3D models.
"""

import argparse
import json
import logging
import os
from pathlib import Path
from datetime import datetime

import gradio as gr

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Find cache directory
def get_cache_dir() -> Path:
    """Get the cache directory path."""
    # Check for explicit path first
    if os.environ.get("CACHE_DIR"):
        return Path(os.environ["CACHE_DIR"])

    # Default to cache/ in project root
    project_root = Path(__file__).parent.parent
    return project_root / "cache"


def get_sessions() -> list[dict]:
    """Get all session directories with metadata."""
    cache_dir = get_cache_dir()
    if not cache_dir.exists():
        return []

    sessions = []
    for session_dir in sorted(cache_dir.iterdir(), reverse=True):
        if session_dir.is_dir() and session_dir.name.startswith("session_"):
            # Parse timestamp from name
            try:
                timestamp_str = session_dir.name.replace("session_", "")
                timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")

                # Count files
                file_count = sum(1 for _ in session_dir.rglob("*") if _.is_file())

                # Get size
                size_bytes = sum(f.stat().st_size for f in session_dir.rglob("*") if f.is_file())
                size_mb = size_bytes / (1024 * 1024)

                sessions.append({
                    "name": session_dir.name,
                    "path": str(session_dir),
                    "timestamp": timestamp,
                    "display": f"{timestamp.strftime('%Y-%m-%d %H:%M:%S')} ({file_count} files, {size_mb:.1f} MB)",
                    "file_count": file_count,
                    "size_mb": size_mb,
                })
            except ValueError:
                continue

    return sessions


def get_images_for_session(session_path: str) -> list[tuple[str, str]]:
    """Get all images from a session directory."""
    if not session_path:
        return []

    session_dir = Path(session_path)
    if not session_dir.exists():
        return []

    images = []
    for ext in ["*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp"]:
        for img_path in session_dir.rglob(ext):
            # Create caption from path
            rel_path = img_path.relative_to(session_dir)
            caption = str(rel_path)
            images.append((str(img_path), caption))

    # Sort by modification time (newest first)
    images.sort(key=lambda x: Path(x[0]).stat().st_mtime, reverse=True)
    return images


def get_models_for_session(session_path: str) -> list[dict]:
    """Get all 3D models from a session directory."""
    if not session_path:
        return []

    session_dir = Path(session_path)
    if not session_dir.exists():
        return []

    models = []
    for ext in ["*.glb", "*.gltf", "*.obj", "*.stl", "*.step", "*.stp"]:
        for model_path in session_dir.rglob(ext):
            rel_path = model_path.relative_to(session_dir)
            models.append({
                "path": str(model_path),  # Full absolute path
                "name": model_path.name,
                "rel_path": str(rel_path),
                "size_kb": model_path.stat().st_size / 1024,
            })

    return models


def get_videos_for_session(session_path: str) -> list[dict]:
    """Get all videos from a session directory."""
    if not session_path:
        return []

    session_dir = Path(session_path)
    if not session_dir.exists():
        return []

    videos = []
    for ext in ["*.mp4", "*.webm", "*.mov", "*.avi"]:
        for video_path in session_dir.rglob(ext):
            rel_path = video_path.relative_to(session_dir)
            videos.append({
                "path": str(video_path),
                "name": video_path.name,
                "rel_path": str(rel_path),
                "size_kb": video_path.stat().st_size / 1024,
            })

    # Sort by modification time (newest first)
    videos.sort(key=lambda x: Path(x["path"]).stat().st_mtime, reverse=True)
    return videos


def get_analyses_for_session(session_path: str) -> list[dict]:
    """Get VLM analysis results from a session directory."""
    if not session_path:
        return []

    session_dir = Path(session_path)
    if not session_dir.exists():
        return []

    analyses = []

    # Look for analysis JSON files
    for json_path in session_dir.rglob("*analysis*.json"):
        try:
            with open(json_path) as f:
                data = json.load(f)
                analyses.append({
                    "path": str(json_path),
                    "name": json_path.name,
                    "data": data,
                })
        except (json.JSONDecodeError, IOError):
            continue

    # Look for analysis text files
    for txt_path in session_dir.rglob("*analysis*.txt"):
        try:
            with open(txt_path) as f:
                content = f.read()
                analyses.append({
                    "path": str(txt_path),
                    "name": txt_path.name,
                    "data": {"text": content},
                })
        except IOError:
            continue

    return analyses


def get_all_content() -> dict:
    """Get all content from cache directory (not session-specific)."""
    cache_dir = get_cache_dir()

    # Also check common output directories
    output_dirs = [
        cache_dir,
        Path("/home/paul/freecad_mcp/data/trellis/outputs"),
        Path("/tmp"),
    ]

    images = []
    models = []

    for output_dir in output_dirs:
        if not output_dir.exists():
            continue

        # Get images
        for ext in ["*.png", "*.jpg", "*.jpeg"]:
            for img_path in output_dir.rglob(ext):
                if img_path.stat().st_size > 1000:  # Skip tiny files
                    images.append((str(img_path), img_path.name))

        # Get 3D models
        for ext in ["*.glb", "*.gltf", "*.obj", "*.stl"]:
            for model_path in output_dir.rglob(ext):
                models.append({
                    "path": str(model_path),
                    "name": model_path.name,
                    "size_kb": model_path.stat().st_size / 1024,
                })

    # Sort by modification time
    images.sort(key=lambda x: Path(x[0]).stat().st_mtime, reverse=True)
    models.sort(key=lambda x: Path(x["path"]).stat().st_mtime, reverse=True)

    return {"images": images[:50], "models": models[:20]}  # Limit for performance


def create_gallery_interface():
    """Create the Gradio gallery interface."""

    with gr.Blocks(title="FreeCAD MCP Gallery", theme=gr.themes.Soft()) as app:
        gr.Markdown("# FreeCAD MCP Gallery")
        gr.Markdown("View images, 3D models, and VLM analyses from your sessions")

        with gr.Row():
            with gr.Column(scale=1):
                # Session selector
                sessions = get_sessions()
                session_choices = [(s["display"], s["path"]) for s in sessions]

                session_dropdown = gr.Dropdown(
                    choices=session_choices,
                    label="Select Session",
                    value=session_choices[0][1] if session_choices else None,
                    interactive=True,
                )

                refresh_btn = gr.Button("Refresh Sessions", variant="secondary")

            with gr.Column(scale=2):
                session_info = gr.Markdown("Select a session to view its contents")

        with gr.Tabs() as tabs:
            # Images tab
            with gr.TabItem("Images", id=0):
                image_gallery = gr.Gallery(
                    label="Session Images",
                    columns=4,
                    rows=3,
                    height="auto",
                    object_fit="contain",
                    show_label=False,
                )

                with gr.Row():
                    selected_image = gr.Image(
                        label="Selected Image",
                        height=400,
                        show_label=True,
                    )
                    image_info = gr.Markdown("Click an image to view details")

            # 3D Models tab
            with gr.TabItem("3D Models", id=1):
                with gr.Row():
                    model_dropdown = gr.Dropdown(
                        choices=[],
                        label="Select Model",
                        interactive=True,
                    )
                    load_model_btn = gr.Button("Load Model", variant="primary")

                model_list = gr.Dataframe(
                    headers=["Name", "Path", "Size (KB)"],
                    label="Available Models",
                    interactive=False,
                )

                with gr.Row():
                    model_viewer = gr.Model3D(
                        label="3D Model Viewer",
                        height=500,
                    )
                    model_info = gr.Markdown("Select a model from dropdown and click Load")

            # Videos tab
            with gr.TabItem("Videos", id=2):
                with gr.Row():
                    video_dropdown = gr.Dropdown(
                        choices=[],
                        label="Select Video",
                        interactive=True,
                    )
                    load_video_btn = gr.Button("Load Video", variant="primary")

                video_list = gr.Dataframe(
                    headers=["Name", "Path", "Size (KB)"],
                    label="Available Videos",
                    interactive=False,
                )

                with gr.Row():
                    video_player = gr.Video(
                        label="Video Player",
                        height=400,
                    )
                    video_info = gr.Markdown("Select a video from dropdown and click Load")

            # VLM Analyses tab
            with gr.TabItem("VLM Analyses", id=3):
                analysis_list = gr.Dropdown(
                    choices=[],
                    label="Select Analysis",
                    interactive=True,
                )
                analysis_content = gr.JSON(
                    label="Analysis Content",
                )
                analysis_text = gr.Textbox(
                    label="Analysis Text",
                    lines=10,
                    interactive=False,
                )

            # All Content tab
            with gr.TabItem("All Content", id=4):
                gr.Markdown("### All images and models from cache and output directories")

                all_gallery = gr.Gallery(
                    label="All Images",
                    columns=5,
                    rows=4,
                    height="auto",
                    object_fit="contain",
                )

                all_models = gr.Dataframe(
                    headers=["Name", "Path", "Size (KB)"],
                    label="All 3D Models",
                    interactive=False,
                )

                load_all_btn = gr.Button("Load All Content", variant="primary")

        # Event handlers
        def update_session(session_path):
            if not session_path:
                return [], gr.update(choices=[], value=None), [], gr.update(choices=[], value=None), [], gr.update(choices=[], value=None), "No session selected", []

            images = get_images_for_session(session_path)
            models = get_models_for_session(session_path)
            videos = get_videos_for_session(session_path)
            analyses = get_analyses_for_session(session_path)

            # Format model data for dataframe - include full path for selection
            model_data = [[m["name"], m["path"], f"{m['size_kb']:.1f}"] for m in models]

            # Format model choices for dropdown (name -> path)
            model_choices = [(m["name"], m["path"]) for m in models]
            model_dropdown_update = gr.update(choices=model_choices, value=model_choices[0][1] if model_choices else None)

            # Format video data for dataframe
            video_data = [[v["name"], v["path"], f"{v['size_kb']:.1f}"] for v in videos]

            # Format video choices for dropdown (name -> path)
            video_choices = [(v["name"], v["path"]) for v in videos]
            video_dropdown_update = gr.update(choices=video_choices, value=video_choices[0][1] if video_choices else None)

            # Format analysis choices
            analysis_choices = [(a["name"], a["path"]) for a in analyses]
            analysis_dropdown_update = gr.update(choices=analysis_choices, value=None)

            # Session info
            session_name = Path(session_path).name
            info = f"**Session:** {session_name}\n\n"
            info += f"**Images:** {len(images)} | **Models:** {len(models)} | **Videos:** {len(videos)} | **Analyses:** {len(analyses)}"

            logger.info(f"Session loaded: {len(images)} images, {len(models)} models, {len(videos)} videos, {len(analyses)} analyses")

            return images, model_dropdown_update, model_data, video_dropdown_update, video_data, analysis_dropdown_update, info, analyses

        def refresh_sessions():
            sessions = get_sessions()
            choices = [(s["display"], s["path"]) for s in sessions]
            return gr.Dropdown(choices=choices, value=choices[0][1] if choices else None)

        def select_image(evt: gr.SelectData, gallery):
            if evt.index < len(gallery):
                img_path, caption = gallery[evt.index]
                path = Path(img_path)
                info = f"**File:** {path.name}\n\n"
                info += f"**Path:** `{img_path}`\n\n"
                info += f"**Size:** {path.stat().st_size / 1024:.1f} KB\n\n"
                info += f"**Modified:** {datetime.fromtimestamp(path.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}"
                return img_path, info
            return None, "No image selected"

        def load_model(model_path):
            """Load a model from its path."""
            logger.info(f"load_model called with path: {model_path}")

            if not model_path:
                return None, "No model selected"

            try:
                if Path(model_path).exists():
                    file_size_mb = Path(model_path).stat().st_size / (1024 * 1024)
                    model_name = Path(model_path).name
                    info = f"**Model:** {model_name}\n\n**Path:** `{model_path}`\n\n**Size:** {file_size_mb:.1f} MB"

                    # Note: Large models (>10MB) may take time to load in browser
                    if file_size_mb > 10:
                        info += f"\n\n*Note: Large file ({file_size_mb:.0f} MB), may take time to load in browser*"

                    logger.info(f"Loading model: {model_name} ({file_size_mb:.1f} MB)")
                    return model_path, info
                else:
                    return None, f"Model file not found: {model_path}"
            except Exception as e:
                logger.exception(f"Error loading model: {e}")
                return None, f"Error loading model: {str(e)}"

        def load_video(video_path):
            """Load a video from its path."""
            logger.info(f"load_video called with path: {video_path}")

            if not video_path:
                return None, "No video selected"

            try:
                if Path(video_path).exists():
                    file_size_mb = Path(video_path).stat().st_size / (1024 * 1024)
                    video_name = Path(video_path).name
                    info = f"**Video:** {video_name}\n\n**Path:** `{video_path}`\n\n**Size:** {file_size_mb:.1f} MB"

                    logger.info(f"Loading video: {video_name} ({file_size_mb:.1f} MB)")
                    return video_path, info
                else:
                    return None, f"Video file not found: {video_path}"
            except Exception as e:
                logger.exception(f"Error loading video: {e}")
                return None, f"Error loading video: {str(e)}"

        def load_analysis(analysis_path, analyses_data):
            for a in analyses_data:
                if a["path"] == analysis_path:
                    data = a["data"]
                    text = data.get("text", json.dumps(data, indent=2))
                    return data, text
            return {}, ""

        def load_all_content():
            content = get_all_content()
            model_data = [[m["name"], m["path"], f"{m['size_kb']:.1f}"] for m in content["models"]]
            return content["images"], model_data

        # Store analyses data
        analyses_state = gr.State([])

        # Connect events
        session_dropdown.change(
            update_session,
            inputs=[session_dropdown],
            outputs=[image_gallery, model_dropdown, model_list, video_dropdown, video_list, analysis_list, session_info, analyses_state],
        )

        refresh_btn.click(
            refresh_sessions,
            outputs=[session_dropdown],
        )

        image_gallery.select(
            select_image,
            inputs=[image_gallery],
            outputs=[selected_image, image_info],
        )

        load_model_btn.click(
            load_model,
            inputs=[model_dropdown],
            outputs=[model_viewer, model_info],
        )

        load_video_btn.click(
            load_video,
            inputs=[video_dropdown],
            outputs=[video_player, video_info],
        )

        analysis_list.change(
            load_analysis,
            inputs=[analysis_list, analyses_state],
            outputs=[analysis_content, analysis_text],
        )

        load_all_btn.click(
            load_all_content,
            outputs=[all_gallery, all_models],
        )

        # Auto-load first session on start
        if session_choices:
            app.load(
                update_session,
                inputs=[session_dropdown],
                outputs=[image_gallery, model_dropdown, model_list, video_dropdown, video_list, analysis_list, session_info, analyses_state],
            )

    return app


def main():
    """Run the gallery interface."""
    parser = argparse.ArgumentParser(description="FreeCAD MCP Gallery Interface")
    parser.add_argument("--port", type=int, default=7865, help="Port to run on")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--share", action="store_true", help="Create Gradio share link")
    args = parser.parse_args()

    app = create_gallery_interface()

    logger.info(f"Starting gallery interface on {args.host}:{args.port}")
    app.launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
    )


if __name__ == "__main__":
    main()
