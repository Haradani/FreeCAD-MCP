"""Cloudflare tunnel management for public URL access."""

import asyncio
import logging
import os
import re
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TunnelInfo:
    """Information about an active tunnel."""

    name: str
    local_port: int
    public_url: str | None = None
    process: subprocess.Popen | None = field(default=None, repr=False)
    status: str = "starting"
    error: str | None = None


class TunnelClient:
    """Manages Cloudflare Quick Tunnels for public URL access."""

    def __init__(self):
        """Initialize tunnel client."""
        self._tunnels: dict[str, TunnelInfo] = {}
        self._cloudflared_path = self._find_cloudflared()

    def _find_cloudflared(self) -> str | None:
        """Find cloudflared binary."""
        # Check common locations
        paths = [
            "/usr/local/bin/cloudflared",
            "/usr/bin/cloudflared",
            os.path.expanduser("~/.local/bin/cloudflared"),
            "cloudflared",  # In PATH
        ]

        for path in paths:
            try:
                result = subprocess.run(
                    [path, "version"],
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    return path
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

        return None

    def is_available(self) -> bool:
        """Check if cloudflared is available."""
        return self._cloudflared_path is not None

    def get_install_instructions(self) -> str:
        """Get instructions for installing cloudflared."""
        return """cloudflared is not installed. Install with:

# Linux (Debian/Ubuntu)
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb

# Or download binary directly
wget -O ~/.local/bin/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
chmod +x ~/.local/bin/cloudflared
"""

    def create_tunnel(
        self,
        name: str,
        local_port: int,
        local_host: str = "localhost",
        protocol: str = "http",
    ) -> dict[str, Any]:
        """Create a Cloudflare Quick Tunnel to expose a local port.

        Args:
            name: Friendly name for this tunnel
            local_port: Local port to expose
            local_host: Local hostname (default: localhost)
            protocol: Protocol (http or https)

        Returns:
            Dict with success status and tunnel info
        """
        if not self.is_available():
            return {
                "success": False,
                "error": "cloudflared not installed",
                "install_instructions": self.get_install_instructions(),
            }

        # Clean up dead tunnels first
        self._cleanup_dead_tunnels()

        # Check if tunnel with this name already exists
        if name in self._tunnels:
            existing = self._tunnels[name]
            if existing.process and existing.process.poll() is None:
                return {
                    "success": True,
                    "message": "Tunnel already running",
                    "public_url": existing.public_url,
                    "name": name,
                    "local_port": local_port,
                }

        # Build local URL
        local_url = f"{protocol}://{local_host}:{local_port}"

        try:
            # Start cloudflared tunnel
            # Using Quick Tunnel (no account required)
            cmd = [
                self._cloudflared_path,
                "tunnel",
                "--url", local_url,
            ]

            logger.info(f"Starting tunnel: {' '.join(cmd)}")

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            # Create tunnel info
            tunnel = TunnelInfo(
                name=name,
                local_port=local_port,
                process=process,
                status="starting",
            )
            self._tunnels[name] = tunnel

            # Wait for URL to appear in output (with timeout)
            public_url = None
            start_time = time.time()
            timeout = 30

            while time.time() - start_time < timeout:
                if process.poll() is not None:
                    # Process ended
                    remaining = process.stdout.read() if process.stdout else ""
                    tunnel.status = "failed"
                    tunnel.error = f"Process exited with code {process.returncode}"
                    return {
                        "success": False,
                        "error": tunnel.error,
                        "output": remaining,
                    }

                line = process.stdout.readline() if process.stdout else ""
                if not line:
                    time.sleep(0.1)
                    continue

                logger.debug(f"cloudflared: {line.strip()}")

                # Look for the public URL
                # Format: "https://xxx-xxx-xxx.trycloudflare.com"
                url_match = re.search(r'https://[a-z0-9-]+\.trycloudflare\.com', line)
                if url_match:
                    public_url = url_match.group(0)
                    break

            if public_url:
                tunnel.public_url = public_url
                tunnel.status = "running"

                return {
                    "success": True,
                    "public_url": public_url,
                    "name": name,
                    "local_port": local_port,
                    "local_url": local_url,
                    "message": f"Tunnel created: {public_url} -> {local_url}",
                }
            else:
                tunnel.status = "timeout"
                tunnel.error = "Timeout waiting for public URL"
                # Don't kill process - it might still be starting
                return {
                    "success": False,
                    "error": "Timeout waiting for public URL",
                    "name": name,
                }

        except Exception as e:
            logger.exception(f"Failed to create tunnel: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def stop_tunnel(self, name: str) -> dict[str, Any]:
        """Stop a running tunnel.

        Args:
            name: Tunnel name

        Returns:
            Dict with success status
        """
        if name not in self._tunnels:
            return {
                "success": False,
                "error": f"Tunnel '{name}' not found",
            }

        tunnel = self._tunnels[name]

        if tunnel.process:
            try:
                tunnel.process.terminate()
                tunnel.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                tunnel.process.kill()
            except Exception as e:
                logger.warning(f"Error stopping tunnel: {e}")

        tunnel.status = "stopped"
        del self._tunnels[name]

        return {
            "success": True,
            "message": f"Tunnel '{name}' stopped",
        }

    def _cleanup_dead_tunnels(self) -> list[str]:
        """Remove tunnels whose processes have died.

        Returns:
            List of removed tunnel names
        """
        dead_tunnels = []
        for name, tunnel in list(self._tunnels.items()):
            if tunnel.process:
                poll_result = tunnel.process.poll()
                if poll_result is not None:
                    # Process has exited
                    dead_tunnels.append(name)
                    del self._tunnels[name]
                    logger.info(f"Cleaned up dead tunnel '{name}' (exit code: {poll_result})")
        return dead_tunnels

    def get_tunnel_status(self, name: str | None = None) -> list[dict[str, Any]]:
        """Get status of one or all tunnels.

        Args:
            name: Tunnel name (None for all)

        Returns:
            List of tunnel status dicts
        """
        # Clean up dead tunnels first
        self._cleanup_dead_tunnels()

        results = []

        tunnels_to_check = (
            {name: self._tunnels.get(name)}
            if name
            else self._tunnels
        )

        for tunnel_name, tunnel in tunnels_to_check.items():
            if tunnel is None:
                results.append({
                    "name": tunnel_name,
                    "status": "not found",
                })
                continue

            # Double-check process status
            status = tunnel.status
            if tunnel.process:
                poll_result = tunnel.process.poll()
                if poll_result is not None:
                    status = "stopped"

            results.append({
                "name": tunnel.name,
                "local_port": tunnel.local_port,
                "public_url": tunnel.public_url,
                "status": status,
                "error": tunnel.error,
            })

        return results

    def list_tunnels(self) -> list[dict[str, Any]]:
        """List all active tunnels (automatically removes dead ones).

        Returns:
            List of tunnel info dicts for running tunnels only
        """
        # Clean up dead tunnels first
        self._cleanup_dead_tunnels()

        # Only return tunnels that are actually running
        return [
            {
                "name": tunnel.name,
                "local_port": tunnel.local_port,
                "public_url": tunnel.public_url,
                "status": tunnel.status,
            }
            for tunnel in self._tunnels.values()
            if tunnel.process and tunnel.process.poll() is None
        ]

    def stop_all_tunnels(self) -> dict[str, Any]:
        """Stop all running tunnels.

        Returns:
            Dict with results
        """
        stopped = []
        errors = []

        for name in list(self._tunnels.keys()):
            result = self.stop_tunnel(name)
            if result["success"]:
                stopped.append(name)
            else:
                errors.append(f"{name}: {result.get('error')}")

        return {
            "success": len(errors) == 0,
            "stopped": stopped,
            "errors": errors if errors else None,
        }


# Global client instance
_tunnel_client: TunnelClient | None = None


def get_tunnel_client() -> TunnelClient:
    """Get or create the global tunnel client."""
    global _tunnel_client
    if _tunnel_client is None:
        _tunnel_client = TunnelClient()
    return _tunnel_client
