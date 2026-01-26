#!/usr/bin/env python3
"""View the combined truck + chair scene."""
import gradio as gr
from pathlib import Path

SCENE_GLB = "data/trellis/outputs/truck_with_chair.glb"

def create_interface():
    with gr.Blocks(title="Truck with Chair") as demo:
        gr.Markdown("# Chair on Flatbed Truck")
        gr.Markdown("3D scene: wooden dining chair placed on the back of a flatbed truck")

        model = gr.Model3D(
            value=SCENE_GLB,
            label="3D Scene (drag to rotate, scroll to zoom)",
            height=600,
        )

        gr.Markdown("---")
        gr.File(value=SCENE_GLB, label="Download GLB")

    return demo

if __name__ == "__main__":
    demo = create_interface()
    demo.launch(server_name="0.0.0.0", server_port=7862)
