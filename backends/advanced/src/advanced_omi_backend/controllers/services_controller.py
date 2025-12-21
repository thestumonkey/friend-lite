"""
Services controller for handling Docker service orchestration business logic.
"""

import logging
from typing import List, Dict, Optional

from fastapi.responses import JSONResponse

from advanced_omi_backend.docker_manager import get_docker_manager, ServiceInfo

logger = logging.getLogger(__name__)


async def get_services_status(user_controllable_only: bool = True) -> JSONResponse:
    """
    Get status of all manageable Docker services.

    Args:
        user_controllable_only: If True, only return user-controllable services

    Returns:
        JSONResponse with services list and overall status
    """
    try:
        docker_manager = get_docker_manager()

        if not docker_manager.is_available():
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Docker not available",
                    "message": "Docker daemon is not running or not accessible",
                    "docker_available": False
                }
            )

        services = docker_manager.list_services(user_controllable_only=user_controllable_only)

        # Convert ServiceInfo objects to dicts
        services_data = []
        for service in services:
            services_data.append({
                "name": service.name,
                "container_id": service.container_id,
                "status": service.status.value,
                "image": service.image,
                "created": service.created.isoformat() if service.created else None,
                "ports": service.ports,
                "health": service.health,
                "error": service.error,
                "description": docker_manager.MANAGEABLE_SERVICES[service.name].get("description", ""),
                "required": docker_manager.MANAGEABLE_SERVICES[service.name].get("required", False),
                "user_controllable": docker_manager.MANAGEABLE_SERVICES[service.name].get("user_controllable", True)
            })

        return JSONResponse(
            content={
                "services": services_data,
                "docker_available": True,
                "status": "success"
            }
        )

    except Exception as e:
        logger.error(f"Error getting services status: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to get services status: {str(e)}"}
        )


async def get_service_detail(service_name: str) -> JSONResponse:
    """
    Get detailed information about a specific service.

    Args:
        service_name: Name of the service

    Returns:
        JSONResponse with service details
    """
    try:
        docker_manager = get_docker_manager()

        if not docker_manager.is_available():
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Docker not available",
                    "message": "Docker daemon is not running or not accessible"
                }
            )

        service_info = docker_manager.get_service_info(service_name)

        return JSONResponse(
            content={
                "service": {
                    "name": service_info.name,
                    "container_id": service_info.container_id,
                    "status": service_info.status.value,
                    "image": service_info.image,
                    "created": service_info.created.isoformat() if service_info.created else None,
                    "ports": service_info.ports,
                    "health": service_info.health,
                    "error": service_info.error,
                    "description": docker_manager.MANAGEABLE_SERVICES.get(service_name, {}).get("description", ""),
                    "required": docker_manager.MANAGEABLE_SERVICES.get(service_name, {}).get("required", False),
                    "user_controllable": docker_manager.MANAGEABLE_SERVICES.get(service_name, {}).get("user_controllable", True)
                },
                "status": "success"
            }
        )

    except Exception as e:
        logger.error(f"Error getting service detail for {service_name}: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to get service detail: {str(e)}"}
        )


async def start_service(service_name: str) -> JSONResponse:
    """
    Start a Docker service.

    Args:
        service_name: Name of the service to start

    Returns:
        JSONResponse with operation result
    """
    try:
        docker_manager = get_docker_manager()

        if not docker_manager.is_available():
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Docker not available",
                    "message": "Docker daemon is not running or not accessible"
                }
            )

        success, message = docker_manager.start_service(service_name)

        if success:
            logger.info(f"Service {service_name} started successfully")
            return JSONResponse(
                content={
                    "message": message,
                    "service": service_name,
                    "status": "success"
                }
            )
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "error": message,
                    "service": service_name,
                    "status": "failed"
                }
            )

    except Exception as e:
        logger.error(f"Error starting service {service_name}: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to start service: {str(e)}"}
        )


async def stop_service(service_name: str) -> JSONResponse:
    """
    Stop a Docker service.

    Args:
        service_name: Name of the service to stop

    Returns:
        JSONResponse with operation result
    """
    try:
        docker_manager = get_docker_manager()

        if not docker_manager.is_available():
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Docker not available",
                    "message": "Docker daemon is not running or not accessible"
                }
            )

        success, message = docker_manager.stop_service(service_name)

        if success:
            logger.info(f"Service {service_name} stopped successfully")
            return JSONResponse(
                content={
                    "message": message,
                    "service": service_name,
                    "status": "success"
                }
            )
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "error": message,
                    "service": service_name,
                    "status": "failed"
                }
            )

    except Exception as e:
        logger.error(f"Error stopping service {service_name}: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to stop service: {str(e)}"}
        )


async def restart_service(service_name: str) -> JSONResponse:
    """
    Restart a Docker service.

    Args:
        service_name: Name of the service to restart

    Returns:
        JSONResponse with operation result
    """
    try:
        docker_manager = get_docker_manager()

        if not docker_manager.is_available():
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Docker not available",
                    "message": "Docker daemon is not running or not accessible"
                }
            )

        success, message = docker_manager.restart_service(service_name)

        if success:
            logger.info(f"Service {service_name} restarted successfully")
            return JSONResponse(
                content={
                    "message": message,
                    "service": service_name,
                    "status": "success"
                }
            )
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "error": message,
                    "service": service_name,
                    "status": "failed"
                }
            )

    except Exception as e:
        logger.error(f"Error restarting service {service_name}: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to restart service: {str(e)}"}
        )


async def get_service_logs(service_name: str, tail: int = 100) -> JSONResponse:
    """
    Get logs from a Docker service.

    Args:
        service_name: Name of the service
        tail: Number of lines to retrieve

    Returns:
        JSONResponse with service logs
    """
    try:
        docker_manager = get_docker_manager()

        if not docker_manager.is_available():
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Docker not available",
                    "message": "Docker daemon is not running or not accessible"
                }
            )

        success, logs = docker_manager.get_service_logs(service_name, tail=tail)

        if success:
            return JSONResponse(
                content={
                    "logs": logs,
                    "service": service_name,
                    "status": "success"
                }
            )
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "error": logs,
                    "service": service_name,
                    "status": "failed"
                }
            )

    except Exception as e:
        logger.error(f"Error getting logs for service {service_name}: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to get service logs: {str(e)}"}
        )
