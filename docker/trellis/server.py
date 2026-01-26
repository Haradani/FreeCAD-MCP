"""
TRELLIS.2 Image-to-3D HTTP Server

Provides REST API for converting images to 3D meshes using Microsoft TRELLIS.2-4B.

Endpoints:
    POST /generate - Convert image to 3D mesh
    GET /health - Health check
    GET /status - Model status and GPU info
    POST /load - Explicitly load model
    POST /unload - Unload model to free memory
"""

import argparse
import base64
import io
import json
import logging
import os
import tempfile
import time
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

import torch
from PIL import Image

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Lazy import TRELLIS.2 to avoid loading until needed
pipeline = None


def get_best_gpu() -> str:
    """Select GPU with most free memory."""
    if not torch.cuda.is_available():
        return "cpu"

    device = os.environ.get("TRELLIS_DEVICE", "auto")
    if device != "auto":
        return device

    num_gpus = torch.cuda.device_count()
    if num_gpus == 1:
        return "cuda:0"

    # Find GPU with most free memory
    best_gpu = 0
    best_free = 0
    for i in range(num_gpus):
        free, total = torch.cuda.mem_get_info(i)
        if free > best_free:
            best_free = free
            best_gpu = i

    logger.info(f"Selected GPU {best_gpu} with {best_free / 1024**3:.1f} GB free")
    return f"cuda:{best_gpu}"


def load_pipeline():
    """Load TRELLIS.2 pipeline (lazy loading)."""
    global pipeline
    if pipeline is not None:
        return pipeline

    logger.info("Loading TRELLIS.2-4B pipeline...")
    start = time.time()

    try:
        from trellis2.pipelines import Trellis2ImageTo3DPipeline
        from trellis2.pipelines import rembg
        from transformers import AutoModelForImageSegmentation, PreTrainedModel

        # Patch PreTrainedModel to handle the all_tied_weights_keys getter/setter issue
        # The breaking change in transformers main tries to:
        # 1. SET all_tied_weights_keys in post_init (but it's a property)
        # 2. GET all_tied_weights_keys.keys() in mark_tied_weights_as_initialized

        original_mark_tied = PreTrainedModel.mark_tied_weights_as_initialized
        def patched_mark_tied_weights(self):
            if not hasattr(self, '_all_tied_weights_keys'):
                object.__setattr__(self, '_all_tied_weights_keys', {})
            return original_mark_tied(self)
        PreTrainedModel.mark_tied_weights_as_initialized = patched_mark_tied_weights

        original_post_init = PreTrainedModel.post_init
        def patched_post_init(model_self):
            if not hasattr(model_self, '_all_tied_weights_keys'):
                object.__setattr__(model_self, '_all_tied_weights_keys', {})
            if not hasattr(model_self, '_tied_weights_keys'):
                object.__setattr__(model_self, '_tied_weights_keys', [])
            original_setattr = type(model_self).__setattr__
            def safe_setattr(self, name, value):
                if name == 'all_tied_weights_keys':
                    object.__setattr__(self, '_all_tied_weights_keys', value)
                else:
                    original_setattr(self, name, value)
            type(model_self).__setattr__ = safe_setattr
            try:
                original_post_init(model_self)
            finally:
                type(model_self).__setattr__ = original_setattr
        PreTrainedModel.post_init = patched_post_init

        original_getattr = PreTrainedModel.__getattr__ if hasattr(PreTrainedModel, '__getattr__') else None
        def patched_getattr(self, name):
            if name == 'all_tied_weights_keys':
                return getattr(self, '_all_tied_weights_keys', {})
            if original_getattr:
                return original_getattr(self, name)
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        PreTrainedModel.__getattr__ = patched_getattr

        # Patch BiRefNet to use ungated camenduru/RMBG-2.0 instead of gated briaai/RMBG-2.0
        def patched_birefnet_init(self, model_name: str = "camenduru/RMBG-2.0"):
            from torchvision import transforms
            logger.info("Loading RMBG model: camenduru/RMBG-2.0 (fixing meta tensor + API issues)")

            # Patch torch.linspace to force CPU during model init (fixes meta tensor issue)
            original_linspace = torch.linspace
            def patched_linspace(*args, **kwargs):
                kwargs['device'] = 'cpu'
                return original_linspace(*args, **kwargs)

            try:
                torch.linspace = patched_linspace
                self.model = AutoModelForImageSegmentation.from_pretrained(
                    "camenduru/RMBG-2.0",
                    trust_remote_code=True,
                    device_map=None,
                    low_cpu_mem_usage=False,
                )
            finally:
                torch.linspace = original_linspace

            self.model.eval()
            self.transform_image = transforms.Compose([
                transforms.Resize((1024, 1024)),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ])
        rembg.BiRefNet.__init__ = patched_birefnet_init

        pipeline = Trellis2ImageTo3DPipeline.from_pretrained("microsoft/TRELLIS.2-4B")

        # Move to selected GPU device (respects TRELLIS_DEVICE env var)
        device = get_best_gpu()
        pipeline = pipeline.to(device)
        logger.info(f"Pipeline loaded on {device} in {time.time() - start:.1f}s")

    except Exception as e:
        logger.error(f"Failed to load pipeline: {e}")
        raise

    return pipeline


