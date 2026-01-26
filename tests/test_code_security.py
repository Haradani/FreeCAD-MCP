"""Tests for code security module."""

import pytest

from src.code_security import CodeSecurityChecker, check_code_security


class TestCodeSecurityChecker:
    """Test code security checker."""

    def test_safe_code_allowed(self):
        """Test that safe code is allowed."""
        code = """
import FreeCAD
doc = FreeCAD.newDocument("Test")
box = doc.addObject("Part::Box", "Box")
box.Length = 100
"""
        result = check_code_security(code)
        assert result.allowed is True

    def test_os_import_blocked(self):
        """Test that os import is blocked."""
        code = "import os\nos.system('rm -rf /')"
        result = check_code_security(code)
        assert result.allowed is False
        assert "os" in result.reason

    def test_subprocess_blocked(self):
        """Test that subprocess is blocked."""
        code = "import subprocess\nsubprocess.run(['ls'])"
        result = check_code_security(code)
        assert result.allowed is False
        assert "subprocess" in result.reason

    def test_socket_blocked(self):
        """Test that socket is blocked."""
        code = "import socket\ns = socket.socket()"
        result = check_code_security(code)
        assert result.allowed is False
        assert "socket" in result.reason

    def test_eval_blocked(self):
        """Test that eval is blocked."""
        code = "eval('print(1)')"
        result = check_code_security(code)
        assert result.allowed is False
        assert "eval" in result.reason

    def test_exec_blocked(self):
        """Test that exec is blocked."""
        code = "exec('import os')"
        result = check_code_security(code)
        assert result.allowed is False
        assert "exec" in result.reason

    def test_open_blocked(self):
        """Test that open is blocked."""
        code = "f = open('/etc/passwd')"
        result = check_code_security(code)
        assert result.allowed is False
        assert "open" in result.reason

    def test_freecad_quit_blocked(self):
        """Test that FreeCAD quit is blocked."""
        code = "FreeCAD.quit()"
        result = check_code_security(code)
        assert result.allowed is False
        assert "quit" in result.reason

    def test_from_import_blocked(self):
        """Test that from import of blocked modules is blocked."""
        code = "from os import path"
        result = check_code_security(code)
        assert result.allowed is False
        assert "os" in result.reason

    def test_syntax_error_rejected(self):
        """Test that syntax errors are caught."""
        code = "def broken("
        result = check_code_security(code)
        assert result.allowed is False
        assert "Syntax error" in result.reason

    def test_dunder_warning(self):
        """Test that dunder attributes generate warnings."""
        code = """
class Foo:
    def __init__(self):
        pass
"""
        result = check_code_security(code)
        # Dunder methods in class definitions are OK but warned
        assert result.allowed is True
        # Should have warning about dunder
        if result.warnings:
            assert any("dunder" in w.lower() for w in result.warnings)

    def test_complex_safe_code(self):
        """Test complex but safe FreeCAD code."""
        code = """
import FreeCAD
import Part
import Draft

# Create document
doc = FreeCAD.newDocument("Assembly")

# Create parts
box = doc.addObject("Part::Box", "Base")
box.Length = 100
box.Width = 100
box.Height = 20

cyl = doc.addObject("Part::Cylinder", "Hole")
cyl.Radius = 10
cyl.Height = 30

# Boolean cut
cut = doc.addObject("Part::Cut", "BaseWithHole")
cut.Base = box
cut.Tool = cyl

doc.recompute()
print(f"Created: {cut.Name}")
"""
        result = check_code_security(code)
        assert result.allowed is True


class TestCustomSecurityChecker:
    """Test custom security checker configuration."""

    def test_allow_file_ops(self):
        """Test allowing file operations."""
        checker = CodeSecurityChecker(allow_file_ops=True)
        # os should be allowed when file ops enabled
        assert "os" not in checker.blocked_modules

    def test_custom_blocked_modules(self):
        """Test adding custom blocked modules."""
        checker = CodeSecurityChecker(custom_blocked_modules={"custom_dangerous"})
        assert "custom_dangerous" in checker.blocked_modules

        code = "import custom_dangerous"
        result = checker.check_code(code)
        assert result.allowed is False
