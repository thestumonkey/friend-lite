"""Docker container orchestration manager.

This module provides centralized Docker container management for controlling
local services through the Chronicle backend API.
"""

import logging
from enum import Enum
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

import docker
from docker.errors import DockerException, NotFound, APIError

logger = logging.getLogger(__name__)


class ServiceStatus(str, Enum):
    """Service status enum."""

    RUNNING = "running"
    STOPPED = "stopped"
    PAUSED = "paused"
    RESTARTING = "restarting"
    DEAD = "dead"
    CREATED = "created"
    EXITED = "exited"
    UNKNOWN = "unknown"
    NOT_FOUND = "not_found"


@dataclass
class ServiceInfo:
    """Information about a Docker service/container."""

    name: str
    container_id: Optional[str]
    status: ServiceStatus
    image: Optional[str]
    created: Optional[datetime]
    ports: Dict[str, str]
    health: Optional[str]
    error: Optional[str] = None


class DockerManager:
    """
    Manages Docker containers for local Chronicle services.

    Provides methods to start, stop, restart, and monitor Docker containers
    that are part of the Chronicle infrastructure.
    """

    # Define manageable services
    MANAGEABLE_SERVICES = {
        # Infrastructure services
        "mongo": {"description": "MongoDB database", "required": True},
        "redis": {"description": "Redis cache", "required": True},
        "qdrant": {"description": "Qdrant vector database", "required": True},

        # Optional services
        "neo4j": {"description": "Neo4j graph database", "required": False},
        "caddy": {"description": "Caddy reverse proxy", "required": False},

        # Application services (typically not user-controlled)
        "backend": {"description": "Chronicle backend API", "required": False, "user_controllable": False},
        "workers": {"description": "Background workers", "required": False, "user_controllable": False},
        "webui": {"description": "Web UI", "required": False, "user_controllable": False},
    }

    def __init__(self):
        """Initialize Docker manager."""
        self._client: Optional[docker.DockerClient] = None
        self._initialized = False
        self._docker_available = False

    def initialize(self) -> bool:
        """
        Initialize Docker client connection.

        Returns:
            True if Docker is available, False otherwise
        """
        if self._initialized:
            return self._docker_available

        try:
            self._client = docker.from_env()
            # Test connection
            self._client.ping()
            self._docker_available = True
            logger.info("Docker client initialized successfully")
        except DockerException as e:
            logger.warning(f"Docker not available: {e}")
            self._docker_available = False
        except Exception as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            self._docker_available = False
        finally:
            self._initialized = True

        return self._docker_available

    def is_available(self) -> bool:
        """Check if Docker is available."""
        if not self._initialized:
            self.initialize()
        return self._docker_available

    def get_service_info(self, service_name: str) -> ServiceInfo:
        """
        Get information about a specific service.

        Args:
            service_name: Name of the service/container

        Returns:
            ServiceInfo object with service details
        """
        if not self.is_available():
            return ServiceInfo(
                name=service_name,
                container_id=None,
                status=ServiceStatus.UNKNOWN,
                image=None,
                created=None,
                ports={},
                health=None,
                error="Docker not available"
            )

        try:
            container = self._client.containers.get(service_name)

            # Extract port mappings
            ports = {}
            if container.attrs.get("NetworkSettings", {}).get("Ports"):
                for container_port, host_bindings in container.attrs["NetworkSettings"]["Ports"].items():
                    if host_bindings:
                        for binding in host_bindings:
                            host_port = binding.get("HostPort")
                            if host_port:
                                ports[container_port] = host_port

            # Get health status if available
            health = None
            if container.attrs.get("State", {}).get("Health"):
                health = container.attrs["State"]["Health"].get("Status")

            return ServiceInfo(
                name=service_name,
                container_id=container.id[:12],
                status=ServiceStatus(container.status.lower()) if container.status.lower() in [s.value for s in ServiceStatus] else ServiceStatus.UNKNOWN,
                image=container.image.tags[0] if container.image.tags else container.image.short_id,
                created=datetime.fromisoformat(container.attrs["Created"].replace("Z", "+00:00")),
                ports=ports,
                health=health
            )

        except NotFound:
            return ServiceInfo(
                name=service_name,
                container_id=None,
                status=ServiceStatus.NOT_FOUND,
                image=None,
                created=None,
                ports={},
                health=None
            )
        except Exception as e:
            logger.error(f"Error getting service info for {service_name}: {e}")
            return ServiceInfo(
                name=service_name,
                container_id=None,
                status=ServiceStatus.UNKNOWN,
                image=None,
                created=None,
                ports={},
                health=None,
                error=str(e)
            )

    def list_services(self, user_controllable_only: bool = True) -> List[ServiceInfo]:
        """
        List all manageable services and their status.

        Args:
            user_controllable_only: If True, only return services users can control

        Returns:
            List of ServiceInfo objects
        """
        services = []
        for service_name, config in self.MANAGEABLE_SERVICES.items():
            # Filter by user controllable flag
            if user_controllable_only and not config.get("user_controllable", True):
                continue

            service_info = self.get_service_info(service_name)
            services.append(service_info)

        return services

    def start_service(self, service_name: str) -> tuple[bool, str]:
        """
        Start a Docker service.

        Args:
            service_name: Name of the service to start

        Returns:
            Tuple of (success: bool, message: str)
        """
        if not self.is_available():
            return False, "Docker not available"

        if service_name not in self.MANAGEABLE_SERVICES:
            return False, f"Service '{service_name}' is not a manageable service"

        # Check if service is user controllable
        if not self.MANAGEABLE_SERVICES[service_name].get("user_controllable", True):
            return False, f"Service '{service_name}' cannot be controlled by users"

        try:
            container = self._client.containers.get(service_name)

            if container.status == "running":
                return True, f"Service '{service_name}' is already running"

            container.start()
            logger.info(f"Started service: {service_name}")
            return True, f"Service '{service_name}' started successfully"

        except NotFound:
            return False, f"Service '{service_name}' container not found"
        except APIError as e:
            logger.error(f"Docker API error starting {service_name}: {e}")
            return False, f"Failed to start service: {str(e)}"
        except Exception as e:
            logger.error(f"Error starting {service_name}: {e}")
            return False, f"Error starting service: {str(e)}"

    def stop_service(self, service_name: str, timeout: int = 10) -> tuple[bool, str]:
        """
        Stop a Docker service.

        Args:
            service_name: Name of the service to stop
            timeout: Seconds to wait before killing the container

        Returns:
            Tuple of (success: bool, message: str)
        """
        if not self.is_available():
            return False, "Docker not available"

        if service_name not in self.MANAGEABLE_SERVICES:
            return False, f"Service '{service_name}' is not a manageable service"

        # Check if service is user controllable
        if not self.MANAGEABLE_SERVICES[service_name].get("user_controllable", True):
            return False, f"Service '{service_name}' cannot be controlled by users"

        # Prevent stopping required services
        if self.MANAGEABLE_SERVICES[service_name].get("required", False):
            return False, f"Service '{service_name}' is required and cannot be stopped"

        try:
            container = self._client.containers.get(service_name)

            if container.status != "running":
                return True, f"Service '{service_name}' is not running"

            container.stop(timeout=timeout)
            logger.info(f"Stopped service: {service_name}")
            return True, f"Service '{service_name}' stopped successfully"

        except NotFound:
            return False, f"Service '{service_name}' container not found"
        except APIError as e:
            logger.error(f"Docker API error stopping {service_name}: {e}")
            return False, f"Failed to stop service: {str(e)}"
        except Exception as e:
            logger.error(f"Error stopping {service_name}: {e}")
            return False, f"Error stopping service: {str(e)}"

    def restart_service(self, service_name: str, timeout: int = 10, internal: bool = False) -> tuple[bool, str]:
        """
        Restart a Docker service.

        Args:
            service_name: Name of the service to restart
            timeout: Seconds to wait before killing the container
            internal: If True, bypass user_controllable check (for system-initiated restarts)

        Returns:
            Tuple of (success: bool, message: str)
        """
        if not self.is_available():
            return False, "Docker not available"

        if service_name not in self.MANAGEABLE_SERVICES:
            return False, f"Service '{service_name}' is not a manageable service"

        # Check if service is user controllable (unless internal restart)
        if not internal and not self.MANAGEABLE_SERVICES[service_name].get("user_controllable", True):
            return False, f"Service '{service_name}' cannot be controlled by users"

        try:
            # Try to find container by exact name first
            try:
                container = self._client.containers.get(service_name)
            except NotFound:
                # If not found, search by docker-compose service label
                containers = self._client.containers.list(
                    filters={"label": f"com.docker.compose.service={service_name}"}
                )
                if not containers:
                    return False, f"Service '{service_name}' container not found"
                container = containers[0]  # Use first matching container

            container.restart(timeout=timeout)
            logger.info(f"Restarted service: {service_name} (container: {container.name})")
            return True, f"Service '{service_name}' restarted successfully"

        except NotFound:
            return False, f"Service '{service_name}' container not found"
        except APIError as e:
            logger.error(f"Docker API error restarting {service_name}: {e}")
            return False, f"Failed to restart service: {str(e)}"
        except Exception as e:
            logger.error(f"Error restarting {service_name}: {e}")
            return False, f"Error restarting service: {str(e)}"

    def get_service_logs(self, service_name: str, tail: int = 100) -> tuple[bool, str]:
        """
        Get logs from a Docker service.

        Args:
            service_name: Name of the service
            tail: Number of lines to retrieve from the end

        Returns:
            Tuple of (success: bool, logs: str)
        """
        if not self.is_available():
            return False, "Docker not available"

        if service_name not in self.MANAGEABLE_SERVICES:
            return False, f"Service '{service_name}' is not a manageable service"

        try:
            container = self._client.containers.get(service_name)
            logs = container.logs(tail=tail, timestamps=True).decode("utf-8")
            return True, logs

        except NotFound:
            return False, f"Service '{service_name}' container not found"
        except Exception as e:
            logger.error(f"Error getting logs for {service_name}: {e}")
            return False, f"Error getting logs: {str(e)}"


# Global instance
_docker_manager: Optional[DockerManager] = None


def get_docker_manager() -> DockerManager:
    """Get the global DockerManager instance."""
    global _docker_manager
    if _docker_manager is None:
        _docker_manager = DockerManager()
        _docker_manager.initialize()
    return _docker_manager