def unload_pipeline():
    """Unload pipeline to free GPU memory."""
    global pipeline
    if pipeline is not None:
        del pipeline
        pipeline = None
        torch.cuda.empty_cache()
        logger.info("Pipeline unloaded")


def generate_3d(
    image: Image.Image,
    seed: int = 42,
    resolution: str = "512",
    output_dir: str = "/storage/outputs"
) -> dict[str, Any]:
    """
    Generate 3D mesh from image using TRELLIS.2.

    Args:
        image: PIL Image to convert
        seed: Random seed for generation
        resolution: Output resolution ("512", "1024", "1024_cascade")
        output_dir: Directory to save output files

    Returns:
        dict with mesh_path, vertices, faces count, and timing info
    """
    pipe = load_pipeline()

    start = time.time()

    logger.info(f"Generating 3D mesh with resolution={resolution}, seed={seed}...")

    # TRELLIS.2 expects specific image preprocessing
    if image.mode != "RGB":
        image = image.convert("RGB")

    # Generate mesh
    outputs = pipe.run(
        image,
        seed=seed,
    )

    mesh = outputs[0]  # First output is the mesh

    generation_time = time.time() - start
    logger.info(f"Generation completed in {generation_time:.1f}s")

    # Save mesh
    os.makedirs(output_dir, exist_ok=True)
    timestamp = int(time.time() * 1000)

    # TRELLIS.2 MeshWithVoxel needs to be converted to GLB using o_voxel.postprocess
    import o_voxel

    # Simplify mesh to nvdiffrast limit
    mesh.simplify(16777216)

    # Convert to GLB with texture baking
    output_path = os.path.join(output_dir, f"mesh_{timestamp}.glb")
    glb = o_voxel.postprocess.to_glb(
        vertices=mesh.vertices,
        faces=mesh.faces,
        attr_volume=mesh.attrs,
        coords=mesh.coords,
        attr_layout=mesh.layout,
        voxel_size=mesh.voxel_size,
        aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
        decimation_target=500000,
        texture_size=2048,
        remesh=False,
        verbose=True
    )
    # Use extension_webp=False to avoid pillow-simd compatibility issue
    glb.export(output_path, extension_webp=False)

    # Get mesh stats
    try:
        vertices = len(mesh.vertices) if hasattr(mesh, 'vertices') else 0
        faces = len(mesh.faces) if hasattr(mesh, 'faces') else 0
    except Exception:
        vertices = 0
        faces = 0

    return {
        "success": True,
        "mesh_path": output_path,
        "format": "glb",
        "resolution": resolution,
        "seed": seed,
        "vertices": vertices,
        "faces": faces,
        "generation_time_seconds": round(generation_time, 2)
    }


