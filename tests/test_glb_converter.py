"""Tests for GLB converter."""

import pytest
from unittest.mock import MagicMock, patch, Mock
from pathlib import Path
import tempfile
import os

from src.glb_converter import (
    convert_glb_to_obj,
    convert_glb_to_stl,
    get_mesh_info,
    ConversionResult
)


class TestConversionResult:
    """Test ConversionResult dataclass."""

    def test_success_result(self):
        """Test successful conversion result."""
        result = ConversionResult(
            success=True,
            obj_path="/path/to/mesh.obj",
            mtl_path="/path/to/mesh.mtl",
            vertices=1000,
            faces=2000
        )

        assert result.success is True
        assert result.obj_path == "/path/to/mesh.obj"
        assert result.error is None

    def test_failure_result(self):
        """Test failure result."""
        result = ConversionResult(
            success=False,
            error="File not found"
        )

        assert result.success is False
        assert result.obj_path is None
        assert result.error == "File not found"


class TestConvertGlbToObj:
    """Test GLB to OBJ conversion."""

    def test_missing_file(self):
        """Test handling of missing input file."""
        result = convert_glb_to_obj("/nonexistent/path/mesh.glb")

        assert result.success is False
        assert "not found" in result.error.lower()

    def test_trimesh_import_available(self):
        """Test that trimesh is available for testing."""
        # Verify trimesh can be imported (it's installed)
        try:
            import trimesh
            assert hasattr(trimesh, 'load')
        except ImportError:
            pytest.skip("trimesh not installed")

    @patch("trimesh.load")
    def test_successful_conversion(self, mock_load):
        """Test successful GLB to OBJ conversion."""
        # Create mock mesh
        mock_mesh = MagicMock()
        mock_mesh.vertices = [[0, 0, 0], [1, 0, 0], [0, 1, 0]]
        mock_mesh.faces = [[0, 1, 2]]
        mock_mesh.export = MagicMock()

        mock_load.return_value = mock_mesh

        with tempfile.TemporaryDirectory() as tmpdir:
            glb_path = Path(tmpdir) / "test.glb"
            glb_path.touch()  # Create empty file

            result = convert_glb_to_obj(glb_path, output_dir=tmpdir)

            assert result.success is True
            assert result.vertices == 3
            assert result.faces == 1

    @patch("trimesh.load")
    def test_scene_with_multiple_meshes(self, mock_load):
        """Test conversion of GLB scene with multiple meshes."""
        import trimesh

        # Create mock scene with multiple meshes
        mock_mesh1 = MagicMock(spec=trimesh.Trimesh)
        mock_mesh1.vertices = [[0, 0, 0], [1, 0, 0], [0, 1, 0]]
        mock_mesh1.faces = [[0, 1, 2]]

        mock_mesh2 = MagicMock(spec=trimesh.Trimesh)
        mock_mesh2.vertices = [[0, 0, 1], [1, 0, 1], [0, 1, 1]]
        mock_mesh2.faces = [[0, 1, 2]]

        mock_scene = MagicMock(spec=trimesh.Scene)
        mock_scene.geometry = {"mesh1": mock_mesh1, "mesh2": mock_mesh2}

        mock_load.return_value = mock_scene

        # Mock concatenate
        combined_mesh = MagicMock()
        combined_mesh.vertices = [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 0, 1], [0, 1, 1]]
        combined_mesh.faces = [[0, 1, 2], [3, 4, 5]]
        combined_mesh.export = MagicMock()

        with patch("trimesh.util.concatenate", return_value=combined_mesh):
            with tempfile.TemporaryDirectory() as tmpdir:
                glb_path = Path(tmpdir) / "test.glb"
                glb_path.touch()

                result = convert_glb_to_obj(glb_path, output_dir=tmpdir)

                assert result.success is True


class TestConvertGlbToStl:
    """Test GLB to STL conversion."""

    def test_missing_file(self):
        """Test handling of missing input file."""
        result = convert_glb_to_stl("/nonexistent/path/mesh.glb")

        assert result.success is False
        assert "not found" in result.error.lower()

    @patch("trimesh.load")
    def test_successful_conversion(self, mock_load):
        """Test successful GLB to STL conversion."""
        mock_mesh = MagicMock()
        mock_mesh.vertices = [[0, 0, 0], [1, 0, 0], [0, 1, 0]]
        mock_mesh.faces = [[0, 1, 2]]
        mock_mesh.export = MagicMock()

        mock_load.return_value = mock_mesh

        with tempfile.TemporaryDirectory() as tmpdir:
            glb_path = Path(tmpdir) / "test.glb"
            glb_path.touch()

            result = convert_glb_to_stl(glb_path, output_dir=tmpdir)

            assert result.success is True
            assert result.stl_path is not None


class TestGetMeshInfo:
    """Test mesh info retrieval."""

    def test_missing_file(self):
        """Test handling of missing file."""
        info = get_mesh_info("/nonexistent/mesh.glb")

        assert "error" in info

    @patch("trimesh.load")
    def test_successful_info(self, mock_load):
        """Test successful mesh info retrieval."""
        import numpy as np

        mock_mesh = MagicMock()
        mock_mesh.vertices = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]])
        mock_mesh.faces = np.array([[0, 1, 2], [0, 1, 3]])
        mock_mesh.bounds = np.array([[0, 0, 0], [1, 1, 1]])
        mock_mesh.is_watertight = True
        mock_mesh.volume = 0.166
        mock_mesh.center_mass = np.array([0.25, 0.25, 0.25])

        mock_load.return_value = mock_mesh

        with tempfile.TemporaryDirectory() as tmpdir:
            mesh_path = Path(tmpdir) / "test.glb"
            mesh_path.touch()

            info = get_mesh_info(mesh_path)

            assert info["vertices"] == 4
            assert info["faces"] == 2
            assert info["is_watertight"] is True
