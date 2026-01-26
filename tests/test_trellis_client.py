"""Tests for TRELLIS.2 client."""

import pytest
from unittest.mock import MagicMock, patch, Mock
import io
import base64

from PIL import Image

from src.trellis_client import TrellisClient, TrellisResult, TrellisStatus


class TestTrellisClient:
    """Test TRELLIS.2 HTTP client."""

    def test_init_defaults(self):
        """Test client initialization with defaults."""
        client = TrellisClient()
        assert client.host == "localhost"
        assert client.port == 8000
        assert client._base_url == "http://localhost:8000"

    def test_init_custom(self):
        """Test client initialization with custom values."""
        client = TrellisClient(host="trellishost", port=9000, timeout=300.0)
        assert client.host == "trellishost"
        assert client.port == 9000
        assert client.timeout == 300.0

    @patch.dict("os.environ", {"TRELLIS_HOST": "envhost", "TRELLIS_PORT": "8001"})
    def test_init_from_env(self):
        """Test client initialization from environment variables."""
        client = TrellisClient()
        assert client.host == "envhost"
        assert client.port == 8001

    @patch("httpx.Client")
    def test_ping_success(self, mock_client_class):
        """Test successful ping."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__ = Mock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = Mock(return_value=False)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.get.return_value = mock_response

        client = TrellisClient()
        assert client.ping() is True

    @patch("httpx.Client")
    def test_ping_failure(self, mock_client_class):
        """Test failed ping."""
        mock_client_class.return_value.__enter__.side_effect = Exception("Connection refused")

        client = TrellisClient()
        assert client.ping() is False

    @patch("httpx.Client")
    def test_get_status(self, mock_client_class):
        """Test getting service status."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__ = Mock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = Mock(return_value=False)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "TRELLIS.2-4B",
            "model_loaded": True,
            "gpu": {
                "cuda_available": True,
                "devices": [
                    {"index": 0, "name": "RTX 3090", "memory_total_gb": 24.0, "memory_free_gb": 20.0}
                ]
            }
        }
        mock_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_response

        client = TrellisClient()
        status = client.get_status()

        assert status.model == "TRELLIS.2-4B"
        assert status.model_loaded is True
        assert status.cuda_available is True
        assert len(status.devices) == 1

    @patch("httpx.Client")
    def test_load_model(self, mock_client_class):
        """Test loading model."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__ = Mock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = Mock(return_value=False)
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_client.post.return_value = mock_response

        client = TrellisClient()
        assert client.load_model() is True

    @patch("httpx.Client")
    def test_unload_model(self, mock_client_class):
        """Test unloading model."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__ = Mock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = Mock(return_value=False)
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_client.post.return_value = mock_response

        client = TrellisClient()
        assert client.unload_model() is True

    @patch("httpx.Client")
    def test_generate_3d_success(self, mock_client_class):
        """Test successful 3D generation."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__ = Mock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = Mock(return_value=False)
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "mesh_path": "/storage/outputs/mesh_123.glb",
            "format": "glb",
            "resolution": "512",
            "seed": 42,
            "vertices": 24000,
            "faces": 48000,
            "generation_time_seconds": 190.5
        }
        mock_client.post.return_value = mock_response

        # Create a test image
        test_image = Image.new("RGB", (100, 100), color="red")

        client = TrellisClient()
        result = client.generate_3d(image=test_image, seed=42, resolution="512")

        assert result.success is True
        assert result.mesh_path == "/storage/outputs/mesh_123.glb"
        assert result.vertices == 24000
        assert result.faces == 48000

    @patch("httpx.Client")
    def test_generate_3d_failure(self, mock_client_class):
        """Test failed 3D generation."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__ = Mock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = Mock(return_value=False)
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": False,
            "error": "GPU out of memory"
        }
        mock_client.post.return_value = mock_response

        test_image = Image.new("RGB", (100, 100), color="red")

        client = TrellisClient()
        result = client.generate_3d(image=test_image)

        assert result.success is False
        assert "GPU out of memory" in result.error

    def test_generate_3d_no_image(self):
        """Test generation without image."""
        client = TrellisClient()
        result = client.generate_3d()

        assert result.success is False
        assert "No image provided" in result.error


class TestTrellisResult:
    """Test TrellisResult dataclass."""

    def test_success_result(self):
        """Test successful result."""
        result = TrellisResult(
            success=True,
            mesh_path="/path/to/mesh.glb",
            vertices=10000,
            faces=20000,
            generation_time_seconds=100.5
        )

        assert result.success is True
        assert result.mesh_path == "/path/to/mesh.glb"
        assert result.error is None

    def test_failure_result(self):
        """Test failure result."""
        result = TrellisResult(
            success=False,
            error="Something went wrong"
        )

        assert result.success is False
        assert result.mesh_path is None
        assert result.error == "Something went wrong"


class TestTrellisStatus:
    """Test TrellisStatus dataclass."""

    def test_status(self):
        """Test status dataclass."""
        status = TrellisStatus(
            model="TRELLIS.2-4B",
            model_loaded=True,
            cuda_available=True,
            devices=[{"index": 0, "name": "RTX 3090"}]
        )

        assert status.model == "TRELLIS.2-4B"
        assert status.model_loaded is True
        assert len(status.devices) == 1
