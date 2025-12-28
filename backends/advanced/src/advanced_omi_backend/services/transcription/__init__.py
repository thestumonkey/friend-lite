"""
Transcription providers and registry-driven factory.

This module exposes a provider that reads its configuration from the
central model registry (config.yml). No environment-based selection
or provider-specific branching is used for batch transcription.
"""

import asyncio
import json
import logging
from typing import Optional

import httpx
import websockets

from advanced_omi_backend.model_registry import get_models_registry
from .base import BaseTranscriptionProvider, BatchTranscriptionProvider, StreamingTranscriptionProvider

logger = logging.getLogger(__name__)


def get_transcription_provider(
    provider_name: Optional[str] = None,
    mode: Optional[str] = None,
    allow_missing_keys: bool = False,
) -> Optional[BaseTranscriptionProvider]:
    """
    if d is None or not dotted:
        return None
    cur = d
    for part in dotted.split('.'):
        if not part:
            continue
        if '[' in part and part.endswith(']'):
            name, idx_str = part[:-1].split('[', 1)
            if name:
                cur = cur.get(name, {}) if isinstance(cur, dict) else {}
            try:
                idx = int(idx_str)
            except Exception:
                return None
            if isinstance(cur, list) and 0 <= idx < len(cur):
                cur = cur[idx]
            else:
                return None
        else:
            cur = cur.get(part, None) if isinstance(cur, dict) else None
        if cur is None:
            return None
    return cur

    Args:
        provider_name: Name of the provider ('deepgram', 'parakeet').
                      If None, will auto-select based on available configuration.
        mode: Processing mode ('streaming', 'batch'). If None, defaults to 'batch'.
        allow_missing_keys: If True, return None instead of raising error when
                           provider is requested but API key is not configured.
                           Enables graceful degradation mode.

class RegistryBatchTranscriptionProvider(BatchTranscriptionProvider):
    """Batch transcription provider driven by config.yml."""

    Raises:
        RuntimeError: If a specific provider is requested but not properly configured
                     (only when allow_missing_keys=False).
    """
    deepgram_key = os.getenv("DEEPGRAM_API_KEY")
    parakeet_url = os.getenv("PARAKEET_ASR_URL")

    if provider_name:
        provider_name = provider_name.lower()

    if mode is None:
        mode = "batch"
    mode = mode.lower()

    # Handle specific provider requests
    if provider_name == "deepgram":
        if not deepgram_key:
            if allow_missing_keys:
                logger.debug(
                    "Deepgram provider requested but DEEPGRAM_API_KEY not configured (graceful degradation mode)"
                )
                return None
            raise RuntimeError(
                "Deepgram transcription provider requested but DEEPGRAM_API_KEY not configured"
            )
        logger.info(f"Using Deepgram transcription provider in {mode} mode")
        if mode == "streaming":
            return DeepgramStreamingProvider(deepgram_key)
        else:
            return DeepgramProvider(deepgram_key)

    elif provider_name == "parakeet":
        if not parakeet_url:
            if allow_missing_keys:
                logger.debug(
                    "Parakeet provider requested but PARAKEET_ASR_URL not configured (graceful degradation mode)"
                )
                return None
            raise RuntimeError(
                "Parakeet ASR provider requested but PARAKEET_ASR_URL not configured"
            )
        logger.info(f"Using Parakeet transcription provider in {mode} mode")
        if mode == "streaming":
            return ParakeetStreamingProvider(parakeet_url)
        else:
            return ParakeetProvider(parakeet_url)

    # Auto-select provider based on available configuration (when provider_name is None)
    if provider_name is None:
        # Check TRANSCRIPTION_PROVIDER environment variable first
        env_provider = os.getenv("TRANSCRIPTION_PROVIDER")
        if env_provider:
            # Recursively call with the specified provider (pass allow_missing_keys through)
            return get_transcription_provider(env_provider, mode, allow_missing_keys)

        # Auto-select: prefer Deepgram if available, fallback to Parakeet
        if deepgram_key:
            logger.info(f"Auto-selected Deepgram transcription provider in {mode} mode")
            if mode == "streaming":
                return DeepgramStreamingProvider(deepgram_key)
            else:
                return DeepgramProvider(deepgram_key)
        elif parakeet_url:
            logger.info(f"Auto-selected Parakeet transcription provider in {mode} mode")
            if mode == "streaming":
                return ParakeetStreamingProvider(parakeet_url)
            else:
                resp = await client.get(url, headers=headers, params=query)
            resp.raise_for_status()
            data = resp.json()

        # Extract normalized shape
        text, words, segments = "", [], []
        extract = (op.get("response", {}) or {}).get("extract") or {}
        if extract:
            text = _dotted_get(data, extract.get("text")) or ""
            words = _dotted_get(data, extract.get("words")) or []
            segments = _dotted_get(data, extract.get("segments")) or []
        return {"text": text, "words": words, "segments": segments}

