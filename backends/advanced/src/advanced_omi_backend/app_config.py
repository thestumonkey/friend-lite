"""
Application configuration for Chronicle backend.

Centralizes all application-level configuration including database connections,
service configurations, and environment variables that were previously in main.py.
"""

import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

from advanced_omi_backend.constants import OMI_CHANNELS, OMI_SAMPLE_RATE, OMI_SAMPLE_WIDTH
from advanced_omi_backend.services.transcription import get_transcription_provider
from advanced_omi_backend.settings_models import (
    AllSettings,
    ApiKeysSettings,
    AudioProcessingSettings,
    ConversationSettings,
    DiarizationSettings,
    InfrastructureSettings,
    LLMSettings,
    MiscSettings,
    NetworkSettings,
    ProviderSettings,
    SpeechDetectionSettings,
)

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class AppConfig:
    """Centralized application configuration."""

    def __init__(self):
        # MongoDB Configuration
        self.mongodb_uri = os.getenv("MONGODB_URI", "mongodb://mongo:27017")
        # default to legacy value to avoid breaking peoples .env
        self.mongodb_database = os.getenv("MONGODB_DATABASE", "friend-lite")
        self.mongo_client = AsyncIOMotorClient(self.mongodb_uri)
        self.db = self.mongo_client.get_default_database(self.mongodb_database)
        self.users_col = self.db["users"]
        self.speakers_col = self.db["speakers"]

        # Audio Configuration
        self.segment_seconds = 60  # length of each stored chunk
        self.target_samples = OMI_SAMPLE_RATE * self.segment_seconds
        self.audio_chunk_dir = Path("./audio_chunks")
        self.audio_chunk_dir.mkdir(parents=True, exist_ok=True)

        # Conversation timeout configuration
        self.new_conversation_timeout_minutes = float(
            os.getenv("NEW_CONVERSATION_TIMEOUT_MINUTES", "1.5")
        )

        # Audio cropping configuration
        self.audio_cropping_enabled = os.getenv("AUDIO_CROPPING_ENABLED", "true").lower() == "true"
        self.min_speech_segment_duration = float(os.getenv("MIN_SPEECH_SEGMENT_DURATION", "1.0"))
        self.cropping_context_padding = float(os.getenv("CROPPING_CONTEXT_PADDING", "0.1"))

        # Transcription Configuration (graceful degradation is always enabled)
        self.transcription_provider_name = self._load_provider_setting("transcription")

        # API keys are lazy-loaded via properties (see @property methods below)
        self._deepgram_api_key = None
        self._mistral_api_key = None
        self._deepgram_api_key_loaded = False
        self._mistral_api_key_loaded = False

        # Transcription provider is lazy-loaded (see @property method below)
        self._transcription_provider = None
        self._transcription_provider_loaded = False

        # External Services Configuration
        self.qdrant_base_url = os.getenv("QDRANT_BASE_URL", "qdrant")
        self.qdrant_port = os.getenv("QDRANT_PORT", "6333")
        self.memory_provider = self._load_provider_setting("memory")
        # Map legacy provider names to current names
        if self.memory_provider in ("friend-lite", "friend_lite"):
            logger.debug(f"Mapping legacy provider '{self.memory_provider}' to 'chronicle'")
            self.memory_provider = "chronicle"

        # Redis Configuration
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

        # CORS Configuration
        default_origins = "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,http://127.0.0.1:3002"
        self.cors_origins = os.getenv("CORS_ORIGINS", default_origins)
        self.allowed_origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

        # Tailscale support
        self.tailscale_regex = r"http://100\.\d{1,3}\.\d{1,3}\.\d{1,3}:3000"

        # Thread pool configuration
        self.max_workers = os.cpu_count() or 4

        # LLM Configuration (graceful degradation is always enabled)
        self.llm_provider = os.getenv("LLM_PROVIDER", "openai")

        # API key is lazy-loaded via property (see @property method below)
        self._openai_api_key = None
        self._openai_api_key_loaded = False

        # LLM enabled status is lazy-loaded (see @property method below)
        self._llm_enabled = None
        self._llm_enabled_loaded = False

        # Memory service configuration
        self.memory_service_supports_threshold = self.memory_provider == "chronicle"

        # Settings cache - loaded from YAML and kept in memory
        self._config_cache = None
        self._config_loaded = False

    @property
    def deepgram_api_key(self) -> Optional[str]:
        """Lazy-load Deepgram API key from config/secrets.yaml or environment."""
        if not self._deepgram_api_key_loaded:
            self._deepgram_api_key = self._get_api_key("deepgram")
            self._deepgram_api_key_loaded = True
        return self._deepgram_api_key

    @property
    def mistral_api_key(self) -> Optional[str]:
        """Lazy-load Mistral API key from config/secrets.yaml or environment."""
        if not self._mistral_api_key_loaded:
            self._mistral_api_key = self._get_api_key("mistral")
            self._mistral_api_key_loaded = True
        return self._mistral_api_key

    @property
    def openai_api_key(self) -> Optional[str]:
        """Lazy-load OpenAI API key from config/secrets.yaml or environment."""
        if not self._openai_api_key_loaded:
            self._openai_api_key = self._get_api_key("openai")
            self._openai_api_key_loaded = True
        return self._openai_api_key

    @property
    def transcription_provider(self):
        """Lazy-load transcription provider (graceful degradation is default)."""
        if not self._transcription_provider_loaded:
            self._transcription_provider = get_transcription_provider(
                self.transcription_provider_name
            )
            if self._transcription_provider:
                logger.info(
                    f"✅ Using {self._transcription_provider.name} transcription provider ({self._transcription_provider.mode})"
                )
            else:
                logger.warning("⚠️  Transcription disabled - No API key configured")
                logger.warning("   Add API keys via wizard: http://localhost:3000/wizard")
            self._transcription_provider_loaded = True
        return self._transcription_provider

    @property
    def transcription_enabled(self) -> bool:
        """Check if transcription is enabled based on provider availability."""
        return self.transcription_provider is not None

    @property
    def llm_enabled(self) -> bool:
        """Check if LLM is enabled based on API key availability."""
        if not self._llm_enabled_loaded:
            if not self.openai_api_key:
                if self.llm_required and not self.allow_missing_api_keys:
                    logger.error("❌ LLM provider required but OPENAI_API_KEY not configured")
                else:
                    logger.warning("⚠️  LLM disabled - Memory extraction and chat features unavailable")
                    if self.allow_missing_api_keys:
                        logger.warning("   Add OpenAI API key to enable LLM features")
                        logger.warning("   Configure at: http://localhost:4000/system")
                self._llm_enabled = False
            else:
                self._llm_enabled = True
                logger.info(f"✅ LLM enabled (provider: {self.llm_provider})")
            self._llm_enabled_loaded = True
        return self._llm_enabled

    def reload_config(self):
        """Invalidate all cached configuration values.

        This method resets all lazy-loaded caches so they'll be reloaded from
        config files on next access. Call this after any config file update.

        This is automatically called by ConfigParser.save() so you typically
        don't need to call it manually.
        """
        # Reset all API key caches
        self._deepgram_api_key_loaded = False
        self._mistral_api_key_loaded = False
        self._openai_api_key_loaded = False
        self._deepgram_api_key = None
        self._mistral_api_key = None
        self._openai_api_key = None

        # Reset provider caches
        self._transcription_provider_loaded = False
        self._transcription_provider = None
        self._llm_enabled_loaded = False
        self._llm_enabled = None

        # Reset settings cache
        self._config_loaded = False
        self._config_cache = None

        # Reload provider settings from config (not lazy-loaded)
        self.transcription_provider_name = self._load_provider_setting("transcription")
        self.memory_provider = self._load_provider_setting("memory")

        logger.info("🔄 All config caches invalidated - will reload from config on next access")

    def invalidate_cache(self, category: str = None):
        """Legacy method for cache invalidation (for backward compatibility).

        Simply calls reload_config() regardless of category since we reload everything.
        """
        self.reload_config()

    async def _load_config_from_yaml(self):
        """Load configuration from YAML files into memory cache."""
        if not self._config_loaded:
            from advanced_omi_backend.config import get_config_parser, init_config_parser
            import asyncio

            try:
                config_parser = get_config_parser()
            except RuntimeError:
                config_parser = init_config_parser("config/config.yaml")

            self._config_cache = await config_parser.load()
            self._config_loaded = True
            logger.info("📄 Configuration loaded from YAML files into memory")

    async def get_config(self):
        """Get the full cached configuration."""
        if not self._config_loaded:
            await self._load_config_from_yaml()
        return self._config_cache

    # Settings Manager Interface (for compatibility with settings_routes.py)

    async def get_all_settings(self) -> AllSettings:
        """Get all settings combined."""
        config = await self.get_config()
        return AllSettings(
            speech_detection=config.speech_detection,
            conversation=config.conversation,
            audio_processing=config.audio_processing,
            diarization=config.diarization,
            llm=config.llm,
            providers=config.providers,
            network=config.network,
            infrastructure=config.infrastructure,
            misc=config.misc,
            api_keys=config.api_keys,
        )

    async def update_all_settings(self, settings: AllSettings, updated_by: str = "user"):
        """Update all settings at once."""
        from advanced_omi_backend.config import get_config_parser

        config_parser = get_config_parser()
        config = await config_parser.load()

        # Update all sections
        config.speech_detection = settings.speech_detection
        config.conversation = settings.conversation
        config.audio_processing = settings.audio_processing
        config.diarization = settings.diarization
        config.llm = settings.llm
        config.providers = settings.providers
        config.network = settings.network
        config.infrastructure = settings.infrastructure
        config.misc = settings.misc
        config.api_keys = settings.api_keys

        # Save (this automatically calls reload_config())
        await config_parser.save(config)

    async def get_speech_detection(self) -> SpeechDetectionSettings:
        """Get speech detection settings."""
        config = await self.get_config()
        return config.speech_detection

    async def update_speech_detection(self, settings: SpeechDetectionSettings, updated_by: str = "user"):
        """Update speech detection settings."""
        from advanced_omi_backend.config import get_config_parser
        config_parser = get_config_parser()
        config = await config_parser.load()
        config.speech_detection = settings
        await config_parser.save(config)

    async def get_conversation(self) -> ConversationSettings:
        """Get conversation settings."""
        config = await self.get_config()
        return config.conversation

    async def update_conversation(self, settings: ConversationSettings, updated_by: str = "user"):
        """Update conversation settings."""
        from advanced_omi_backend.config import get_config_parser
        config_parser = get_config_parser()
        config = await config_parser.load()
        config.conversation = settings
        await config_parser.save(config)

    async def get_audio_processing(self) -> AudioProcessingSettings:
        """Get audio processing settings."""
        config = await self.get_config()
        return config.audio_processing

    async def update_audio_processing(self, settings: AudioProcessingSettings, updated_by: str = "user"):
        """Update audio processing settings."""
        from advanced_omi_backend.config import get_config_parser
        config_parser = get_config_parser()
        config = await config_parser.load()
        config.audio_processing = settings
        await config_parser.save(config)

    async def get_diarization(self) -> DiarizationSettings:
        """Get diarization settings."""
        config = await self.get_config()
        return config.diarization

    async def update_diarization(self, settings: DiarizationSettings, updated_by: str = "user"):
        """Update diarization settings."""
        from advanced_omi_backend.config import get_config_parser
        config_parser = get_config_parser()
        config = await config_parser.load()
        config.diarization = settings
        await config_parser.save(config)

    async def get_llm(self) -> LLMSettings:
        """Get LLM settings."""
        config = await self.get_config()
        return config.llm

    async def update_llm(self, settings: LLMSettings, updated_by: str = "user"):
        """Update LLM settings."""
        from advanced_omi_backend.config import get_config_parser
        config_parser = get_config_parser()
        config = await config_parser.load()
        config.llm = settings
        await config_parser.save(config)

    async def get_providers(self) -> ProviderSettings:
        """Get provider settings."""
        config = await self.get_config()
        return config.providers

    async def update_providers(self, settings: ProviderSettings, updated_by: str = "user"):
        """Update provider settings."""
        from advanced_omi_backend.config import get_config_parser
        config_parser = get_config_parser()
        config = await config_parser.load()
        config.providers = settings
        await config_parser.save(config)

    async def get_network(self) -> NetworkSettings:
        """Get network settings."""
        config = await self.get_config()
        return config.network

    async def update_network(self, settings: NetworkSettings, updated_by: str = "user"):
        """Update network settings."""
        from advanced_omi_backend.config import get_config_parser
        config_parser = get_config_parser()
        config = await config_parser.load()
        config.network = settings
        await config_parser.save(config)

    async def get_infrastructure(self) -> InfrastructureSettings:
        """Get infrastructure settings."""
        config = await self.get_config()
        return config.infrastructure

    async def update_infrastructure(self, settings: InfrastructureSettings, updated_by: str = "user"):
        """Update infrastructure settings."""
        from advanced_omi_backend.config import get_config_parser
        config_parser = get_config_parser()
        config = await config_parser.load()
        config.infrastructure = settings
        await config_parser.save(config)

    async def get_misc(self) -> MiscSettings:
        """Get miscellaneous settings."""
        config = await self.get_config()
        return config.misc

    async def update_misc(self, settings: MiscSettings, updated_by: str = "user"):
        """Update miscellaneous settings."""
        from advanced_omi_backend.config import get_config_parser
        config_parser = get_config_parser()
        config = await config_parser.load()
        config.misc = settings
        await config_parser.save(config)

    async def get_api_keys(self) -> ApiKeysSettings:
        """Get API keys settings."""
        config = await self.get_config()
        return config.api_keys

    async def update_api_keys(self, settings: ApiKeysSettings, updated_by: str = "user"):
        """Update API keys settings."""
        from advanced_omi_backend.config import get_config_parser
        config_parser = get_config_parser()
        config = await config_parser.load()
        config.api_keys = settings
        await config_parser.save(config)

    def _get_api_key(self, provider: str) -> Optional[str]:
        """
        Get API key from config/secrets.yaml (config-first) or environment variable (fallback).

        Args:
            provider: The provider name ("openai", "deepgram", "mistral")

        Returns:
            API key string or None if not found
        """
        # Try environment variable first (for backward compatibility)
        env_key_map = {
            "openai": "OPENAI_API_KEY",
            "deepgram": "DEEPGRAM_API_KEY",
            "mistral": "MISTRAL_API_KEY"
        }

        env_key = os.getenv(env_key_map.get(provider, f"{provider.upper()}_API_KEY"))
        if env_key:
            logger.info(f"🔑 Loaded {provider} API key from environment variable")
            return env_key

        # Load from config/secrets.yaml
        try:
            logger.info(f"🔍 Attempting to load {provider} API key from config/secrets.yaml")
            from advanced_omi_backend.config import get_config_parser, init_config_parser
            import asyncio

            # Initialize config parser if not already initialized
            try:
                config_parser = get_config_parser()
                logger.info(f"   Using existing ConfigParser instance")
            except RuntimeError:
                logger.info(f"   Initializing new ConfigParser instance")
                config_parser = init_config_parser("config/config.yaml")

            # Load config synchronously - check if we're in an event loop
            try:
                loop = asyncio.get_running_loop()
                # We're in an event loop - load synchronously using thread pool
                logger.info(f"   Loading config from running event loop")
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    config = executor.submit(lambda: asyncio.run(config_parser.load())).result()
            except RuntimeError:
                # No event loop running - safe to use asyncio.run()
                logger.info(f"   Loading config with asyncio.run()")
                config = asyncio.run(config_parser.load())

            # Map provider name to config attribute
            api_key_map = {
                "openai": config.api_keys.openai_api_key,
                "deepgram": config.api_keys.deepgram_api_key,
                "mistral": config.api_keys.mistral_api_key
            }

            api_key = api_key_map.get(provider)
            if api_key:
                logger.info(f"✅ Successfully loaded {provider} API key from config/secrets.yaml")
                return api_key
            else:
                logger.info(f"⚠️  No {provider} API key found in config/secrets.yaml")
                return None

        except Exception as e:
            logger.warning(f"❌ Could not load {provider} API key from config: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return None

    def _load_provider_setting(self, provider_type: str) -> Optional[str]:
        """
        Load provider setting from config/config.yaml (config-first, NO environment variable fallback).

        Args:
            provider_type: The provider type ("transcription", "memory")

        Returns:
            Provider name string or None if not found
        """
        # Load from config/config.yaml (NO environment variable fallback)
        try:
            logger.info(f"🔍 Attempting to load {provider_type}_provider from config/config.yaml")
            from advanced_omi_backend.config import get_config_parser, init_config_parser
            import asyncio

            # Initialize config parser if not already initialized
            try:
                config_parser = get_config_parser()
                logger.info(f"   Using existing ConfigParser instance")
            except RuntimeError:
                logger.info(f"   Initializing new ConfigParser instance")
                config_parser = init_config_parser("config/config.yaml")

            # Load config synchronously - check if we're in an event loop
            try:
                loop = asyncio.get_running_loop()
                # We're in an event loop - load synchronously using thread pool
                logger.info(f"   Loading config from running event loop")
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    config = executor.submit(lambda: asyncio.run(config_parser.load())).result()
            except RuntimeError:
                # No event loop running - safe to use asyncio.run()
                logger.info(f"   Loading config with asyncio.run()")
                config = asyncio.run(config_parser.load())

            # Get provider from config
            provider_value = None
            if provider_type == "transcription":
                provider_value = config.providers.transcription_provider
            elif provider_type == "memory":
                provider_value = config.providers.memory_provider

            if provider_value:
                # Handle "auto" provider - convert to None so auto-detection works
                if provider_value == "auto":
                    logger.info(f"✅ {provider_type}_provider set to 'auto' - will auto-detect based on available API keys")
                    return None
                logger.info(f"✅ Successfully loaded {provider_type}_provider from config/config.yaml: {provider_value}")
                return provider_value
            else:
                logger.info(f"⚠️  No {provider_type}_provider found in config/config.yaml")
                # Default values
                if provider_type == "memory":
                    return "chronicle"
                return None

        except Exception as e:
            logger.warning(f"❌ Could not load {provider_type}_provider from config: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            # Default values
            if provider_type == "memory":
                return "chronicle"
            return None


# Global configuration instance
app_config = AppConfig()


def get_app_config() -> AppConfig:
    """Get the global application configuration instance."""
    return app_config


def get_audio_chunk_dir() -> Path:
    """Get the audio chunk directory."""
    return app_config.audio_chunk_dir


def get_mongo_collections():
    """Get MongoDB collections."""
    return {
        'users': app_config.users_col,
        'speakers': app_config.speakers_col,
    }


def get_redis_config():
    """Get Redis configuration."""
    return {
        'url': app_config.redis_url,
        'encoding': "utf-8",
        'decode_responses': False
    }