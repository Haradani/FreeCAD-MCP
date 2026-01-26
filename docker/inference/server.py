#!/usr/bin/env python3
"""Vision AI inference server using ZMQ.

Provides:
- SAM3 segmentation
- Cosmos VLM image understanding
- GPU memory management for dual 3090 setup
"""

import base64
import io
import json
import logging
import os
import time
from typing import Any

import numpy as np
import torch
import zmq
from PIL import Image

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class GPUManager:
    """Manage GPU memory allocation for multiple models."""

    def __init__(self):
        """Initialize GPU manager."""
        self.num_gpus = torch.cuda.device_count()
        logger.info(f"Found {self.num_gpus} GPU(s)")

        for i in range(self.num_gpus):
            props = torch.cuda.get_device_properties(i)
            logger.info(
                f"  GPU {i}: {props.name}, {props.total_memory / 1024**3:.1f} GB"
            )

    def get_free_memory(self, device: int = 0) -> float:
        """Get free memory on device in GB."""
        torch.cuda.synchronize(device)
        free, total = torch.cuda.mem_get_info(device)
        return free / 1024**3

    def clear_cache(self, device: int | None = None):
        """Clear CUDA cache."""
        if device is not None:
            with torch.cuda.device(device):
                torch.cuda.empty_cache()
        else:
            torch.cuda.empty_cache()


class VLMHandler:
    """Handler for Vision Language Model (Cosmos VLM)."""

    def __init__(
        self,
        device: str = "cuda:0",
        quantization: str = "4bit",
    ):
        """Initialize VLM handler.

        Args:
            device: CUDA device
            quantization: '4bit', '8bit', or 'none'
        """
        self.device = device
        self.quantization = quantization
        self.model = None
        self.processor = None
        self.model_id = "nvidia/Cosmos-Reason1-7B"

    def load(self):
        """Load the VLM model."""
        if self.model is not None:
            return

        logger.info(f"Loading VLM on {self.device} with {self.quantization} quantization...")

        from transformers import AutoProcessor, AutoModelForVision2Seq, BitsAndBytesConfig

        # Configure quantization
        if self.quantization == "4bit":
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
            )
        elif self.quantization == "8bit":
            bnb_config = BitsAndBytesConfig(load_in_8bit=True)
        else:
            bnb_config = None

        # Load processor
        self.processor = AutoProcessor.from_pretrained(
            self.model_id,
            trust_remote_code=True,
        )

        # Load model
        self.model = AutoModelForVision2Seq.from_pretrained(
            self.model_id,
            quantization_config=bnb_config,
            device_map=self.device,
            torch_dtype=torch.float16,
            trust_remote_code=True,
        )

        logger.info("VLM loaded successfully")

    def unload(self):
        """Unload model to free memory."""
        if self.model is not None:
            del self.model
            del self.processor
            self.model = None
            self.processor = None
            torch.cuda.empty_cache()
            logger.info("VLM unloaded")

    def analyze_image(
        self,
        image: Image.Image,
        prompt: str,
        max_tokens: int = 512,
    ) -> dict[str, Any]:
        """Analyze image with prompt.

        Args:
            image: PIL Image to analyze
            prompt: Question or instruction
            max_tokens: Maximum response tokens

        Returns:
            Dict with 'response', 'thinking' (if chain-of-thought)
        """
        self.load()

        # Prepare inputs
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image"},
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        input_text = self.processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
        )

        inputs = self.processor(
            images=image,
            text=input_text,
            return_tensors="pt",
        ).to(self.device)

        # Generate
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
            )

        response = self.processor.decode(
            outputs[0][inputs["input_ids"].shape[-1]:],
            skip_special_tokens=True,
        )

        # Parse chain-of-thought if present
        result = {"response": response}

        if "<think>" in response:
            think_start = response.find("<think>") + 7
            think_end = response.find("</think>")
            if think_end > think_start:
                result["thinking"] = response[think_start:think_end].strip()
                result["response"] = response[think_end + 8:].strip()

        return result


