"""Docker service management client for FreeCAD MCP."""

import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Service definitions with their profiles, compose service names, and GPU config
SERVICE_DEFINITIONS = {
    "freecad": {
        "compose_service": "freecad",
        "profile": None,  # Default service, no profile needed
        "description": "FreeCAD XML-RPC server with optional GUI",
        "supports_gui": True,
        "uses_gpu": False,
        "default_port": 9875,
    },
    "freecad-headless": {
        "compose_service": "freecad-headless",
        "profile": "headless",
        "description": "FreeCAD headless XML-RPC server (lighter)",
        "supports_gui": False,
        "uses_gpu": False,
        "default_port": 9875,
    },
    "inference": {
        "compose_service": "inference",
        "profile": "vision",
        "description": "Vision AI (Cosmos VLM on GPU 0, SAM3 on GPU 1)",
        "supports_gui": False,
        "uses_gpu": True,
        "default_gpus": "0,1",
        "default_port": 5555,
        "gpu_env_vars": ["VLM_DEVICE", "SAM_DEVICE"],
    },
    "trellis": {
        "compose_service": "trellis",
        "profile": "trellis",
        "description": "TRELLIS.2 Image-to-3D generation",
        "supports_gui": False,
        "uses_gpu": True,
        "default_gpus": "1",
        "default_port": 8000,
        "gpu_env_vars": ["CUDA_VISIBLE_DEVICES", "TRELLIS_DEVICE"],
    },
    "diffusion": {
        "compose_service": "diffusion-gen",
        "profile": "diffusion",
        "description": "ComfyUI text-to-image generation",
        "supports_gui": False,
        "uses_gpu": True,
        "default_gpus": "0",
        "default_port": 8188,
        "gpu_env_vars": ["NVIDIA_VISIBLE_DEVICES"],
    },
}


@dataclass
class ServiceStatus:
    """Status of a Docker service."""

    name: str
    running: bool
    status: str
    container_id: str | None = None
    image: str | None = None
    ports: list[str] = field(default_factory=list)
    health: str | None = None
    uptime: str | None = None
    gpu_info: str | None = None


@dataclass
class ServiceInfo:
    """Information about an available service."""

    name: str
    description: str
    profile: str | None
    supports_gui: bool
    uses_gpu: bool = False
    default_gpus: str | None = None
    default_port: int | None = None


