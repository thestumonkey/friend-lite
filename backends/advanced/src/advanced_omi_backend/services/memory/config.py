"""Memory service configuration utilities."""

import logging
import os
import yaml
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Union

from advanced_omi_backend.model_registry import get_models_registry
from advanced_omi_backend.utils.config_utils import resolve_value

memory_logger = logging.getLogger("memory_service")


def _is_langfuse_enabled() -> bool:
    """Check if Langfuse is properly configured."""
    return bool(
        os.getenv("LANGFUSE_PUBLIC_KEY")
        and os.getenv("LANGFUSE_SECRET_KEY")
        and os.getenv("LANGFUSE_HOST")
    )


class LLMProvider(Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    OLLAMA = "ollama"
    CUSTOM = "custom"


class VectorStoreProvider(Enum):
    """Supported vector store providers."""

    QDRANT = "qdrant"
    WEAVIATE = "weaviate"
    CUSTOM = "custom"


class MemoryProvider(Enum):
    """Supported memory service providers."""

    CHRONICLE = "chronicle"  # Default sophisticated implementation
    OPENMEMORY_MCP = "openmemory_mcp"  # OpenMemory MCP backend
    MYCELIA = "mycelia"  # Mycelia memory backend


@dataclass
class MemoryConfig:
    """Configuration for memory service."""

    memory_provider: MemoryProvider = MemoryProvider.CHRONICLE
    llm_provider: LLMProvider = LLMProvider.OPENAI
    vector_store_provider: VectorStoreProvider = VectorStoreProvider.QDRANT
    llm_config: Dict[str, Any] = None
    vector_store_config: Dict[str, Any] = None
    embedder_config: Dict[str, Any] = None
    openmemory_config: Dict[str, Any] = None  # Configuration for OpenMemory MCP
    mycelia_config: Dict[str, Any] = None  # Configuration for Mycelia
    extraction_prompt: str = None
    extraction_enabled: bool = True
    timeout_seconds: int = 1200


def load_config_yml() -> Dict[str, Any]:
    """Load config.yml from standard locations."""
    # Check /app/config.yml (Docker) or root relative to file
    current_dir = Path(__file__).parent.resolve()
    # Path inside Docker: /app/config.yml (if mounted) or ../../../config.yml relative to src
    paths = [
        Path("/app/config.yml"),
        current_dir.parent.parent.parent.parent.parent / "config.yml",  # Relative to src/
        Path("./config.yml"),
    ]

    for path in paths:
        if path.exists():
            with open(path, "r") as f:
                return yaml.safe_load(f) or {}

    raise FileNotFoundError(f"config.yml not found in any of: {[str(p) for p in paths]}")


def create_openmemory_config(
    server_url: str = "http://localhost:8765",
    client_name: str = "chronicle",
    user_id: str = "default",
    timeout: int = 30,
) -> Dict[str, Any]:
    """Create OpenMemory MCP configuration."""
    return {
        "server_url": server_url,
        "client_name": client_name,
        "user_id": user_id,
        "timeout": timeout,
    }


def create_mycelia_config(
    api_url: str = "http://localhost:8080", api_key: str = None, timeout: int = 30, **kwargs
) -> Dict[str, Any]:
    """Create Mycelia configuration."""
    config = {
        "api_url": api_url,
        "timeout": timeout,
    }
    if api_key:
        config["api_key"] = api_key
    config.update(kwargs)
    return config


def build_memory_config_from_env(allow_missing_keys: bool = False) -> MemoryConfig:
    """Build memory configuration from environment variables and YAML config.

    Args:
        allow_missing_keys: If True, allow missing API keys and disable features gracefully.
                           If False, raise errors when required keys are missing.
    """
    try:
        # Determine memory provider from registry
        reg = get_models_registry()
        mem_settings = reg.memory if reg else {}
        memory_provider = (mem_settings.get("provider") or "chronicle").lower()

        # Map legacy provider names to current names
        if memory_provider in ("friend-lite", "friend_lite"):
            memory_logger.info(f"🔧 Mapping legacy provider '{memory_provider}' to 'chronicle'")
            memory_provider = "chronicle"

        if memory_provider not in [p.value for p in MemoryProvider]:
            raise ValueError(f"Unsupported memory provider: {memory_provider}")

        memory_provider_enum = MemoryProvider(memory_provider)

        # For OpenMemory MCP, configuration is much simpler
        if memory_provider_enum == MemoryProvider.OPENMEMORY_MCP:
            mcp = mem_settings.get("openmemory_mcp") or {}
            openmemory_config = create_openmemory_config(
                server_url=mcp.get("server_url", "http://localhost:8765"),
                client_name=mcp.get("client_name", "chronicle"),
                user_id=mcp.get("user_id", "default"),
                timeout=int(mcp.get("timeout", 30)),
            )

            memory_logger.info(
                f"🔧 Memory config: Provider=OpenMemory MCP, URL={openmemory_config['server_url']}"
            )

            return MemoryConfig(
                memory_provider=memory_provider_enum,
                openmemory_config=openmemory_config,
                timeout_seconds=int(mem_settings.get("timeout_seconds", 1200)),
            )

        # For Mycelia provider, build mycelia_config + llm_config (for temporal extraction)
        if memory_provider_enum == MemoryProvider.MYCELIA:
            # Registry-driven Mycelia configuration
            mys = mem_settings.get("mycelia") or {}
            api_url = mys.get("api_url", "http://localhost:5173")
            timeout = int(mys.get("timeout", 30))
            mycelia_config = create_mycelia_config(api_url=api_url, timeout=timeout)

            # Use default LLM from registry for temporal extraction
            llm_config = None
            if reg:
                llm_def = reg.get_default("llm")
                if llm_def:
                    llm_config = create_openai_config(
                        api_key=llm_def.api_key or "",
                        model=llm_def.model_name,
                        base_url=llm_def.model_url,
                    )
                    memory_logger.info(
                        f"🔧 Mycelia temporal extraction (registry): LLM={llm_def.model_name}"
                    )
            else:
                memory_logger.warning(
                    "Registry not available for Mycelia temporal extraction; disabled"
                )

            memory_logger.info(
                f"🔧 Memory config: Provider=Mycelia, URL={mycelia_config['api_url']}"
            )

            return MemoryConfig(
                memory_provider=memory_provider_enum,
                mycelia_config=mycelia_config,
                llm_config=llm_config,
                timeout_seconds=int(mem_settings.get("timeout_seconds", timeout)),
            )

        # For Chronicle provider, use registry-driven configuration

        # Registry-driven configuration only (no env-based branching)
        llm_config = None
        llm_provider_enum = None
        embedding_dims = 1536 # Default

        # Build LLM configuration
        if llm_provider == "openai":
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if not openai_api_key:
                if allow_missing_keys:
                    memory_logger.warning("OPENAI_API_KEY not set - memory extraction will be disabled")
                    llm_config = None
                    llm_provider_enum = None
                else:
                    raise ValueError("OPENAI_API_KEY required for OpenAI provider")
            else:
                # Use environment variables for model, fall back to config, then defaults
                model = os.getenv("OPENAI_MODEL") or memory_config.get("llm_settings", {}).get("model") or "gpt-4o-mini"
                embedding_model = memory_config.get("llm_settings", {}).get("embedding_model") or "text-embedding-3-small"
                base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
                memory_logger.info(f"🔧 Memory config: LLM={model}, Embedding={embedding_model}, Base URL={base_url}")

                llm_config = create_openai_config(
                    api_key=openai_api_key,
                    model=model,
                    embedding_model=embedding_model,
                    base_url=base_url,
                    temperature=memory_config.get("llm_settings", {}).get("temperature", 0.1),
                    max_tokens=memory_config.get("llm_settings", {}).get("max_tokens", 2000)
                )
                llm_provider_enum = LLMProvider.OPENAI
                embedding_dims = get_embedding_dims(llm_config)
                memory_logger.info(f"🔧 Setting Embedder dims {embedding_dims}")
        
        elif llm_provider == "ollama":
            base_url = os.getenv("OLLAMA_BASE_URL")
            if not base_url:
                raise ValueError("OLLAMA_BASE_URL required for Ollama provider")
            
            model = os.getenv("OLLAMA_MODEL")
            if not model:
                raise ValueError("OLLAMA_MODEL required for Ollama provider")
            embedding_model = os.getenv("OLLAMA_EMBEDDER_MODEL")
            if not embedding_model:
                raise ValueError("OLLAMA_EMBEDDER_MODEL required for Ollama provider")
            memory_logger.info(f"🔧 Memory config: LLM={model}, Embedding={embedding_model}, Base URL={base_url}")

            llm_config = create_ollama_config(
                base_url=base_url,
                model=model,
                embedding_model=embedding_model,
            )
            llm_provider_enum = LLMProvider.OLLAMA
            embedding_dims = get_embedding_dims(llm_config)
            memory_logger.info(f"🔧 Setting Embedder dims {embedding_dims}")

        # Build vector store configuration
        vector_store_provider = os.getenv("VECTOR_STORE_PROVIDER", "qdrant").lower()
        
        if vector_store_provider == "qdrant":
            qdrant_host = os.getenv("QDRANT_BASE_URL", "qdrant")
            vector_store_config = create_qdrant_config(
                host=qdrant_host,
                port=int(os.getenv("QDRANT_PORT", "6333")),
                collection_name="omi_memories",
                embedding_dims=embedding_dims
            )
            vector_store_provider_enum = VectorStoreProvider.QDRANT
            
        else:
            raise ValueError(f"Unsupported vector store provider: {vector_store_provider}")
        
        # Get memory extraction settings
        extraction_enabled = config_loader.is_memory_extraction_enabled()
        extraction_prompt = config_loader.get_memory_prompt() if extraction_enabled else None
        
        memory_logger.info(f"🔧 Memory config: Provider=Chronicle, LLM={llm_provider}, VectorStore={vector_store_provider}, Extraction={extraction_enabled}")
        
        return MemoryConfig(
            memory_provider=memory_provider_enum,
            llm_provider=llm_provider_enum,
            vector_store_provider=vector_store_provider_enum,
            llm_config=llm_config,
            vector_store_config=vector_store_config,
            embedder_config={},  # Included in llm_config
            extraction_prompt=extraction_prompt,
            extraction_enabled=extraction_enabled,
            timeout_seconds=timeout_seconds,
        )

    except ImportError:
        memory_logger.warning("Config loader not available, using environment variables only")
        raise


def get_embedding_dims(llm_config: Dict[str, Any]) -> int:
    """
    Query the embedding endpoint and return the embedding vector length.
    Works for OpenAI and OpenAI-compatible endpoints (e.g., Ollama).
    """
    embedding_model = llm_config.get("embedding_model")
    try:
        reg = get_models_registry()
        if reg:
            emb_def = reg.get_default("embedding")
            if emb_def and emb_def.embedding_dimensions:
                return int(emb_def.embedding_dimensions)
    except Exception as e:
        memory_logger.exception(
            f"Failed to get embedding dimensions from registry for model '{embedding_model}'"
        )
        raise e
