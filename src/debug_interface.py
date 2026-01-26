"""Gradio debug interface with Cloudflare tunnel support."""

import asyncio
import io
import logging
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import gradio as gr
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class RequestRecord:
    """Record of an MCP tool request."""

    id: str
    timestamp: datetime
    tool_name: str
    arguments: dict[str, Any]
    result: str | None = None
    error: str | None = None
    image: Image.Image | None = None
    duration_ms: float | None = None


class RequestTracker:
    """Track MCP requests for display in debug interface."""

    def __init__(self, max_records: int = 100):
        """Initialize tracker.

        Args:
            max_records: Maximum number of records to keep
        """
        self.max_records = max_records
        self.records: list[RequestRecord] = []
        self._lock = threading.Lock()
        self._counter = 0

    def add_request(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> str:
        """Add a new request record.

        Args:
            tool_name: Name of the tool called
            arguments: Tool arguments

        Returns:
            Request ID
        """
        with self._lock:
            self._counter += 1
            request_id = f"req_{self._counter}"

            record = RequestRecord(
                id=request_id,
                timestamp=datetime.now(),
                tool_name=tool_name,
                arguments=arguments,
            )
            self.records.append(record)

            # Trim old records
            if len(self.records) > self.max_records:
                self.records = self.records[-self.max_records :]

            return request_id

    def update_result(
        self,
        request_id: str,
        result: str | None = None,
        error: str | None = None,
        image: Image.Image | None = None,
        duration_ms: float | None = None,
    ) -> None:
        """Update a request with its result.

        Args:
            request_id: Request ID
            result: Result text
            error: Error message if failed
            image: Result image if any
            duration_ms: Duration in milliseconds
        """
        with self._lock:
            for record in reversed(self.records):
                if record.id == request_id:
                    record.result = result
                    record.error = error
                    record.image = image
                    record.duration_ms = duration_ms
                    break

    def get_records(self, limit: int = 20) -> list[RequestRecord]:
        """Get recent request records.

        Args:
            limit: Maximum number of records

        Returns:
            List of records, newest first
        """
        with self._lock:
            return list(reversed(self.records[-limit:]))

    def get_images(self, limit: int = 10) -> list[tuple[Image.Image, str]]:
        """Get recent images with captions.

        Args:
            limit: Maximum number of images

        Returns:
            List of (image, caption) tuples
        """
        images = []
        with self._lock:
            for record in reversed(self.records):
                if record.image is not None:
                    caption = f"{record.tool_name} @ {record.timestamp.strftime('%H:%M:%S')}"
                    images.append((record.image, caption))
                    if len(images) >= limit:
                        break
        return images


class CloudflareTunnel:
    """Manage Cloudflare Quick Tunnel."""

    def __init__(self, port: int = 7860):
        """Initialize tunnel manager.

        Args:
            port: Local port to tunnel
        """
        self.port = port
        self.process: subprocess.Popen | None = None
        self.url: str | None = None
        self._lock = threading.Lock()

    def start(self) -> str | None:
        """Start Cloudflare tunnel.

        Returns:
            Public URL or None if failed
        """
        with self._lock:
            if self.process is not None:
                return self.url

            try:
                # Check if cloudflared is available
                subprocess.run(
                    ["cloudflared", "--version"],
                    capture_output=True,
                    check=True,
                )
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.warning("cloudflared not found, tunnel unavailable")
                return None

            try:
                # Start tunnel
                self.process = subprocess.Popen(
                    ["cloudflared", "tunnel", "--url", f"http://localhost:{self.port}"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )

                # Wait for URL in output
                start_time = time.time()
                while time.time() - start_time < 30:  # 30 second timeout
                    if self.process.poll() is not None:
                        logger.error("cloudflared process exited unexpectedly")
                        return None

                    line = self.process.stdout.readline()
                    if "trycloudflare.com" in line:
                        # Extract URL
                        import re
                        match = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
                        if match:
                            self.url = match.group(0)
                            logger.info(f"Cloudflare tunnel started: {self.url}")
                            return self.url

                    time.sleep(0.1)

                logger.error("Timeout waiting for Cloudflare tunnel URL")
                self.stop()
                return None

            except Exception as e:
                logger.exception(f"Failed to start Cloudflare tunnel: {e}")
                return None

    def stop(self) -> None:
        """Stop Cloudflare tunnel."""
        with self._lock:
            if self.process is not None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                self.process = None
                self.url = None
                logger.info("Cloudflare tunnel stopped")

    @property
    def is_running(self) -> bool:
        """Check if tunnel is running."""
        with self._lock:
            return self.process is not None and self.process.poll() is None


# Global instances
request_tracker = RequestTracker()
tunnel: CloudflareTunnel | None = None


def create_debug_interface(
    freecad_client: Any = None,
    enable_tunnel: bool = True,
    port: int = 7860,
) -> gr.Blocks:
    """Create Gradio debug interface.

    Args:
        freecad_client: FreeCAD client for direct testing
        enable_tunnel: Whether to enable Cloudflare tunnel
        port: Port to run on

    Returns:
        Gradio Blocks interface
    """
    global tunnel

    if enable_tunnel:
        tunnel = CloudflareTunnel(port=port)

    def get_status() -> str:
        """Get current status."""
        lines = ["### FreeCAD MCP Debug Interface\n"]

        # Tunnel status
        if tunnel and tunnel.is_running:
            lines.append(f"**Public URL:** {tunnel.url}")
        elif tunnel:
            lines.append("**Tunnel:** Not running")
        else:
            lines.append("**Tunnel:** Disabled")

        # FreeCAD connection
        if freecad_client:
            try:
                if freecad_client.ping():
                    lines.append("**FreeCAD:** Connected")
                else:
                    lines.append("**FreeCAD:** Not responding")
            except Exception:
                lines.append("**FreeCAD:** Disconnected")
        else:
            lines.append("**FreeCAD:** Client not configured")

        # Request stats
        records = request_tracker.get_records(100)
        lines.append(f"\n**Total requests:** {len(records)}")

        return "\n".join(lines)

    def get_request_history() -> str:
        """Get formatted request history."""
        records = request_tracker.get_records(20)
        if not records:
            return "No requests yet"

        lines = []
        for record in records:
            ts = record.timestamp.strftime("%H:%M:%S")
            status = "✓" if record.result else "✗" if record.error else "..."
            duration = f" ({record.duration_ms:.0f}ms)" if record.duration_ms else ""
            lines.append(f"[{ts}] {status} **{record.tool_name}**{duration}")

            # Show brief arguments
            args_str = ", ".join(f"{k}={v!r}" for k, v in list(record.arguments.items())[:3])
            if len(record.arguments) > 3:
                args_str += ", ..."
            lines.append(f"  Args: {args_str}")

            if record.error:
                lines.append(f"  Error: {record.error}")

            lines.append("")

        return "\n".join(lines)

    def get_gallery_images() -> list[tuple[Image.Image, str]]:
        """Get images for gallery."""
        return request_tracker.get_images(10)

    def start_tunnel() -> str:
        """Start Cloudflare tunnel."""
        if tunnel is None:
            return "Tunnel not configured"
        url = tunnel.start()
        if url:
            return f"Tunnel started: {url}"
        return "Failed to start tunnel"

    def stop_tunnel() -> str:
        """Stop Cloudflare tunnel."""
        if tunnel is None:
            return "Tunnel not configured"
        tunnel.stop()
        return "Tunnel stopped"

    def test_connection() -> str:
        """Test FreeCAD connection."""
        if freecad_client is None:
            return "FreeCAD client not configured"
        try:
            if freecad_client.ping():
                return "FreeCAD connection OK"
            return "FreeCAD not responding"
        except Exception as e:
            return f"Connection error: {e}"

    def execute_test_code(code: str) -> tuple[str, Image.Image | None]:
        """Execute test code and return result."""
        if freecad_client is None:
            return "FreeCAD client not configured", None

        try:
            result = freecad_client.execute_code(code)
            output = []
            if result.get("success"):
                output.append("Success!")
                if result.get("result"):
                    output.append(f"Result: {result['result']}")
            else:
                output.append("Failed!")
                if result.get("error"):
                    output.append(f"Error: {result['error']}")

            if result.get("stdout"):
                output.append(f"\nOutput:\n{result['stdout']}")

            # Try to get a view
            image = None
            try:
                image = freecad_client.get_view()
            except Exception:
                pass

            return "\n".join(output), image

        except Exception as e:
            return f"Error: {e}", None

    # Build interface
    with gr.Blocks(title="FreeCAD MCP Debug") as interface:
        gr.Markdown("# FreeCAD MCP Debug Interface")

        with gr.Row():
            with gr.Column(scale=2):
                status_md = gr.Markdown(get_status)
                refresh_btn = gr.Button("Refresh Status")
                refresh_btn.click(get_status, outputs=status_md)

            with gr.Column(scale=1):
                with gr.Row():
                    tunnel_start_btn = gr.Button("Start Tunnel")
                    tunnel_stop_btn = gr.Button("Stop Tunnel")
                tunnel_status = gr.Textbox(label="Tunnel Status", interactive=False)
                tunnel_start_btn.click(start_tunnel, outputs=tunnel_status)
                tunnel_stop_btn.click(stop_tunnel, outputs=tunnel_status)

        with gr.Tabs():
            with gr.Tab("Request History"):
                history_md = gr.Markdown(get_request_history)
                refresh_history_btn = gr.Button("Refresh History")
                refresh_history_btn.click(get_request_history, outputs=history_md)

            with gr.Tab("Gallery"):
                gallery = gr.Gallery(
                    label="Rendered Views",
                    show_label=True,
                    columns=3,
                    height="auto",
                )
                refresh_gallery_btn = gr.Button("Refresh Gallery")
                refresh_gallery_btn.click(get_gallery_images, outputs=gallery)

            with gr.Tab("Test Console"):
                test_code = gr.Code(
                    label="Python Code",
                    language="python",
                    value="""# Test FreeCAD code
import FreeCAD
doc = FreeCAD.newDocument("Test")
box = doc.addObject("Part::Box", "TestBox")
box.Length = 100
box.Width = 50
box.Height = 30
doc.recompute()
print(f"Created box: {box.Name}")
""",
                )
                run_btn = gr.Button("Run Code")
                test_output = gr.Textbox(label="Output", lines=10)
                test_image = gr.Image(label="Result", type="pil")
                run_btn.click(
                    execute_test_code,
                    inputs=test_code,
                    outputs=[test_output, test_image],
                )

            with gr.Tab("Connection"):
                conn_status = gr.Textbox(label="Connection Status", interactive=False)
                test_conn_btn = gr.Button("Test Connection")
                test_conn_btn.click(test_connection, outputs=conn_status)

        # Initial status load
        interface.load(get_status, outputs=status_md)

    return interface


def launch_debug_interface(
    freecad_client: Any = None,
    enable_tunnel: bool = True,
    port: int = 7860,
    share: bool = False,
) -> None:
    """Launch the debug interface.

    Args:
        freecad_client: FreeCAD client for testing
        enable_tunnel: Enable Cloudflare tunnel
        port: Port to run on
        share: Use Gradio's share feature (alternative to Cloudflare)
    """
    interface = create_debug_interface(
        freecad_client=freecad_client,
        enable_tunnel=enable_tunnel,
        port=port,
    )

    # Start tunnel if enabled
    if enable_tunnel and tunnel:
        url = tunnel.start()
        if url:
            logger.info(f"Debug interface available at: {url}")

    interface.launch(
        server_name="0.0.0.0",
        server_port=port,
        share=share,
    )


def main():
    """Run debug interface standalone."""
    import argparse

    parser = argparse.ArgumentParser(description="FreeCAD MCP Debug Interface")
    parser.add_argument("--port", type=int, default=7860, help="Port to run on")
    parser.add_argument("--no-tunnel", action="store_true", help="Disable Cloudflare tunnel")
    parser.add_argument("--share", action="store_true", help="Use Gradio share")
    parser.add_argument("--freecad-host", default="localhost", help="FreeCAD host")
    parser.add_argument("--freecad-port", type=int, default=9875, help="FreeCAD port")
    args = parser.parse_args()

    # Create FreeCAD client
    from .freecad_client import FreeCADClient
    client = FreeCADClient(host=args.freecad_host, port=args.freecad_port)

    launch_debug_interface(
        freecad_client=client,
        enable_tunnel=not args.no_tunnel,
        port=args.port,
        share=args.share,
    )


if __name__ == "__main__":
    main()