class RegistryStreamingTranscriptionProvider(StreamingTranscriptionProvider):
    """Streaming transcription provider using a config-driven WebSocket template."""

    def __init__(self):
        registry = get_models_registry()
        if not registry:
            raise RuntimeError("config.yml not found; cannot configure streaming STT provider")
        model = registry.get_default("stt_stream")
        if not model:
            raise RuntimeError("No default stt_stream model defined in config.yml")
        self.model = model
        self._name = model.model_provider or model.name
        self._streams: dict[str, dict] = {}

    @property
    def name(self) -> str:
        return self._name

    async def start_stream(self, client_id: str, sample_rate: int = 16000, diarize: bool = False):
        url = self.model.model_url
        ops = self.model.operations or {}
        start_msg = (ops.get("start", {}) or {}).get("message", {})
        # Inject session_id if placeholder present
        start_msg = json.loads(json.dumps(start_msg))  # deep copy
        start_msg.setdefault("session_id", client_id)
        # Apply sample rate and diarization if present
        if "config" in start_msg and isinstance(start_msg["config"], dict):
            start_msg["config"].setdefault("sample_rate", sample_rate)
            if diarize:
                start_msg["config"]["diarize"] = True

        ws = await websockets.connect(url, open_timeout=10)
        await ws.send(json.dumps(start_msg))
        # Wait for confirmation; non-fatal if not provided
        try:
            await asyncio.wait_for(ws.recv(), timeout=2.0)
        except Exception:
            pass
        self._streams[client_id] = {"ws": ws, "sample_rate": sample_rate, "final": None, "interim": []}

    async def process_audio_chunk(self, client_id: str, audio_chunk: bytes) -> dict | None:
        if client_id not in self._streams:
            return None
        ws = self._streams[client_id]["ws"]
        ops = self.model.operations or {}
        chunk_hdr = (ops.get("chunk_header", {}) or {}).get("message", {})
        hdr = json.loads(json.dumps(chunk_hdr))
        hdr.setdefault("type", "audio_chunk")
        hdr.setdefault("session_id", client_id)
        hdr.setdefault("rate", self._streams[client_id]["sample_rate"])
        await ws.send(json.dumps(hdr))
        await ws.send(audio_chunk)

        # Non-blocking read for interim results
        expect = (ops.get("expect", {}) or {})
        interim_type = expect.get("interim_type")
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=0.01)
                data = json.loads(msg)
                if interim_type and data.get("type") == interim_type:
                    self._streams[client_id]["interim"].append(data)
        except asyncio.TimeoutError:
            pass
        return None

    async def end_stream(self, client_id: str) -> dict:
        if client_id not in self._streams:
            return {"text": "", "words": [], "segments": []}
        ws = self._streams[client_id]["ws"]
        ops = self.model.operations or {}
        end_msg = (ops.get("end", {}) or {}).get("message", {"type": "stop"})
        await ws.send(json.dumps(end_msg))

        expect = (ops.get("expect", {}) or {})
        final_type = expect.get("final_type")
        extract = expect.get("extract", {})

        final = None
        try:
            # Drain until final or close
            for _ in range(500):  # hard cap
                msg = await asyncio.wait_for(ws.recv(), timeout=1.5)
                data = json.loads(msg)
                if not final_type or data.get("type") == final_type:
                    final = data
                    break
        except Exception:
            pass
        try:
            await ws.close()
        except Exception:
            pass

        self._streams.pop(client_id, None)

        if not isinstance(final, dict):
            return {"text": "", "words": [], "segments": []}
        return {
            "text": _dotted_get(final, extract.get("text")) if extract else final.get("text", ""),
            "words": _dotted_get(final, extract.get("words")) if extract else final.get("words", []),
            "segments": _dotted_get(final, extract.get("segments")) if extract else final.get("segments", []),
        }


def get_transcription_provider(provider_name: Optional[str] = None, mode: Optional[str] = None) -> Optional[BaseTranscriptionProvider]:
    """Return a registry-driven transcription provider.

    - mode="batch": HTTP-based STT (default)
    - mode="streaming": WebSocket-based STT

    Note: The models registry returns None when config.yml is missing or invalid.
    We avoid broad exception handling here and simply return None when the
    required defaults are not configured.
    """
    registry = get_models_registry()
    if not registry:
        return None

    selected_mode = (mode or "batch").lower()
    if selected_mode == "streaming":
        if not registry.get_default("stt_stream"):
            return None
        return RegistryStreamingTranscriptionProvider()

    # batch mode
    if not registry.get_default("stt"):
        return None
    return RegistryBatchTranscriptionProvider()


__all__ = [
    "get_transcription_provider",
    "RegistryBatchTranscriptionProvider",
    "RegistryStreamingTranscriptionProvider",
    "BaseTranscriptionProvider",
    "BatchTranscriptionProvider",
    "StreamingTranscriptionProvider",
]
