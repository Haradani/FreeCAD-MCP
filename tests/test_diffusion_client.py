"""Tests for ComfyUI diffusion client."""

import pytest
from unittest.mock import MagicMock, patch, Mock
import json

from src.diffusion_client import DiffusionClient, DiffusionResult


class TestDiffusionClient:
    """Test ComfyUI HTTP client."""

    def test_init_defaults(self):
        """Test client initialization with defaults."""
        client = DiffusionClient()
        assert client.host == "localhost"
        assert client.port == 8188
        assert client._base_url == "http://localhost:8188"

    def test_init_custom(self):
        """Test client initialization with custom values."""
        client = DiffusionClient(host="comfyhost", port=8000, timeout=600.0)
        assert client.host == "comfyhost"
        assert client.port == 8000
        assert client.timeout == 600.0

    @patch.dict("os.environ", {"DIFFUSION_HOST": "envhost", "DIFFUSION_PORT": "8189"})
    def test_init_from_env(self):
        """Test client initialization from environment variables."""
        client = DiffusionClient()
        assert client.host == "envhost"
        assert client.port == 8189

    @patch("httpx.Client")
    def test_ping_success(self, mock_client_class):
        """Test successful ping."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__ = Mock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = Mock(return_value=False)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.get.return_value = mock_response

        client = DiffusionClient()
        assert client.ping() is True

    @patch("httpx.Client")
    def test_ping_failure(self, mock_client_class):
        """Test failed ping."""
        mock_client_class.return_value.__enter__.side_effect = Exception("Connection refused")

        client = DiffusionClient()
        assert client.ping() is False

    @patch("httpx.Client")
    def test_get_queue_status(self, mock_client_class):
        """Test getting queue status."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__ = Mock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = Mock(return_value=False)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "queue_running": [],
            "queue_pending": []
        }
        mock_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_response

        client = DiffusionClient()
        status = client.get_queue_status()

        assert "queue_running" in status
        assert "queue_pending" in status

    def test_prepare_workflow(self):
        """Test workflow preparation."""
        client = DiffusionClient()
        workflow = client._prepare_workflow(
            prompt="a red car",
            negative_prompt="blurry",
            seed=123,
            width=512,
            height=512
        )

        # Check that text prompts were set
        assert workflow["4"]["inputs"]["text"] == "a red car"
        assert workflow["5"]["inputs"]["text"] == "blurry"
        assert workflow["7"]["inputs"]["seed"] == 123
        assert workflow["6"]["inputs"]["width"] == 512
        assert workflow["6"]["inputs"]["height"] == 512

    def test_generate_image_for_3d_prompt(self):
        """Test that generate_image_for_3d creates proper prompts."""
        client = DiffusionClient()

        # Mock the generate_image method to capture the prompt
        captured_prompts = {}

        def mock_generate_image(prompt, negative_prompt, seed, width, height):
            captured_prompts["prompt"] = prompt
            captured_prompts["negative_prompt"] = negative_prompt
            return DiffusionResult(success=True, prompt=prompt, seed=seed or 42)

        client.generate_image = mock_generate_image

        client.generate_image_for_3d(subject="a wooden chair", seed=42)

        # Check prompt was crafted correctly
        assert "wooden chair" in captured_prompts["prompt"]
        assert "white background" in captured_prompts["prompt"]
        assert "centered" in captured_prompts["prompt"]
        assert "multiple objects" in captured_prompts["negative_prompt"]


class TestDiffusionResult:
    """Test DiffusionResult dataclass."""

    def test_success_result(self):
        """Test successful result."""
        result = DiffusionResult(
            success=True,
            image_path="/path/to/image.png",
            image_base64="base64data",
            prompt="test prompt",
            seed=42,
            generation_time_seconds=3.5
        )

        assert result.success is True
        assert result.image_path == "/path/to/image.png"
        assert result.seed == 42
        assert result.error is None

    def test_failure_result(self):
        """Test failure result."""
        result = DiffusionResult(
            success=False,
            error="Generation failed"
        )

        assert result.success is False
        assert result.image_path is None
        assert result.error == "Generation failed"


class TestWorkflowLoading:
    """Test workflow file loading."""

    def test_load_workflow_fallback(self):
        """Test that fallback workflow is returned when file doesn't exist."""
        client = DiffusionClient()

        # Even if workflow file doesn't exist, should return valid workflow
        workflow = client._load_workflow()

        assert "prompt" in workflow or "1" in workflow
        # Should have the essential nodes
        has_sampler = False
        for key, value in (workflow.get("prompt", workflow)).items():
            if isinstance(value, dict) and value.get("class_type") == "KSampler":
                has_sampler = True
                break
        assert has_sampler, "Workflow should contain KSampler node"
