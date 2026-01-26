"""Tests for FreeCAD client."""

import pytest
from unittest.mock import MagicMock, patch

from src.freecad_client import FreeCADClient, ObjectInfo, DocumentInfo


class TestFreeCADClient:
    """Test FreeCAD XML-RPC client."""

    def test_init(self):
        """Test client initialization."""
        client = FreeCADClient(host="testhost", port=1234)
        assert client.host == "testhost"
        assert client.port == 1234
        assert client._url == "http://testhost:1234"

    def test_ping_success(self):
        """Test successful ping."""
        client = FreeCADClient()
        client._proxy = MagicMock()
        client._proxy.ping.return_value = "pong"

        assert client.ping() is True

    def test_ping_failure(self):
        """Test failed ping."""
        client = FreeCADClient()
        client._proxy = MagicMock()
        client._proxy.ping.side_effect = Exception("Connection refused")

        assert client.ping() is False

    def test_create_document(self):
        """Test document creation."""
        client = FreeCADClient()
        client._proxy = MagicMock()
        client._proxy.create_document.return_value = "TestDoc"

        result = client.create_document("TestDoc")
        assert result == "TestDoc"
        client._proxy.create_document.assert_called_once_with("TestDoc")

    def test_create_primitive_box(self):
        """Test box primitive creation."""
        client = FreeCADClient()
        client._proxy = MagicMock()
        client._proxy.create_primitive.return_value = "Box001"

        result = client.create_primitive(
            "box",
            name="MyBox",
            length=100,
            width=50,
            height=30,
        )

        assert result == "Box001"
        client._proxy.create_primitive.assert_called_once()

    def test_boolean_operation(self):
        """Test boolean operations."""
        client = FreeCADClient()
        client._proxy = MagicMock()
        client._proxy.boolean_operation.return_value = "Fusion001"

        result = client.boolean_operation(
            "union",
            "Box1",
            "Box2",
            result_name="Combined",
        )

        assert result == "Fusion001"

    def test_transform_object(self):
        """Test object transformation."""
        client = FreeCADClient()
        client._proxy = MagicMock()
        client._proxy.transform_object.return_value = True

        result = client.transform_object(
            "Box1",
            translate=(10, 20, 30),
            rotate=(0, 0, 45),
        )

        assert result is True

    def test_get_objects(self):
        """Test getting object list."""
        client = FreeCADClient()
        client._proxy = MagicMock()
        client._proxy.get_objects.return_value = [
            {"name": "Box1", "type": "Part::Box", "label": "My Box"},
            {"name": "Cyl1", "type": "Part::Cylinder", "label": "My Cylinder"},
        ]

        objects = client.get_objects()

        assert len(objects) == 2
        assert objects[0].name == "Box1"
        assert objects[0].type == "Part::Box"
        assert objects[1].name == "Cyl1"

    def test_list_documents(self):
        """Test listing documents."""
        client = FreeCADClient()
        client._proxy = MagicMock()
        client._proxy.list_documents.return_value = [
            {"name": "Doc1", "file_path": "/tmp/doc1.FCStd", "objects": ["Box1"], "modified": False},
        ]

        docs = client.list_documents()

        assert len(docs) == 1
        assert docs[0].name == "Doc1"
        assert docs[0].file_path == "/tmp/doc1.FCStd"


class TestObjectInfo:
    """Test ObjectInfo dataclass."""

    def test_basic_object(self):
        """Test basic object info."""
        obj = ObjectInfo(
            name="Box1",
            type="Part::Box",
            label="My Box",
        )

        assert obj.name == "Box1"
        assert obj.type == "Part::Box"
        assert obj.label == "My Box"
        assert obj.properties == {}
        assert obj.placement is None

    def test_object_with_properties(self):
        """Test object with properties."""
        obj = ObjectInfo(
            name="Box1",
            type="Part::Box",
            label="My Box",
            properties={"Length": 100, "Width": 50},
            placement={"x": 10, "y": 20, "z": 30},
        )

        assert obj.properties["Length"] == 100
        assert obj.placement["x"] == 10


class TestDocumentInfo:
    """Test DocumentInfo dataclass."""

    def test_document_info(self):
        """Test document info."""
        doc = DocumentInfo(
            name="TestDoc",
            file_path="/tmp/test.FCStd",
            objects=["Box1", "Cyl1"],
            modified=True,
        )

        assert doc.name == "TestDoc"
        assert len(doc.objects) == 2
        assert doc.modified is True
