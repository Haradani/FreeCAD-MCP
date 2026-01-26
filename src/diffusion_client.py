"""HTTP client for ComfyUI diffusion service."""

import base64
import io
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class DiffusionResult:
    """Result from ComfyUI image generation."""

    success: bool
    image_path: str | None = None
    image_base64: str | None = None
    prompt: str | None = None
    seed: int = 0
    generation_time_seconds: float = 0.0
    error: str | None = None


class DiffusionClient:
    """HTTP client for ComfyUI diffusion service."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        timeout: float = 300.0,
    ):
        """Initialize ComfyUI client.

        Args:
            host: ComfyUI server hostname (default from env or localhost)
            port: ComfyUI server port (default from env or 8188)
            timeout: Request timeout in seconds
        """
        self.host = host or os.environ.get("DIFFUSION_HOST", "localhost")
        self.port = port or int(os.environ.get("DIFFUSION_PORT", "8188"))
        self.timeout = timeout
        self._base_url = f"http://{self.host}:{self.port}"

    def ping(self) -> bool:
        """Check if ComfyUI server is responsive.

        Returns:
            True if server is healthy
        """
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self._base_url}/")
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"ComfyUI ping failed: {e}")
            return False

    def get_queue_status(self) -> dict[str, Any]:
        """Get ComfyUI queue status.

        Returns:
            Queue status dict with running and pending counts
        """
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{self._base_url}/queue")
            response.raise_for_status()
            return response.json()

    def get_history(self, prompt_id: str | None = None) -> dict[str, Any]:
        """Get generation history.

        Args:
            prompt_id: Optional specific prompt ID

        Returns:
            History dict
        """
        url = f"{self._base_url}/history"
        if prompt_id:
            url = f"{url}/{prompt_id}"

        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.json()

    def _load_workflow(self) -> dict[str, Any]:
        """Load the text-to-image workflow template.

        Returns:
            Workflow dict
        """
        workflow_path = Path(__file__).parent.parent / "docker" / "diffusion" / "workflows" / "text_to_image.json"

        if not workflow_path.exists():
            raise FileNotFoundError(f"Workflow file not found: {workflow_path}")

        with open(workflow_path) as f:
            return json.load(f)

    def _prepare_workflow(
        self,
        prompt: str,
        negative_prompt: str = "",
        seed: int = 42,
        width: int = 1024,
        height: int = 1024,
    ) -> dict[str, Any]:
        """Prepare workflow with variables substituted.

        Args:
            prompt: Text prompt for generation
            negative_prompt: Negative prompt
            seed: Random seed
            width: Output width
            height: Output height

        Returns:
            Prepared workflow dict
        """
        workflow = self._load_workflow()
        workflow_prompt = workflow.get("prompt", workflow)

        # Update text prompts
        if "4" in workflow_prompt:
            workflow_prompt["4"]["inputs"]["text"] = prompt
        if "5" in workflow_prompt:
            workflow_prompt["5"]["inputs"]["text"] = negative_prompt

        # Update seed
        if "7" in workflow_prompt:
            workflow_prompt["7"]["inputs"]["seed"] = seed

        # Update dimensions
        if "6" in workflow_prompt:
            workflow_prompt["6"]["inputs"]["width"] = width
            workflow_prompt["6"]["inputs"]["height"] = height

        return workflow_prompt

    def generate_image(
        self,
        prompt: str,
        negative_prompt: str = "multiple objects, text, watermark, blurry, low quality",
        seed: int | None = None,
        width: int = 1024,
        height: int = 1024,
        poll_interval: float = 1.0,
    ) -> DiffusionResult:
        """Generate image from text prompt.

        Args:
            prompt: Text description of image to generate
            negative_prompt: Things to avoid in generation
            seed: Random seed (random if None)
            width: Output image width
            height: Output image height
            poll_interval: Seconds between status polls

        Returns:
            DiffusionResult with image path/data
        """
        if seed is None:
            import random
            seed = random.randint(0, 2**32 - 1)

        start_time = time.time()

        # Prepare workflow
        workflow_prompt = self._prepare_workflow(
            prompt=prompt,
            negative_prompt=negative_prompt,
            seed=seed,
            width=width,
            height=height,
        )

        # Generate unique client ID
        client_id = str(uuid.uuid4())

        try:
            with httpx.Client(timeout=self.timeout) as client:
                # Queue the prompt
                response = client.post(
                    f"{self._base_url}/prompt",
                    json={"prompt": workflow_prompt, "client_id": client_id},
                )
                response.raise_for_status()
                result = response.json()
                prompt_id = result.get("prompt_id")

                if not prompt_id:
                    return DiffusionResult(
                        success=False,
                        error="No prompt_id returned",
                    )

                logger.info(f"Queued prompt {prompt_id}")

                # Poll for completion
                while True:
                    time.sleep(poll_interval)

                    # Check history for completion
                    history_response = client.get(f"{self._base_url}/history/{prompt_id}")
                    if history_response.status_code == 200:
                        history = history_response.json()
                        if prompt_id in history:
                            outputs = history[prompt_id].get("outputs", {})
                            # Find the save image node output
                            for node_id, node_output in outputs.items():
                                if "images" in node_output:
                                    images = node_output["images"]
                                    if images:
                                        image_info = images[0]
                                        filename = image_info.get("filename")
                                        subfolder = image_info.get("subfolder", "")
                                        image_type = image_info.get("type", "output")

                                        # Construct the image path
                                        image_path = f"/storage/outputs/{subfolder}/{filename}" if subfolder else f"/storage/outputs/{filename}"

                                        # Try to fetch the image data
                                        view_response = client.get(
                                            f"{self._base_url}/view",
                                            params={
                                                "filename": filename,
                                                "subfolder": subfolder,
                                                "type": image_type,
                                            },
                                        )

                                        image_base64 = None
                                        if view_response.status_code == 200:
                                            image_base64 = base64.b64encode(view_response.content).decode()

                                        generation_time = time.time() - start_time
                                        return DiffusionResult(
                                            success=True,
                                            image_path=image_path,
                                            image_base64=image_base64,
                                            prompt=prompt,
                                            seed=seed,
                                            generation_time_seconds=round(generation_time, 2),
                                        )

                    # Check queue status
                    queue_response = client.get(f"{self._base_url}/queue")
                    if queue_response.status_code == 200:
                        queue = queue_response.json()
                        running = queue.get("queue_running", [])
                        pending = queue.get("queue_pending", [])

                        # Check if our prompt is still being processed
                        still_processing = any(
                            p[1] == prompt_id
                            for p in running + pending
                        )

                        if not still_processing:
                            # Not in queue and not in history - check for errors
                            break

                    # Timeout check
                    if time.time() - start_time > self.timeout:
                        return DiffusionResult(
                            success=False,
                            error="Generation timed out",
                        )

                return DiffusionResult(
                    success=False,
                    error="Generation completed but no output found",
                )

        except httpx.TimeoutException:
            return DiffusionResult(success=False, error="Request timed out")
        except Exception as e:
            logger.exception(f"ComfyUI generation failed: {e}")
            return DiffusionResult(success=False, error=str(e))

    def generate_image_for_3d(
        self,
        subject: str,
        seed: int | None = None,
    ) -> DiffusionResult:
        """Generate an image optimized for 3D conversion.

        Args:
            subject: Description of the 3D object to generate
            seed: Random seed

        Returns:
            DiffusionResult optimized for TRELLIS.2 input
        """
        # Craft prompt optimized for 3D conversion
        prompt = (
            f"a single 3D model of {subject}, "
            "white background, studio lighting, product photography, "
            "centered, high detail, sharp focus, isolated object"
        )

        negative_prompt = (
            "multiple objects, background clutter, text, watermark, "
            "blurry, low quality, cropped, partial view, shadows"
        )

        return self.generate_image(
            prompt=prompt,
            negative_prompt=negative_prompt,
            seed=seed,
            width=1024,
            height=1024,
        )
