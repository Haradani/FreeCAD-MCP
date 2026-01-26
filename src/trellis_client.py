"""HTTP client for TRELLIS.2 Image-to-3D service."""

import base64
import io
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

logger = logging.getLogger(__name__)

# Path mapping constants for container-to-host translation
# TRELLIS container outputs at /storage/outputs -> host ./data/trellis/outputs
TRELLIS_CONTAINER_OUTPUT_PREFIX = "/storage/outputs"
TRELLIS_HOST_OUTPUT_PREFIX = "./data/trellis/outputs"

# FreeCAD container reads from /data/trellis/outputs
FREECAD_CONTAINER_OUTPUT_PREFIX = "/data/trellis/outputs"


@dataclass
class TrellisResult:
    """Result from TRELLIS.2 generation."""

    success: bool
    mesh_path: str | None = None
    format: str = "glb"
    resolution: str = "512"
    seed: int = 42
    vertices: int = 0
    faces: int = 0
    generation_time_seconds: float = 0.0
    error: str | None = None


@dataclass
class TrellisStatus:
    """Status of TRELLIS.2 service."""

    model: str
    model_loaded: bool
    cuda_available: bool
    devices: list[dict[str, Any]]


class TrellisClient:
    """HTTP client for TRELLIS.2 Image-to-3D service."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        timeout: float = 600.0,
    ):
        """Initialize TRELLIS.2 client.

        Args:
            host: TRELLIS server hostname (default from env or localhost)
            port: TRELLIS server port (default from env or 8000)
            timeout: Request timeout in seconds (default 600 for long generation)
        """
        self.host = host or os.environ.get("TRELLIS_HOST", "localhost")
        self.port = port or int(os.environ.get("TRELLIS_PORT", "8000"))
        self.timeout = timeout
        self._base_url = f"http://{self.host}:{self.port}"

    @staticmethod
    def translate_container_to_host_path(container_path: str) -> str:
        """Translate TRELLIS container path to host path.

        Args:
            container_path: Path inside TRELLIS container (e.g., /storage/outputs/mesh.glb)

        Returns:
            Corresponding host path (e.g., ./data/trellis/outputs/mesh.glb)
        """
        if container_path.startswith(TRELLIS_CONTAINER_OUTPUT_PREFIX):
            relative = container_path[len(TRELLIS_CONTAINER_OUTPUT_PREFIX):]
            return TRELLIS_HOST_OUTPUT_PREFIX + relative
        return container_path

    @staticmethod
    def translate_host_to_freecad_path(host_path: str) -> str:
        """Translate host path to FreeCAD container path.

        Args:
            host_path: Path on host (e.g., ./data/trellis/outputs/mesh.obj)

        Returns:
            Corresponding FreeCAD container path (e.g., /data/trellis/outputs/mesh.obj)
        """
        if host_path.startswith(TRELLIS_HOST_OUTPUT_PREFIX):
            relative = host_path[len(TRELLIS_HOST_OUTPUT_PREFIX):]
            return FREECAD_CONTAINER_OUTPUT_PREFIX + relative
        return host_path

    def ping(self) -> bool:
        """Check if TRELLIS server is responsive.

        Returns:
            True if server is healthy
        """
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self._base_url}/health")
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"TRELLIS ping failed: {e}")
            return False

    def get_status(self) -> TrellisStatus:
        """Get TRELLIS service status.

        Returns:
            TrellisStatus with model and GPU info
        """
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{self._base_url}/status")
            response.raise_for_status()
            data = response.json()

            gpu_info = data.get("gpu", {})
            return TrellisStatus(
                model=data.get("model", "TRELLIS.2-4B"),
                model_loaded=data.get("model_loaded", False),
                cuda_available=gpu_info.get("cuda_available", False),
                devices=gpu_info.get("devices", []),
            )

    def load_model(self) -> bool:
        """Explicitly load the TRELLIS model.

        Returns:
            True if model loaded successfully
        """
        with httpx.Client(timeout=300.0) as client:
            response = client.post(f"{self._base_url}/load")
            data = response.json()
            return data.get("success", False)

    def unload_model(self) -> bool:
        """Unload the TRELLIS model to free GPU memory.

        Returns:
            True if model unloaded successfully
        """
        with httpx.Client(timeout=30.0) as client:
            response = client.post(f"{self._base_url}/unload")
            data = response.json()
            return data.get("success", False)

    def generate_3d(
        self,
        image: Image.Image | str | None = None,
        image_base64: str | None = None,
        seed: int = 42,
        resolution: str = "512",
    ) -> TrellisResult:
        """Generate 3D mesh from image.

        Args:
            image: PIL Image or path to image file
            image_base64: Base64-encoded image data (alternative to image)
            seed: Random seed for generation
            resolution: Output resolution ("512", "1024", "1024_cascade")

        Returns:
            TrellisResult with mesh path and generation info
        """
        # Prepare request data
        request_data: dict[str, Any] = {
            "seed": seed,
            "resolution": resolution,
        }

        if image is not None:
            if isinstance(image, str):
                # It's a file path
                request_data["image_path"] = image
            else:
                # It's a PIL Image - encode to base64
                buf = io.BytesIO()
                image.save(buf, format="PNG")
                request_data["image_base64"] = base64.b64encode(buf.getvalue()).decode()
        elif image_base64 is not None:
            request_data["image_base64"] = image_base64
        else:
            return TrellisResult(success=False, error="No image provided")

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self._base_url}/generate",
                    json=request_data,
                )
                data = response.json()

                if data.get("success"):
                    # Translate container path to host path
                    mesh_path = data.get("mesh_path")
                    if mesh_path:
                        mesh_path = self.translate_container_to_host_path(mesh_path)

                    return TrellisResult(
                        success=True,
                        mesh_path=mesh_path,
                        format=data.get("format", "glb"),
                        resolution=data.get("resolution", resolution),
                        seed=data.get("seed", seed),
                        vertices=data.get("vertices", 0),
                        faces=data.get("faces", 0),
                        generation_time_seconds=data.get("generation_time_seconds", 0.0),
                    )
                else:
                    return TrellisResult(
                        success=False,
                        error=data.get("error", "Unknown error"),
                    )

        except httpx.TimeoutException:
            return TrellisResult(success=False, error="Request timed out")
        except Exception as e:
            logger.exception(f"TRELLIS generation failed: {e}")
            return TrellisResult(success=False, error=str(e))

    def generate_3d_from_file(
        self,
        image_path: str | Path,
        seed: int = 42,
        resolution: str = "512",
    ) -> TrellisResult:
        """Generate 3D mesh from image file.

        Args:
            image_path: Path to image file
            seed: Random seed for generation
            resolution: Output resolution

        Returns:
            TrellisResult with mesh path and generation info
        """
        image = Image.open(image_path)
        return self.generate_3d(image=image, seed=seed, resolution=resolution)
