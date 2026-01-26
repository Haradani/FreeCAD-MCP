"""ZMQ client for communicating with Vision AI inference container."""

import base64
import io
import logging
import os
from typing import Any

import zmq
from PIL import Image

logger = logging.getLogger(__name__)


class InferenceClient:
    """Client for Vision AI inference server."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5555,
        timeout_ms: int = 60000,
    ):
        """Initialize inference client.

        Args:
            host: Inference server host
            port: ZMQ port
            timeout_ms: Request timeout in milliseconds
        """
        self.host = host
        self.port = port
        self.timeout_ms = timeout_ms
        self._context: zmq.Context | None = None
        self._socket: zmq.Socket | None = None

    def _get_socket(self) -> zmq.Socket:
        """Get or create ZMQ socket."""
        if self._socket is None:
            self._context = zmq.Context()
            self._socket = self._context.socket(zmq.REQ)
            self._socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
            self._socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
            self._socket.connect(f"tcp://{self.host}:{self.port}")
        return self._socket

    def _send_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Send request and get response.

        Args:
            request: Request dictionary

        Returns:
            Response dictionary
        """
        socket = self._get_socket()
        socket.send_json(request)
        return socket.recv_json()

    def _image_to_base64(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 string."""
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()

    def _base64_to_image(self, data: str) -> Image.Image:
        """Convert base64 string to PIL Image."""
        img_data = base64.b64decode(data)
        return Image.open(io.BytesIO(img_data))

    def close(self):
        """Close the connection."""
        if self._socket is not None:
            self._socket.close()
            self._socket = None
        if self._context is not None:
            self._context.term()
            self._context = None

    def ping(self) -> bool:
        """Check if inference server is responsive."""
        try:
            response = self._send_request({"action": "ping"})
            return response.get("status") == "ok"
        except Exception as e:
            logger.warning(f"Inference ping failed: {e}")
            return False

    def get_status(self) -> dict[str, Any]:
        """Get inference server status.

        Returns:
            Status dict with gpu count, loaded models, etc.
        """
        return self._send_request({"action": "status"})

    # =========================================================================
    # VLM Operations
    # =========================================================================

    def analyze_image(
        self,
        image: Image.Image,
        prompt: str,
        max_tokens: int = 512,
    ) -> dict[str, Any]:
        """Analyze image with VLM.

        Args:
            image: PIL Image to analyze
            prompt: Question or instruction
            max_tokens: Maximum response tokens

        Returns:
            Dict with 'response', optionally 'thinking' for CoT models
        """
        response = self._send_request({
            "action": "vlm_analyze",
            "image": self._image_to_base64(image),
            "prompt": prompt,
            "max_tokens": max_tokens,
        })

        if response.get("status") != "ok":
            raise RuntimeError(response.get("error", "Unknown error"))

        return {
            "response": response.get("response"),
            "thinking": response.get("thinking"),
        }

    def describe_model(self, image: Image.Image) -> str:
        """Get a description of a CAD model image.

        Args:
            image: Image of the CAD model

        Returns:
            Description string
        """
        result = self.analyze_image(
            image,
            "Describe this CAD model. What type of part is it? "
            "What are its key features and dimensions?",
        )
        return result["response"]

    def check_design(self, image: Image.Image, requirements: str) -> dict[str, Any]:
        """Check if design meets requirements.

        Args:
            image: Image of the CAD model
            requirements: Design requirements to check

        Returns:
            Dict with 'meets_requirements', 'issues', 'suggestions'
        """
        result = self.analyze_image(
            image,
            f"Analyze this CAD model against these requirements: {requirements}\n\n"
            "Respond with:\n"
            "1. Does it meet the requirements? (yes/no)\n"
            "2. Any issues found\n"
            "3. Suggestions for improvement",
        )

        response = result["response"].lower()
        return {
            "meets_requirements": "yes" in response[:50],
            "analysis": result["response"],
            "thinking": result.get("thinking"),
        }

    def load_vlm(self) -> bool:
        """Explicitly load VLM model.

        Returns:
            True if successful
        """
        response = self._send_request({"action": "load_vlm"})
        return response.get("status") == "ok"

    def unload_vlm(self) -> bool:
        """Unload VLM to free GPU memory.

        Returns:
            True if successful
        """
        response = self._send_request({"action": "unload_vlm"})
        return response.get("status") == "ok"

    # =========================================================================
    # SAM Operations
    # =========================================================================

    def segment_point(
        self,
        image: Image.Image,
        point: tuple[int, int],
        foreground: bool = True,
    ) -> dict[str, Any]:
        """Segment region around a point.

        Args:
            image: PIL Image
            point: (x, y) coordinates
            foreground: True for foreground, False for background

        Returns:
            Dict with 'mask' (PIL Image), 'score' (confidence)
        """
        response = self._send_request({
            "action": "sam_point",
            "image": self._image_to_base64(image),
            "point": list(point),
            "point_label": 1 if foreground else 0,
        })

        if response.get("status") != "ok":
            raise RuntimeError(response.get("error", "Unknown error"))

        return {
            "mask": self._base64_to_image(response["mask"]),
            "score": response["score"],
        }

    def segment_text(
        self,
        image: Image.Image,
        description: str,
    ) -> dict[str, Any]:
        """Segment region based on text description.

        Args:
            image: PIL Image
            description: Text description of region

        Returns:
            Dict with 'mask' (PIL Image), 'regions' (detected regions)
        """
        response = self._send_request({
            "action": "sam_text",
            "image": self._image_to_base64(image),
            "text": description,
        })

        if response.get("status") != "ok":
            raise RuntimeError(response.get("error", "Unknown error"))

        return {
            "mask": self._base64_to_image(response["mask"]),
            "regions": response.get("regions", []),
        }

    def segment_feature(
        self,
        image: Image.Image,
        feature_name: str,
    ) -> Image.Image | None:
        """Segment a specific CAD feature by name.

        Args:
            image: Image of CAD model
            feature_name: Name of feature to segment (e.g., "bolt holes", "flange")

        Returns:
            Mask image or None if feature not found
        """
        try:
            result = self.segment_text(image, feature_name)
            if result["regions"]:
                return result["mask"]
            return None
        except Exception as e:
            logger.warning(f"Feature segmentation failed: {e}")
            return None

    def load_sam(self) -> bool:
        """Explicitly load SAM model.

        Returns:
            True if successful
        """
        response = self._send_request({"action": "load_sam"})
        return response.get("status") == "ok"

    def unload_sam(self) -> bool:
        """Unload SAM to free GPU memory.

        Returns:
            True if successful
        """
        response = self._send_request({"action": "unload_sam"})
        return response.get("status") == "ok"


# Global client instance
_client: InferenceClient | None = None


def get_inference_client() -> InferenceClient:
    """Get or create the global inference client."""
    global _client
    if _client is None:
        host = os.environ.get("INFERENCE_HOST", "localhost")
        port = int(os.environ.get("INFERENCE_PORT", "5555"))
        _client = InferenceClient(host=host, port=port)
    return _client