class DockerClient:
    """Client for managing Docker Compose services."""

    def __init__(self, compose_dir: str | Path | None = None):
        """Initialize Docker client.

        Args:
            compose_dir: Directory containing docker-compose.yml
                         (default: project root)
        """
        if compose_dir is None:
            # Default to project root (parent of src/)
            compose_dir = Path(__file__).parent.parent
        self.compose_dir = Path(compose_dir)
        self.compose_file = self.compose_dir / "docker-compose.yml"

        if not self.compose_file.exists():
            raise FileNotFoundError(f"docker-compose.yml not found at {self.compose_file}")

    def _run_compose(
        self,
        args: list[str],
        timeout: int = 60,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        """Run a docker compose command.

        Args:
            args: Command arguments (without 'docker compose')
            timeout: Command timeout in seconds
            check: Whether to raise on non-zero exit

        Returns:
            CompletedProcess result
        """
        cmd = ["docker", "compose", "-f", str(self.compose_file)] + args
        logger.info(f"Running: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            cwd=str(self.compose_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if check and result.returncode != 0:
            logger.error(f"Command failed: {result.stderr}")
            raise subprocess.CalledProcessError(
                result.returncode, cmd, result.stdout, result.stderr
            )

        return result

    def list_available_services(self) -> list[ServiceInfo]:
        """List all available services that can be managed.

        Returns:
            List of service information
        """
        return [
            ServiceInfo(
                name=name,
                description=info["description"],
                profile=info["profile"],
                supports_gui=info["supports_gui"],
                uses_gpu=info.get("uses_gpu", False),
                default_gpus=info.get("default_gpus"),
                default_port=info.get("default_port"),
            )
            for name, info in SERVICE_DEFINITIONS.items()
        ]

    def get_gpu_status(self) -> list[dict[str, Any]]:
        """Get GPU status including memory usage.

        Returns:
            List of GPU info dicts
        """
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=index,name,memory.used,memory.total,memory.free,utilization.gpu",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                return []

            gpus = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 6:
                    gpus.append({
                        "index": int(parts[0]),
                        "name": parts[1],
                        "memory_used_mb": int(parts[2]),
                        "memory_total_mb": int(parts[3]),
                        "memory_free_mb": int(parts[4]),
                        "utilization_percent": int(parts[5]) if parts[5] != "[N/A]" else None,
                    })

            return gpus

        except Exception as e:
            logger.warning(f"Failed to get GPU status: {e}")
            return []

    def start_service(
        self,
        name: str,
        with_gui: bool = False,
        timeout: int = 120,
        detach: bool = True,
        gpus: str | None = None,
        rebuild: bool = False,
    ) -> dict[str, Any]:
        """Start a Docker service.

        Args:
            name: Service name (freecad, trellis, diffusion, inference)
            with_gui: Enable GUI for FreeCAD (sets ENABLE_GUI=true)
            timeout: Timeout for startup in seconds
            detach: Run in detached mode
            gpus: GPU assignment (e.g., "0", "1", "0,1"). Uses service default if not specified.
            rebuild: Force rebuild of the container image

        Returns:
            Dict with success status and message
        """
        if name not in SERVICE_DEFINITIONS:
            return {
                "success": False,
                "error": f"Unknown service: {name}. Available: {list(SERVICE_DEFINITIONS.keys())}",
            }

        service_info = SERVICE_DEFINITIONS[name]
        compose_service = service_info["compose_service"]
        profile = service_info["profile"]

        # Build command
        args = []
        if profile:
            args.extend(["--profile", profile])
        args.append("up")
        if detach:
            args.append("-d")
        if rebuild:
            args.append("--build")
        args.append(compose_service)

        # Set environment
        env = os.environ.copy()
        if with_gui and service_info["supports_gui"]:
            env["ENABLE_GUI"] = "true"

        # Handle GPU configuration
        gpu_message = ""
        if service_info.get("uses_gpu"):
            gpu_to_use = gpus if gpus else service_info.get("default_gpus", "0")

            # Set CUDA_VISIBLE_DEVICES for the compose environment
            env["CUDA_VISIBLE_DEVICES"] = gpu_to_use

            # For trellis, also set the specific env var
            if name == "trellis":
                env["TRELLIS_DEVICE"] = "cuda:0"  # Device 0 within visible devices

            gpu_message = f" on GPU {gpu_to_use}"

        try:
            cmd = ["docker", "compose", "-f", str(self.compose_file)] + args
            logger.info(f"Starting service {name}: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                cwd=str(self.compose_dir),
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": result.stderr.strip() or result.stdout.strip(),
                }

            port = service_info.get("default_port")
            port_info = f" (port {port})" if port else ""

            return {
                "success": True,
                "message": f"Service {name} started successfully{gpu_message}{port_info}",
                "output": result.stdout.strip(),
                "port": port,
                "gpus": gpus if gpus else service_info.get("default_gpus"),
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Timeout starting service {name} after {timeout}s",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def stop_service(
        self,
        name: str,
        force: bool = False,
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Stop a Docker service.

        Args:
            name: Service name
            force: Force kill the container
            timeout: Timeout for graceful stop

        Returns:
            Dict with success status and message
        """
        if name not in SERVICE_DEFINITIONS:
            return {
                "success": False,
                "error": f"Unknown service: {name}. Available: {list(SERVICE_DEFINITIONS.keys())}",
            }

        service_info = SERVICE_DEFINITIONS[name]
        compose_service = service_info["compose_service"]
        profile = service_info["profile"]

        try:
            if force:
                # Use docker kill for immediate termination
                args = []
                if profile:
                    args.extend(["--profile", profile])
                args.extend(["kill", compose_service])
            else:
                # Graceful stop
                args = []
                if profile:
                    args.extend(["--profile", profile])
                args.extend(["stop", "-t", str(timeout), compose_service])

            result = self._run_compose(args, timeout=timeout + 10, check=False)

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": result.stderr.strip() or result.stdout.strip(),
                }

            return {
                "success": True,
                "message": f"Service {name} stopped successfully",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def get_service_status(self, name: str | None = None) -> list[ServiceStatus]:
        """Get status of one or all services.

        Args:
            name: Service name (None for all services)

        Returns:
            List of service statuses
        """
        try:
            # Get container status as JSON
            result = self._run_compose(
                ["ps", "--format", "json", "-a"],
                timeout=30,
                check=False,
            )

            if result.returncode != 0:
                logger.warning(f"Failed to get status: {result.stderr}")
                return []

            # Parse JSON output (one JSON object per line)
            statuses = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                try:
                    container = json.loads(line)
                    # Find which service this container belongs to
                    service_name = container.get("Service", "")

                    # Map compose service name back to our service name
                    our_name = None
                    for svc_name, svc_info in SERVICE_DEFINITIONS.items():
                        if svc_info["compose_service"] == service_name:
                            our_name = svc_name
                            break

                    if our_name is None:
                        continue

                    # Filter by name if specified
                    if name and our_name != name:
                        continue

                    # Parse ports
                    ports = []
                    publishers = container.get("Publishers", [])
                    if publishers:
                        for pub in publishers:
                            if pub.get("PublishedPort"):
                                ports.append(
                                    f"{pub.get('PublishedPort')}->{pub.get('TargetPort')}/{pub.get('Protocol', 'tcp')}"
                                )

                    status = ServiceStatus(
                        name=our_name,
                        running=container.get("State") == "running",
                        status=container.get("Status", "unknown"),
                        container_id=container.get("ID"),
                        image=container.get("Image"),
                        ports=ports,
                        health=container.get("Health"),
                    )
                    statuses.append(status)

                except json.JSONDecodeError:
                    continue

            # If a specific service was requested but not found, return unknown status
            if name and not statuses:
                statuses.append(ServiceStatus(
                    name=name,
                    running=False,
                    status="not found",
                ))

            return statuses

        except Exception as e:
            logger.exception(f"Failed to get service status: {e}")
            return []

    def restart_service(
        self,
        name: str,
        timeout: int = 120,
    ) -> dict[str, Any]:
        """Restart a Docker service.

        Args:
            name: Service name
            timeout: Timeout for restart

        Returns:
            Dict with success status and message
        """
        if name not in SERVICE_DEFINITIONS:
            return {
                "success": False,
                "error": f"Unknown service: {name}",
            }

        service_info = SERVICE_DEFINITIONS[name]
        compose_service = service_info["compose_service"]
        profile = service_info["profile"]

        try:
            args = []
            if profile:
                args.extend(["--profile", profile])
            args.extend(["restart", compose_service])

            result = self._run_compose(args, timeout=timeout, check=False)

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": result.stderr.strip() or result.stdout.strip(),
                }

            return {
                "success": True,
                "message": f"Service {name} restarted successfully",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def get_service_logs(
        self,
        name: str,
        lines: int = 50,
        follow: bool = False,
    ) -> dict[str, Any]:
        """Get logs from a service.

        Args:
            name: Service name
            lines: Number of lines to return
            follow: Whether to follow logs (not recommended for MCP)

        Returns:
            Dict with logs or error
        """
        if name not in SERVICE_DEFINITIONS:
            return {
                "success": False,
                "error": f"Unknown service: {name}",
            }

        service_info = SERVICE_DEFINITIONS[name]
        compose_service = service_info["compose_service"]
        profile = service_info["profile"]

        try:
            args = []
            if profile:
                args.extend(["--profile", profile])
            args.extend(["logs", "--tail", str(lines)])
            if not follow:
                args.append("--no-follow")
            args.append(compose_service)

            result = self._run_compose(args, timeout=30, check=False)

            return {
                "success": True,
                "logs": result.stdout + result.stderr,
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def get_full_status(self) -> dict[str, Any]:
        """Get comprehensive status of all services and GPUs.

        Returns:
            Dict with services, GPUs, and summary information
        """
        services = self.get_service_status()
        gpus = self.get_gpu_status()

        running_services = [s for s in services if s.running]
        gpu_services = [
            name for name, info in SERVICE_DEFINITIONS.items()
            if info.get("uses_gpu")
        ]

        return {
            "services": [
                {
                    "name": s.name,
                    "running": s.running,
                    "status": s.status,
                    "ports": s.ports,
                    "health": s.health,
                    "uses_gpu": SERVICE_DEFINITIONS.get(s.name, {}).get("uses_gpu", False),
                }
                for s in services
            ],
            "gpus": gpus,
            "summary": {
                "running_count": len(running_services),
                "total_services": len(SERVICE_DEFINITIONS),
                "gpu_count": len(gpus),
                "gpu_services": gpu_services,
            },
        }
