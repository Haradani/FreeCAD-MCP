"""Security checks for execute_code tool."""

import ast
import re
from dataclasses import dataclass


# Dangerous modules that should be blocked or require approval
BLOCKED_MODULES = {
    "os",
    "subprocess",
    "sys",
    "shutil",
    "socket",
    "requests",
    "urllib",
    "http",
    "ftplib",
    "smtplib",
    "telnetlib",
    "pickle",
    "marshal",
    "shelve",
    "ctypes",
    "multiprocessing",
    "threading",
    "_thread",
    "asyncio",
    "concurrent",
}

# Dangerous built-in functions
BLOCKED_BUILTINS = {
    "eval",
    "exec",
    "compile",
    "__import__",
    "open",
    "input",
    "breakpoint",
}

# Patterns that indicate potentially dangerous operations
DANGEROUS_PATTERNS = [
    r"__\w+__",  # Dunder methods (could be used for sandbox escape)
    r"\.read\s*\(",  # File reading
    r"\.write\s*\(",  # File writing
    r"\.system\s*\(",  # System calls
    r"\.popen\s*\(",  # Process opening
    r"\.remove\s*\(",  # File deletion
    r"\.rmdir\s*\(",  # Directory deletion
    r"\.unlink\s*\(",  # File unlinking
    r"\.chmod\s*\(",  # Permission changes
    r"\.chown\s*\(",  # Owner changes
]


@dataclass
class SecurityCheckResult:
    """Result of a security check."""

    allowed: bool
    reason: str | None = None
    warnings: list[str] | None = None


class CodeSecurityChecker:
    """Check Python code for security issues before execution."""

    def __init__(
        self,
        allow_file_ops: bool = False,
        allow_network: bool = False,
        custom_blocked_modules: set[str] | None = None,
    ):
        """Initialize security checker.

        Args:
            allow_file_ops: Allow file operations (open, read, write)
            allow_network: Allow network operations
            custom_blocked_modules: Additional modules to block
        """
        self.allow_file_ops = allow_file_ops
        self.allow_network = allow_network
        self.blocked_modules = BLOCKED_MODULES.copy()
        if custom_blocked_modules:
            self.blocked_modules.update(custom_blocked_modules)

        # If file ops allowed, remove os from blocked (but still block dangerous attrs)
        if allow_file_ops:
            self.blocked_modules.discard("os")
            self.blocked_modules.discard("shutil")

    def check_code(self, code: str) -> SecurityCheckResult:
        """Check code for security issues.

        Args:
            code: Python code to check

        Returns:
            SecurityCheckResult with allowed status and reason
        """
        warnings = []

        # Try to parse as AST
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return SecurityCheckResult(
                allowed=False,
                reason=f"Syntax error: {e}",
            )

        # Check imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name.split(".")[0]
                    if module in self.blocked_modules:
                        return SecurityCheckResult(
                            allowed=False,
                            reason=f"Blocked module import: {alias.name}",
                        )

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module = node.module.split(".")[0]
                    if module in self.blocked_modules:
                        return SecurityCheckResult(
                            allowed=False,
                            reason=f"Blocked module import: {node.module}",
                        )

            # Check for dangerous builtins
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in BLOCKED_BUILTINS:
                        return SecurityCheckResult(
                            allowed=False,
                            reason=f"Blocked builtin function: {node.func.id}",
                        )

        # Check for dangerous patterns
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, code):
                # Dunder methods warning (not blocking, just warning)
                if pattern == r"__\w+__":
                    warnings.append("Code contains dunder attributes (potential sandbox escape)")
                else:
                    warnings.append(f"Code contains potentially dangerous pattern: {pattern}")

        # Check for FreeCAD-specific dangerous operations
        if "App.closeDocument" in code:
            warnings.append("Code closes documents - ensure this is intended")

        if "FreeCAD.quit" in code or "FreeCADGui.quit" in code:
            return SecurityCheckResult(
                allowed=False,
                reason="Code attempts to quit FreeCAD",
            )

        return SecurityCheckResult(
            allowed=True,
            warnings=warnings if warnings else None,
        )

    def sanitize_code(self, code: str) -> str:
        """Add safety wrappers to code.

        Args:
            code: Code to sanitize

        Returns:
            Sanitized code with safety wrappers
        """
        # Wrap in a function to limit scope
        lines = code.split("\n")
        indented = "\n".join("    " + line for line in lines)

        wrapped = f"""
def __safe_execute__():
    # Restricted execution context
    import FreeCAD
    import Part
    import Draft
    try:
        import PartDesign
    except ImportError:
        pass

{indented}

__result__ = __safe_execute__()
del __safe_execute__
"""
        return wrapped


# Default checker instance
default_checker = CodeSecurityChecker()


def check_code_security(code: str) -> SecurityCheckResult:
    """Check code security using default checker.

    Args:
        code: Code to check

    Returns:
        SecurityCheckResult
    """
    return default_checker.check_code(code)
