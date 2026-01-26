"""Cache management for MCP server output files.

Provides:
- Timestamped session directories for organized file storage
- Automatic cleanup when cache exceeds size limits
- Cross-platform compatible paths within the project directory
"""

import logging
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default settings
DEFAULT_MAX_CACHE_SIZE_MB = 1024  # 1GB
DEFAULT_MIN_SESSIONS_TO_KEEP = 1


def get_project_root() -> Path:
    """Get the project root directory."""
    # This file is at src/cache_manager.py, so project root is parent of src/
    return Path(__file__).parent.parent


class CacheManager:
    """Manages cached output files with automatic cleanup."""

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        max_size_mb: int = DEFAULT_MAX_CACHE_SIZE_MB,
        min_sessions_to_keep: int = DEFAULT_MIN_SESSIONS_TO_KEEP,
    ):
        """Initialize cache manager.

        Args:
            cache_dir: Cache directory path (default: {project_root}/cache)
            max_size_mb: Maximum cache size in MB before cleanup
            min_sessions_to_keep: Minimum number of session folders to keep
        """
        if cache_dir is None:
            self.cache_dir = get_project_root() / "cache"
        else:
            self.cache_dir = Path(cache_dir)

        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.min_sessions_to_keep = min_sessions_to_keep
        self._current_session: Path | None = None

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_session_dir(self) -> Path:
        """Get or create the current session directory.

        Returns:
            Path to current session directory (timestamped)
        """
        if self._current_session is None:
            # Create timestamped session directory
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._current_session = self.cache_dir / f"session_{timestamp}"
            self._current_session.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created session directory: {self._current_session}")

        return self._current_session

    def get_output_path(self, filename: str, subdir: str | None = None) -> Path:
        """Get a path for an output file in the current session.

        Args:
            filename: Name of the file
            subdir: Optional subdirectory within session

        Returns:
            Full path for the output file
        """
        session = self.get_session_dir()

        if subdir:
            output_dir = session / subdir
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = session

        return output_dir / filename

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all session directories with metadata.

        Returns:
            List of dicts with 'path', 'name', 'created', 'size_bytes'
        """
        sessions = []

        for item in self.cache_dir.iterdir():
            if item.is_dir() and item.name.startswith("session_"):
                try:
                    # Parse timestamp from directory name
                    timestamp_str = item.name.replace("session_", "")
                    created = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                except ValueError:
                    # Fallback to modification time
                    created = datetime.fromtimestamp(item.stat().st_mtime)

                # Calculate directory size
                size = self._get_dir_size(item)

                sessions.append({
                    "path": item,
                    "name": item.name,
                    "created": created,
                    "size_bytes": size,
                })

        # Sort by creation time (oldest first)
        sessions.sort(key=lambda x: x["created"])
        return sessions

    def _get_dir_size(self, path: Path) -> int:
        """Get total size of a directory in bytes."""
        total = 0
        try:
            for item in path.rglob("*"):
                if item.is_file():
                    total += item.stat().st_size
        except (OSError, PermissionError) as e:
            logger.warning(f"Error calculating size for {path}: {e}")
        return total

    def get_total_cache_size(self) -> int:
        """Get total cache size in bytes."""
        return self._get_dir_size(self.cache_dir)

    def cleanup(self, force: bool = False) -> dict[str, Any]:
        """Clean up old sessions if cache exceeds size limit.

        Args:
            force: Force cleanup even if under size limit

        Returns:
            Dict with 'cleaned', 'sessions_removed', 'bytes_freed', 'current_size'
        """
        sessions = self.list_sessions()
        total_size = sum(s["size_bytes"] for s in sessions)

        result = {
            "cleaned": False,
            "sessions_removed": 0,
            "bytes_freed": 0,
            "initial_size": total_size,
            "current_size": total_size,
        }

        # Check if cleanup is needed
        if not force and total_size <= self.max_size_bytes:
            logger.debug(f"Cache size {total_size / 1024 / 1024:.1f}MB is under limit")
            return result

        logger.info(
            f"Cache cleanup triggered: {total_size / 1024 / 1024:.1f}MB "
            f"(limit: {self.max_size_bytes / 1024 / 1024:.1f}MB)"
        )

        # Remove oldest sessions until under limit or at minimum
        sessions_to_remove = []
        remaining_size = total_size

        for session in sessions:
            # Keep minimum number of sessions
            remaining_sessions = len(sessions) - len(sessions_to_remove)
            if remaining_sessions <= self.min_sessions_to_keep:
                break

            # Skip current session
            if self._current_session and session["path"] == self._current_session:
                continue

            # Check if we're under the limit
            if remaining_size <= self.max_size_bytes:
                break

            sessions_to_remove.append(session)
            remaining_size -= session["size_bytes"]

        # Remove the sessions
        for session in sessions_to_remove:
            try:
                shutil.rmtree(session["path"])
                result["sessions_removed"] += 1
                result["bytes_freed"] += session["size_bytes"]
                logger.info(f"Removed old session: {session['name']}")
            except Exception as e:
                logger.error(f"Failed to remove session {session['path']}: {e}")

        result["cleaned"] = result["sessions_removed"] > 0
        result["current_size"] = total_size - result["bytes_freed"]

        if result["cleaned"]:
            logger.info(
                f"Cleanup complete: removed {result['sessions_removed']} sessions, "
                f"freed {result['bytes_freed'] / 1024 / 1024:.1f}MB"
            )

        return result

    def get_status(self) -> dict[str, Any]:
        """Get cache status information.

        Returns:
            Dict with cache statistics
        """
        sessions = self.list_sessions()
        total_size = sum(s["size_bytes"] for s in sessions)

        return {
            "cache_dir": str(self.cache_dir),
            "session_count": len(sessions),
            "total_size_bytes": total_size,
            "total_size_mb": total_size / 1024 / 1024,
            "max_size_mb": self.max_size_bytes / 1024 / 1024,
            "usage_percent": (total_size / self.max_size_bytes * 100) if self.max_size_bytes > 0 else 0,
            "current_session": str(self._current_session) if self._current_session else None,
            "sessions": [
                {
                    "name": s["name"],
                    "created": s["created"].isoformat(),
                    "size_mb": s["size_bytes"] / 1024 / 1024,
                }
                for s in sessions
            ],
        }


# Global cache manager instance
_cache_manager: CacheManager | None = None


def get_cache_manager() -> CacheManager:
    """Get or create the global cache manager."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


def init_cache(max_size_mb: int = DEFAULT_MAX_CACHE_SIZE_MB) -> CacheManager:
    """Initialize cache manager and run cleanup.

    Call this at MCP server startup.

    Args:
        max_size_mb: Maximum cache size in MB

    Returns:
        Initialized cache manager
    """
    global _cache_manager
    _cache_manager = CacheManager(max_size_mb=max_size_mb)

    # Run cleanup on startup
    cleanup_result = _cache_manager.cleanup()
    if cleanup_result["cleaned"]:
        logger.info(
            f"Startup cleanup: removed {cleanup_result['sessions_removed']} old sessions, "
            f"freed {cleanup_result['bytes_freed'] / 1024 / 1024:.1f}MB"
        )

    return _cache_manager


def get_output_path(filename: str, subdir: str | None = None) -> Path:
    """Convenience function to get output path from global cache manager.

    Args:
        filename: Name of the file
        subdir: Optional subdirectory (e.g., 'segmentation', 'screenshots')

    Returns:
        Full path for the output file
    """
    return get_cache_manager().get_output_path(filename, subdir)


def get_session_dir() -> Path:
    """Convenience function to get current session directory."""
    return get_cache_manager().get_session_dir()
