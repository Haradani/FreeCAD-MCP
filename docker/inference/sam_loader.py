#!/usr/bin/env python3
"""SAM model loader utilities."""

import logging
import os
from pathlib import Path

import torch

logger = logging.getLogger(__name__)

# Model URLs
SAM_MODELS = {
    "vit_h": {
        "url": "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth",
        "size": "2.4GB",
    },
    "vit_l": {
        "url": "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_l_0b3195.pth",
        "size": "1.2GB",
    },
    "vit_b": {
        "url": "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth",
        "size": "375MB",
    },
}


def download_model(model_type: str = "vit_h", model_dir: str = "/models") -> str:
    """Download SAM model if not present.

    Args:
        model_type: 'vit_h', 'vit_l', or 'vit_b'
        model_dir: Directory to save model

    Returns:
        Path to downloaded model
    """
    if model_type not in SAM_MODELS:
        raise ValueError(f"Unknown model type: {model_type}")

    model_info = SAM_MODELS[model_type]
    model_path = Path(model_dir) / f"sam_{model_type}.pth"

    if model_path.exists():
        logger.info(f"Model already exists: {model_path}")
        return str(model_path)

    logger.info(f"Downloading SAM {model_type} ({model_info['size']})...")

    import urllib.request

    os.makedirs(model_dir, exist_ok=True)
    urllib.request.urlretrieve(model_info["url"], model_path)

    logger.info(f"Downloaded to: {model_path}")
    return str(model_path)


def load_sam_model(
    model_type: str = "vit_h",
    model_path: str | None = None,
    device: str = "cuda",
):
    """Load SAM model.

    Args:
        model_type: 'vit_h', 'vit_l', or 'vit_b'
        model_path: Path to model checkpoint
        device: Device to load to

    Returns:
        Loaded model
    """
    try:
        from segment_anything import sam_model_registry, SamPredictor

        if model_path is None:
            model_path = download_model(model_type)

        logger.info(f"Loading SAM {model_type} from {model_path}")

        model = sam_model_registry[model_type](checkpoint=model_path)
        model = model.to(device)
        model.eval()

        predictor = SamPredictor(model)
        return model, predictor

    except ImportError:
        logger.warning("segment_anything not available, using transformers fallback")

        from transformers import SamModel, SamProcessor

        model = SamModel.from_pretrained("facebook/sam-vit-huge")
        processor = SamProcessor.from_pretrained("facebook/sam-vit-huge")
        model = model.to(device)

        return model, processor


def get_model_memory(model_type: str = "vit_h") -> float:
    """Estimate model memory usage in GB.

    Args:
        model_type: Model type

    Returns:
        Estimated memory in GB
    """
    memory_map = {
        "vit_h": 2.5,
        "vit_l": 1.3,
        "vit_b": 0.4,
    }
    return memory_map.get(model_type, 2.5)