class SAMHandler:
    """Handler for Segment Anything Model 3."""

    def __init__(self, device: str = "cuda:1"):
        """Initialize SAM handler.

        Args:
            device: CUDA device
        """
        self.device = device
        self.model = None
        self.predictor = None

    def load(self):
        """Load SAM model."""
        if self.model is not None:
            return

        logger.info(f"Loading SAM3 on {self.device}...")

        try:
            from segment_anything_2 import sam_model_registry, SamPredictor

            # Use SAM-H for best quality
            self.model = sam_model_registry["vit_h"](
                checkpoint="/models/sam_vit_h.pth"
            ).to(self.device)
            self.predictor = SamPredictor(self.model)

        except ImportError:
            # Fallback to SAM2 from transformers
            from transformers import SamModel, SamProcessor

            self.processor = SamProcessor.from_pretrained("facebook/sam-vit-huge")
            self.model = SamModel.from_pretrained("facebook/sam-vit-huge").to(self.device)
            self.predictor = None

        logger.info("SAM loaded successfully")

    def unload(self):
        """Unload model to free memory."""
        if self.model is not None:
            del self.model
            del self.predictor
            self.model = None
            self.predictor = None
            torch.cuda.empty_cache()
            logger.info("SAM unloaded")

    def segment_point(
        self,
        image: Image.Image,
        point: tuple[int, int],
        point_label: int = 1,
    ) -> dict[str, Any]:
        """Segment region around a point.

        Args:
            image: PIL Image
            point: (x, y) coordinates
            point_label: 1 for foreground, 0 for background

        Returns:
            Dict with 'mask' (base64 PNG), 'score'
        """
        self.load()

        image_np = np.array(image)

        if self.predictor is not None:
            # SAM2 API
            self.predictor.set_image(image_np)
            masks, scores, _ = self.predictor.predict(
                point_coords=np.array([[point[0], point[1]]]),
                point_labels=np.array([point_label]),
                multimask_output=True,
            )
            # Use highest scoring mask
            best_idx = np.argmax(scores)
            mask = masks[best_idx]
            score = float(scores[best_idx])
        else:
            # Transformers API
            inputs = self.processor(
                images=image,
                input_points=[[[point[0], point[1]]]],
                return_tensors="pt",
            ).to(self.device)

            with torch.no_grad():
                outputs = self.model(**inputs)

            masks = self.processor.image_processor.post_process_masks(
                outputs.pred_masks,
                inputs["original_sizes"],
                inputs["reshaped_input_sizes"],
            )
            mask = masks[0][0][0].cpu().numpy()
            score = float(outputs.iou_scores[0][0][0])

        # Convert mask to PNG
        mask_img = Image.fromarray((mask * 255).astype(np.uint8))
        buf = io.BytesIO()
        mask_img.save(buf, format="PNG")
        mask_b64 = base64.b64encode(buf.getvalue()).decode()

        return {
            "mask": mask_b64,
            "score": score,
        }

    def segment_text(
        self,
        image: Image.Image,
        text_prompt: str,
    ) -> dict[str, Any]:
        """Segment region based on text description.

        Args:
            image: PIL Image
            text_prompt: Description of region to segment

        Returns:
            Dict with 'mask' (base64 PNG), 'regions' list
        """
        self.load()

        # Text-based segmentation requires GroundingDINO + SAM
        # This feature is not implemented - error out instead of returning fake data
        raise NotImplementedError(
            "Text-based segmentation requires GroundingDINO which is not currently installed. "
            "Use point-based segmentation (segment_points) instead."
        )


class InferenceServer:
    """ZMQ-based inference server."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 5555,
    ):
        """Initialize server.

        Args:
            host: Bind host
            port: Bind port
        """
        self.host = host
        self.port = port

        # Initialize GPU manager
        self.gpu_manager = GPUManager()

        # Initialize handlers
        vlm_device = os.environ.get("VLM_DEVICE", "cuda:0")
        vlm_quant = os.environ.get("VLM_QUANTIZATION", "4bit")
        sam_device = os.environ.get("SAM_DEVICE", "cuda:1" if self.gpu_manager.num_gpus > 1 else "cuda:0")

        self.vlm = VLMHandler(device=vlm_device, quantization=vlm_quant)
        self.sam = SAMHandler(device=sam_device)

        # ZMQ setup
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)

    def start(self):
        """Start the server."""
        self.socket.bind(f"tcp://{self.host}:{self.port}")
        logger.info(f"Inference server listening on {self.host}:{self.port}")

        while True:
            try:
                message = self.socket.recv_json()
                response = self.handle_request(message)
                self.socket.send_json(response)
            except Exception as e:
                logger.exception(f"Error handling request: {e}")
                self.socket.send_json({"error": str(e)})

    def handle_request(self, request: dict) -> dict:
        """Handle incoming request.

        Args:
            request: Request dict with 'action' and parameters

        Returns:
            Response dict
        """
        action = request.get("action")

        if action == "ping":
            return {"status": "ok", "timestamp": time.time()}

        elif action == "status":
            return {
                "status": "ok",
                "gpus": self.gpu_manager.num_gpus,
                "vlm_loaded": self.vlm.model is not None,
                "sam_loaded": self.sam.model is not None,
            }

        elif action == "vlm_analyze":
            # Decode image
            img_data = base64.b64decode(request["image"])
            image = Image.open(io.BytesIO(img_data))
            prompt = request.get("prompt", "Describe this image.")
            max_tokens = request.get("max_tokens", 512)

            result = self.vlm.analyze_image(image, prompt, max_tokens)
            return {"status": "ok", **result}

        elif action == "sam_point":
            img_data = base64.b64decode(request["image"])
            image = Image.open(io.BytesIO(img_data))
            point = tuple(request["point"])
            label = request.get("point_label", 1)

            result = self.sam.segment_point(image, point, label)
            return {"status": "ok", **result}

        elif action == "sam_text":
            img_data = base64.b64decode(request["image"])
            image = Image.open(io.BytesIO(img_data))
            text = request["text"]

            result = self.sam.segment_text(image, text)
            return {"status": "ok", **result}

        elif action == "unload_vlm":
            self.vlm.unload()
            return {"status": "ok", "message": "VLM unloaded"}

        elif action == "unload_sam":
            self.sam.unload()
            return {"status": "ok", "message": "SAM unloaded"}

        elif action == "load_vlm":
            self.vlm.load()
            return {"status": "ok", "message": "VLM loaded"}

        elif action == "load_sam":
            self.sam.load()
            return {"status": "ok", "message": "SAM loaded"}

        else:
            return {"error": f"Unknown action: {action}"}


def main():
    """Start the inference server."""
    host = os.environ.get("ZMQ_HOST", "0.0.0.0")
    port = int(os.environ.get("ZMQ_PORT", "5555"))

    server = InferenceServer(host=host, port=port)
    server.start()


if __name__ == "__main__":
    main()
