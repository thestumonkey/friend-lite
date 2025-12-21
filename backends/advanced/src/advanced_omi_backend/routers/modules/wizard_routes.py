"""
Setup wizard routes for initial Chronicle configuration.

Provides a guided setup experience for first-time users.
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from advanced_omi_backend.auth import current_active_user, current_superuser
from advanced_omi_backend.config import get_config_parser
from advanced_omi_backend.users import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wizard", tags=["wizard"])


# Shared helpers

def mask_key(key: str | None) -> str | None:
    """Mask API key for display (show only last 4 characters)."""
    if not key:
        return None
    return "***" + key[-4:] if len(key) > 4 else "***"


async def restart_workers_if_needed():
    """Restart workers container to pick up new configuration."""
    try:
        from advanced_omi_backend.docker_manager import get_docker_manager
        docker_manager = get_docker_manager()
        success, message = docker_manager.restart_service("workers", internal=True)
        if success:
            logger.info(f"✅ Workers container restarted to load new configuration")
        else:
            logger.warning(f"⚠️ Could not restart workers: {message}")
    except Exception as e:
        logger.warning(f"⚠️ Could not restart workers container: {e}")


# Models

class WizardStatusResponse(BaseModel):
    """Wizard completion status."""
    wizard_completed: bool = Field(..., description="Whether wizard has been completed")
    current_step: str = Field(default="api_keys", description="Current wizard step")


class ApiKeysStep(BaseModel):
    """API Keys configuration step (core keys only)."""
    openai_api_key: str | None = None
    deepgram_api_key: str | None = None
    mistral_api_key: str | None = None


# Endpoints

@router.get("/status", response_model=WizardStatusResponse)
async def get_wizard_status(
    current_user: User = Depends(current_active_user),
):
    """
    Get current wizard completion status.

    Wizard is complete when basic API keys are configured.
    """
    try:
        config_parser = get_config_parser()
        config = await config_parser.load()

        # Wizard is complete if LLM and transcription are configured
        has_llm = bool(config.api_keys.openai_api_key)
        has_transcription = bool(config.api_keys.deepgram_api_key or config.api_keys.mistral_api_key)
        wizard_completed = has_llm and has_transcription

        current_step = "complete" if wizard_completed else "api_keys"

        return WizardStatusResponse(
            wizard_completed=wizard_completed,
            current_step=current_step
        )
    except Exception as e:
        logger.error(f"Error getting wizard status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get wizard status: {str(e)}")


@router.get("/api-keys", response_model=ApiKeysStep)
async def get_wizard_api_keys(
    current_user: User = Depends(current_active_user),
):
    """
    Get current API keys configuration.

    Returns masked values to show which keys are configured.
    """
    try:
        config_parser = get_config_parser()
        config = await config_parser.load()

        return ApiKeysStep(
            openai_api_key=mask_key(config.api_keys.openai_api_key),
            deepgram_api_key=mask_key(config.api_keys.deepgram_api_key),
            mistral_api_key=mask_key(config.api_keys.mistral_api_key),
        )
    except Exception as e:
        logger.error(f"Error getting wizard API keys: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get API keys: {str(e)}")


@router.put("/api-keys", response_model=ApiKeysStep)
async def update_wizard_api_keys(
    api_keys: ApiKeysStep,
    current_user: User = Depends(current_superuser),
):
    """
    Update API keys configuration.

    Admin only. Only updates keys that are provided (non-None values).
    """
    try:
        config_parser = get_config_parser()
        config = await config_parser.load()

        # Update only provided keys
        key_mapping = {
            'openai_api_key': api_keys.openai_api_key,
            'deepgram_api_key': api_keys.deepgram_api_key,
            'mistral_api_key': api_keys.mistral_api_key,
        }

        updated_count = 0
        for key, value in key_mapping.items():
            if value is not None:
                setattr(config.api_keys, key, value)
                updated_count += 1

        if updated_count > 0:
            # Save configuration (automatically invalidates app_config cache)
            await config_parser.save(config)
            logger.info(f"Wizard: {updated_count} API keys updated by {current_user.email}")

            # Restart workers to pick up new API keys
            await restart_workers_if_needed()

        # Return masked values
        return ApiKeysStep(
            openai_api_key=mask_key(config.api_keys.openai_api_key),
            deepgram_api_key=mask_key(config.api_keys.deepgram_api_key),
            mistral_api_key=mask_key(config.api_keys.mistral_api_key),
        )
    except Exception as e:
        logger.error(f"Error updating wizard API keys: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update API keys: {str(e)}")
