"""Tests for MCP server."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from src.mcp_server import (
    CreateDocumentInput,
    CreatePrimitiveInput,
    BooleanOperationInput,
    GetViewInput,
    format_object_info,
)
from src.freecad_client import ObjectInfo


class TestInputModels:
    """Test input model validation."""

    def test_create_document_defaults(self):
        """Test create_document default values."""
        inp = CreateDocumentInput()
        assert inp.name == "Unnamed"

    def test_create_document_custom(self):
        """Test create_document with custom name."""
        inp = CreateDocumentInput(name="MyDoc")
        assert inp.name == "MyDoc"

    def test_create_primitive_box(self):
        """Test box primitive input."""
        inp = CreatePrimitiveInput(
            primitive_type="box",
            name="MyBox",
            length=100,
            width=50,
            height=30,
        )
        assert inp.primitive_type == "box"
        assert inp.length == 100
        assert inp.width == 50
        assert inp.height == 30

    def test_create_primitive_cylinder(self):
        """Test cylinder primitive input."""
        inp = CreatePrimitiveInput(
            primitive_type="cylinder",
            radius=25,
            height=100,
        )
        assert inp.primitive_type == "cylinder"
        assert inp.radius == 25
        assert inp.height == 100

    def test_boolean_operation(self):
        """Test boolean operation input."""
        inp = BooleanOperationInput(
            operation="union",
            obj1_name="Box1",
            obj2_name="Box2",
        )
        assert inp.operation == "union"
        assert inp.obj1_name == "Box1"
        assert inp.result_name is None

    def test_get_view_defaults(self):
        """Test get_view default values."""
        inp = GetViewInput()
        assert inp.view_angle == "isometric"
        assert inp.width == 800
        assert inp.height == 600


class TestFormatObjectInfo:
    """Test object info formatting."""

    def test_basic_format(self):
        """Test basic object formatting."""
        obj = ObjectInfo(
            name="Box1",
            type="Part::Box",
            label="My Box",
        )
        result = format_object_info(obj)
        assert "Name: Box1" in result
        assert "Type: Part::Box" in result
        assert "Label: My Box" in result

    def test_format_with_placement(self):
        """Test formatting with placement."""
        obj = ObjectInfo(
            name="Box1",
            type="Part::Box",
            label="My Box",
            placement={"x": 10.0, "y": 20.0, "z": 30.0},
        )
        result = format_object_info(obj)
        assert "Position:" in result
        assert "10" in result
        assert "20" in result
        assert "30" in result

    def test_format_with_properties(self):
        """Test formatting with properties."""
        obj = ObjectInfo(
            name="Box1",
            type="Part::Box",
            label="My Box",
            properties={"Length": 100, "Width": 50},
        )
        result = format_object_info(obj)
        assert "Properties:" in result
        assert "Length: 100" in result
        assert "Width: 50" in result


class TestToolSchemas:
    """Test tool JSON schemas."""

    def test_create_document_schema(self):
        """Test create_document schema generation."""
        schema = CreateDocumentInput.model_json_schema()
        assert "properties" in schema
        assert "name" in schema["properties"]

    def test_create_primitive_schema(self):
        """Test create_primitive schema generation."""
        schema = CreatePrimitiveInput.model_json_schema()
        assert "primitive_type" in schema["properties"]
        assert "required" in schema
        assert "primitive_type" in schema["required"]

    def test_boolean_operation_schema(self):
        """Test boolean_operation schema generation."""
        schema = BooleanOperationInput.model_json_schema()
        assert "operation" in schema["properties"]
        assert "obj1_name" in schema["properties"]
        assert "obj2_name" in schema["properties"]
