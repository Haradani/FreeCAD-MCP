#!/usr/bin/env python3
"""VLM (Vision Language Model) loader utilities."""

import logging
from typing import Any

import torch

logger = logging.getLogger(__name__)

# Supported VLM models
VLM_MODELS = {
    "cosmos-reason-7b": {
        "id": "nvidia/Cosmos-Reason1-7B",
        "memory_fp16": 14.0,  # GB
        "memory_4bit": 5.0,
        "memory_8bit": 8.0,
    },
    "cosmos-reason-2b": {
        "id": "nvidia/Cosmos-Reason1-2B",
        "memory_fp16": 4.0,
        "memory_4bit": 1.5,
        "memory_8bit": 2.5,
    },
    "llava-1.5-7b": {
        "id": "llava-hf/llava-1.5-7b-hf",
        "memory_fp16": 14.0,
        "memory_4bit": 5.0,
        "memory_8bit": 8.0,
    },
}


def get_quantization_config(quantization: str):
    """Get BitsAndBytes quantization config.

    Args:
        quantization: '4bit', '8bit', or 'none'

    Returns:
        BitsAndBytesConfig or None
    """
    if quantization == "none":
        return None

    from transformers import BitsAndBytesConfig

    if quantization == "4bit":
        return BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
        )
    elif quantization == "8bit":
        return BitsAndBytesConfig(load_in_8bit=True)
    else:
        raise ValueError(f"Unknown quantization: {quantization}")


def load_vlm_model(
    model_name: str = "cosmos-reason-7b",
    quantization: str = "4bit",
    device: str = "cuda:0",
) -> tuple[Any, Any]:
    """Load VLM model and processor.

    Args:
        model_name: Model name from VLM_MODELS
        quantization: '4bit', '8bit', or 'none'
        device: CUDA device

    Returns:
        (model, processor) tuple
    """
    if model_name not in VLM_MODELS:
        # Assume it's a HuggingFace model ID
        model_id = model_name
    else:
        model_id = VLM_MODELS[model_name]["id"]

    logger.info(f"Loading VLM {model_id} with {quantization} quantization on {device}")

    from transformers import AutoProcessor, AutoModelForVision2Seq

    # Load processor
    processor = AutoProcessor.from_pretrained(
        model_id,
        trust_remote_code=True,
    )

    # Get quantization config
    bnb_config = get_quantization_config(quantization)

    # Load model
    model = AutoModelForVision2Seq.from_pretrained(
        model_id,
        quantization_config=bnb_config,
        device_map=device,
        torch_dtype=torch.float16,
        trust_remote_code=True,
    )

    logger.info(f"VLM loaded successfully")
    return model, processor


def estimate_memory(model_name: str, quantization: str = "4bit") -> float:
    """Estimate memory requirement for model.

    Args:
        model_name: Model name
        quantization: Quantization level

    Returns:
        Estimated memory in GB
    """
    if model_name not in VLM_MODELS:
        return 10.0  # Default estimate

    model_info = VLM_MODELS[model_name]

    if quantization == "4bit":
        return model_info["memory_4bit"]
    elif quantization == "8bit":
        return model_info["memory_8bit"]
    else:
        return model_info["memory_fp16"]


def get_optimal_config(available_memory_gb: float) -> dict[str, str]:
    """Get optimal model configuration for available memory.

    Args:
        available_memory_gb: Available GPU memory

    Returns:
        Dict with 'model' and 'quantization'
    """
    # Try models in order of capability
    configs = [
        ("cosmos-reason-7b", "4bit", 5.0),
        ("cosmos-reason-7b", "8bit", 8.0),
        ("cosmos-reason-2b", "4bit", 1.5),
        ("cosmos-reason-2b", "none", 4.0),
    ]

    for model, quant, memory in configs:
        if memory <= available_memory_gb * 0.9:  # Leave 10% buffer
            return {"model": model, "quantization": quant}

    # Fallback to smallest
    return {"model": "cosmos-reason-2b", "quantization": "4bit"}
