"""Cosmos VLM integration for CAD analysis.

This module provides high-level functions for using Cosmos VLM
to analyze CAD models and provide natural language feedback.
"""

import logging
from typing import Any

from PIL import Image

from .inference_client import get_inference_client

logger = logging.getLogger(__name__)


def analyze_cad_image(
    image: Image.Image,
    question: str | None = None,
) -> dict[str, Any]:
    """Analyze a CAD model image.

    Args:
        image: Image of the CAD model
        question: Specific question to answer (optional)

    Returns:
        Dict with 'description', 'features', 'analysis'
    """
    client = get_inference_client()

    if question:
        prompt = question
    else:
        prompt = (
            "Analyze this CAD model image. Describe:\n"
            "1. What type of part or assembly this is\n"
            "2. Key geometric features (holes, fillets, chamfers, etc.)\n"
            "3. Approximate dimensions and proportions\n"
            "4. Manufacturing considerations\n"
            "5. Potential issues or improvements"
        )

    result = client.analyze_image(image, prompt, max_tokens=1024)

    return {
        "response": result["response"],
        "thinking": result.get("thinking"),
    }


def validate_design(
    image: Image.Image,
    requirements: list[str],
) -> dict[str, Any]:
    """Validate a CAD design against requirements.

    Args:
        image: Image of the CAD model
        requirements: List of design requirements to check

    Returns:
        Dict with 'valid', 'issues', 'score'
    """
    client = get_inference_client()

    req_text = "\n".join(f"- {r}" for r in requirements)
    prompt = (
        f"Review this CAD model against the following requirements:\n{req_text}\n\n"
        "For each requirement, indicate if it is:\n"
        "- MET: The requirement is satisfied\n"
        "- NOT MET: The requirement is not satisfied (explain why)\n"
        "- UNCLEAR: Cannot determine from this view\n\n"
        "Finally, give an overall assessment."
    )

    result = client.analyze_image(image, prompt, max_tokens=1024)

    # Parse response
    response = result["response"]
    issues = []
    score = 0
    total = len(requirements)

    for req in requirements:
        if "MET" in response and req.lower() in response.lower():
            score += 1
        elif "NOT MET" in response:
            issues.append(f"Requirement not met: {req}")

    return {
        "valid": score == total,
        "score": score / total if total > 0 else 0,
        "issues": issues,
        "analysis": response,
        "thinking": result.get("thinking"),
    }


def suggest_improvements(image: Image.Image) -> list[str]:
    """Get improvement suggestions for a CAD model.

    Args:
        image: Image of the CAD model

    Returns:
        List of improvement suggestions
    """
    client = get_inference_client()

    prompt = (
        "Analyze this CAD model and suggest improvements in these areas:\n"
        "1. Structural integrity\n"
        "2. Manufacturing feasibility\n"
        "3. Assembly considerations\n"
        "4. Material efficiency\n"
        "5. Aesthetic refinements\n\n"
        "List specific, actionable suggestions."
    )

    result = client.analyze_image(image, prompt, max_tokens=1024)

    # Parse suggestions from response
    suggestions = []
    for line in result["response"].split("\n"):
        line = line.strip()
        if line and (line[0].isdigit() or line.startswith("-")):
            # Clean up the suggestion
            suggestion = line.lstrip("0123456789.-) ").strip()
            if suggestion:
                suggestions.append(suggestion)

    return suggestions


def compare_designs(
    image1: Image.Image,
    image2: Image.Image,
    criteria: list[str] | None = None,
) -> dict[str, Any]:
    """Compare two CAD designs.

    Note: This requires sending both images, which may need
    multiple API calls or a combined image.

    Args:
        image1: First design image
        image2: Second design image
        criteria: Comparison criteria (optional)

    Returns:
        Dict with comparison results
    """
    client = get_inference_client()

    # Create a combined image
    width = max(image1.width, image2.width)
    height = image1.height + image2.height + 20
    combined = Image.new("RGB", (width, height), (255, 255, 255))
    combined.paste(image1, (0, 0))
    combined.paste(image2, (0, image1.height + 20))

    if criteria:
        criteria_text = "\n".join(f"- {c}" for c in criteria)
        prompt = (
            "Compare these two CAD designs (top vs bottom) based on:\n"
            f"{criteria_text}\n\n"
            "Which design is better for each criterion and why?"
        )
    else:
        prompt = (
            "Compare these two CAD designs (top image vs bottom image).\n"
            "Identify differences, relative strengths, and weaknesses of each."
        )

    result = client.analyze_image(combined, prompt, max_tokens=1024)

    return {
        "comparison": result["response"],
        "thinking": result.get("thinking"),
    }


def identify_features(image: Image.Image) -> list[dict[str, Any]]:
    """Identify and list features in a CAD model.

    Args:
        image: Image of the CAD model

    Returns:
        List of feature dicts with 'name', 'type', 'description'
    """
    client = get_inference_client()

    prompt = (
        "Identify all visible features in this CAD model.\n"
        "For each feature, provide:\n"
        "- Feature name\n"
        "- Feature type (hole, fillet, chamfer, boss, pocket, etc.)\n"
        "- Brief description\n\n"
        "Format as a numbered list."
    )

    result = client.analyze_image(image, prompt, max_tokens=1024)

    # Parse features from response
    features = []
    current_feature = {}

    for line in result["response"].split("\n"):
        line = line.strip()
        if not line:
            if current_feature:
                features.append(current_feature)
                current_feature = {}
            continue

        if line[0].isdigit():
            if current_feature:
                features.append(current_feature)
            current_feature = {"name": line.lstrip("0123456789.) ").strip()}
        elif "type:" in line.lower():
            current_feature["type"] = line.split(":", 1)[1].strip()
        elif "description:" in line.lower():
            current_feature["description"] = line.split(":", 1)[1].strip()
        elif current_feature and "description" not in current_feature:
            current_feature["description"] = line

    if current_feature:
        features.append(current_feature)

    return features
