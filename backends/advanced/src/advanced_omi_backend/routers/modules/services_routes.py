"""
Services routes for managing Docker services.

Provides endpoints for starting, stopping, and monitoring Docker containers
that are part of the Chronicle infrastructure.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from advanced_omi_backend.auth import current_superuser
from advanced_omi_backend.controllers import services_controller
from advanced_omi_backend.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["services"])


@router.get("/admin/services")
async def get_services_status(
    user_controllable_only: bool = Query(True, description="Only return user-controllable services"),
    current_user: User = Depends(current_superuser)
):
    """
    Get status of all manageable Docker services. Admin only.

    Args:
        user_controllable_only: If True, only return services users can control

    Returns:
        List of services with their current status
    """
    return await services_controller.get_services_status(user_controllable_only)


@router.get("/admin/services/{service_name}")
async def get_service_detail(
    service_name: str,
    current_user: User = Depends(current_superuser)
):
    """
    Get detailed information about a specific service. Admin only.

    Args:
        service_name: Name of the service

    Returns:
        Detailed service information
    """
    return await services_controller.get_service_detail(service_name)


@router.post("/admin/services/{service_name}/start")
async def start_service(
    service_name: str,
    current_user: User = Depends(current_superuser)
):
    """
    Start a Docker service. Admin only.

    Args:
        service_name: Name of the service to start

    Returns:
        Operation result
    """
    return await services_controller.start_service(service_name)


@router.post("/admin/services/{service_name}/stop")
async def stop_service(
    service_name: str,
    current_user: User = Depends(current_superuser)
):
    """
    Stop a Docker service. Admin only.

    Args:
        service_name: Name of the service to stop

    Returns:
        Operation result
    """
    return await services_controller.stop_service(service_name)


@router.post("/admin/services/{service_name}/restart")
async def restart_service(
    service_name: str,
    current_user: User = Depends(current_superuser)
):
    """
    Restart a Docker service. Admin only.

    Args:
        service_name: Name of the service to restart

    Returns:
        Operation result
    """
    return await services_controller.restart_service(service_name)


@router.get("/admin/services/{service_name}/logs")
async def get_service_logs(
    service_name: str,
    tail: int = Query(100, description="Number of log lines to retrieve"),
    current_user: User = Depends(current_superuser)
):
    """
    Get logs from a Docker service. Admin only.

    Args:
        service_name: Name of the service
        tail: Number of lines to retrieve from the end

    Returns:
        Service logs
    """
    return await services_controller.get_service_logs(service_name, tail)
