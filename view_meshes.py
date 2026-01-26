#!/usr/bin/env python3
"""Simple viewer for generated 3D meshes and their source images."""
import gradio as gr
from pathlib import Path

# Paths
DIFFUSION_OUTPUT = Path("data/diffusion/outputs")
TRELLIS_OUTPUT = Path("data/trellis/outputs")

# Our 4 household objects - matched by visual inspection
OBJECTS = [
    {
        "name": "Coffee Mug",
        "image": "generated_00007_.png",  # White ceramic mug
        "mesh_glb": "mesh_1769221791565.glb",
        "mesh_obj": "mesh_1769221791565.obj",
        "prompt": "a white ceramic coffee mug with a handle, simple design",
    },
    {
        "name": "Wooden Chair",
        "image": "generated_00008_.png",  # Wooden dining chair
        "mesh_glb": "mesh_1769221942704.glb",
        "mesh_obj": "mesh_1769221942704.obj",
        "prompt": "a simple wooden dining chair, four legs, flat seat",
    },
    {
        "name": "Table Lamp",
        "image": "generated_00009_.png",  # Table lamp with white shade
        "mesh_glb": "mesh_1769222057462.glb",
        "mesh_obj": "mesh_1769222057462.obj",
        "prompt": "a modern table lamp with cylindrical white lampshade",
    },
    {
        "name": "Ceramic Vase",
        "image": "generated_00010_.png",  # Blue ceramic vase
        "mesh_glb": "mesh_1769222202033.glb",
        "mesh_obj": "mesh_1769222202033.obj",
        "prompt": "a ceramic flower vase, tall elegant curved shape, light blue",
    },
]


def get_object_info(obj_name: str) -> tuple:
    """Get info for selected object."""
    obj = next((o for o in OBJECTS if o["name"] == obj_name), None)
    if not obj:
        return None, "Object not found", "", ""

    img_path = DIFFUSION_OUTPUT / obj["image"]
    glb_path = TRELLIS_OUTPUT / obj["mesh_glb"]
    obj_path = TRELLIS_OUTPUT / obj["mesh_obj"]

    info = f"""### {obj['name']}

**Prompt:** {obj['prompt']}

**Files:**
- GLB: `{glb_path}` ({glb_path.stat().st_size / 1024 / 1024:.1f} MB)
- OBJ: `{obj_path}` ({obj_path.stat().st_size / 1024 / 1024:.1f} MB)
"""

    return (
        str(img_path) if img_path.exists() else None,
        info,
        str(glb_path) if glb_path.exists() else "",
        str(obj_path) if obj_path.exists() else "",
    )


def create_interface():
    """Create Gradio interface."""
    with gr.Blocks(title="Generated Household Objects") as demo:
        gr.Markdown("# Generated 3D Household Objects")
        gr.Markdown("Generated using ComfyUI (text-to-image) + TRELLIS.2 (image-to-3D)")

        with gr.Row():
            with gr.Column(scale=1):
                obj_dropdown = gr.Dropdown(
                    choices=[o["name"] for o in OBJECTS],
                    value=OBJECTS[0]["name"],
                    label="Select Object",
                )
                info_md = gr.Markdown()
                glb_file = gr.File(label="Download GLB")
                obj_file = gr.File(label="Download OBJ")

            with gr.Column(scale=2):
                image = gr.Image(label="Generated Source Image", height=512)

        # Gallery of all images
        gr.Markdown("---")
        gr.Markdown("### All Generated Objects")

        gallery_images = []
        for obj in OBJECTS:
            img_path = DIFFUSION_OUTPUT / obj["image"]
            if img_path.exists():
                gallery_images.append((str(img_path), obj["name"]))

        gallery = gr.Gallery(
            value=gallery_images,
            label="Source Images",
            columns=4,
            height=300,
        )

        # 3D Model viewer using Model3D component
        gr.Markdown("---")
        gr.Markdown("### 3D Model Viewer")
        model_viewer = gr.Model3D(
            label="3D Model (GLB)",
            height=500,
        )

        def update_display(obj_name):
            img, info, glb, obj_path = get_object_info(obj_name)
            return img, info, glb if glb else None, obj_path if obj_path else None, glb if glb else None

        obj_dropdown.change(
            update_display,
            inputs=[obj_dropdown],
            outputs=[image, info_md, glb_file, obj_file, model_viewer],
        )

        # Initial load
        demo.load(
            update_display,
            inputs=[obj_dropdown],
            outputs=[image, info_md, glb_file, obj_file, model_viewer],
        )

    return demo


if __name__ == "__main__":
    demo = create_interface()
    demo.launch(server_name="0.0.0.0", server_port=7861)