class Trellis2Handler(BaseHTTPRequestHandler):
    """HTTP request handler for TRELLIS.2 API."""

    def log_message(self, format: str, *args: Any) -> None:
        """Override to use logger instead of stderr."""
        logger.info("%s - %s", self.address_string(), format % args)

    def _send_json(self, data: dict, status: int = 200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _send_error(self, message: str, status: int = 500):
        """Send error response."""
        self._send_json({"success": False, "error": message}, status)

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/health':
            self._send_json({"status": "healthy"})

        elif self.path == '/status':
            gpu_info = {}
            try:
                if torch.cuda.is_available():
                    gpu_info = {
                        "cuda_available": True,
                        "device_count": torch.cuda.device_count(),
                        "devices": []
                    }
                    for i in range(torch.cuda.device_count()):
                        props = torch.cuda.get_device_properties(i)
                        free, total = torch.cuda.mem_get_info(i)
                        gpu_info["devices"].append({
                            "index": i,
                            "name": props.name,
                            "memory_total_gb": round(total / 1e9, 2),
                            "memory_free_gb": round(free / 1e9, 2),
                            "memory_used_gb": round((total - free) / 1e9, 2),
                        })
                else:
                    gpu_info = {"cuda_available": False}
            except Exception as e:
                gpu_info = {"error": str(e)}

            self._send_json({
                "model": "TRELLIS.2-4B",
                "model_loaded": pipeline is not None,
                "gpu": gpu_info
            })

        else:
            self._send_error("Not found", 404)

    def do_POST(self):
        """Handle POST requests."""
        if self.path == '/generate':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                content_type = self.headers.get('Content-Type', '')

                if 'multipart/form-data' in content_type:
                    import cgi
                    form = cgi.FieldStorage(
                        fp=self.rfile,
                        headers=self.headers,
                        environ={
                            'REQUEST_METHOD': 'POST',
                            'CONTENT_TYPE': content_type
                        }
                    )

                    if 'image' not in form:
                        self._send_error("No image provided", 400)
                        return

                    image_data = form['image'].file.read()
                    image = Image.open(io.BytesIO(image_data))

                    seed = int(form.getvalue('seed', '42'))
                    resolution = form.getvalue('resolution', '512')

                elif 'application/json' in content_type:
                    body = self.rfile.read(content_length)
                    data = json.loads(body)

                    if 'image_path' in data:
                        image = Image.open(data['image_path'])
                    elif 'image_base64' in data:
                        image_data = base64.b64decode(data['image_base64'])
                        image = Image.open(io.BytesIO(image_data))
                    else:
                        self._send_error("No image provided (use image_path or image_base64)", 400)
                        return

                    seed = data.get('seed', 42)
                    resolution = data.get('resolution', '512')

                else:
                    self._send_error("Unsupported content type", 400)
                    return

                result = generate_3d(
                    image=image,
                    seed=seed,
                    resolution=resolution
                )

                self._send_json(result)

            except Exception as e:
                logger.error(f"Generation error: {traceback.format_exc()}")
                self._send_error(str(e), 500)

        elif self.path == '/load':
            try:
                load_pipeline()
                self._send_json({"success": True, "message": "Model loaded"})
            except Exception as e:
                self._send_error(f"Failed to load model: {e}", 500)

        elif self.path == '/unload':
            try:
                unload_pipeline()
                self._send_json({"success": True, "message": "Model unloaded"})
            except Exception as e:
                self._send_error(f"Failed to unload model: {e}", 500)

        else:
            self._send_error("Not found", 404)


def main():
    parser = argparse.ArgumentParser(description="TRELLIS.2 Image-to-3D Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument("--preload", action="store_true", help="Preload model on startup")
    args = parser.parse_args()

    if args.preload:
        logger.info("Preloading model...")
        load_pipeline()

    server = HTTPServer((args.host, args.port), Trellis2Handler)
    logger.info(f"Starting TRELLIS.2 server on {args.host}:{args.port}")
    logger.info("Endpoints:")
    logger.info("  GET  /health   - Health check")
    logger.info("  GET  /status   - Model and GPU status")
    logger.info("  POST /generate - Generate 3D mesh from image")
    logger.info("  POST /load     - Explicitly load model")
    logger.info("  POST /unload   - Unload model to free memory")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
