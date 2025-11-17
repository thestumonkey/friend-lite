"""
Conversation utilities - speech detection, title/summary generation.

Extracted from legacy TranscriptionService to be reusable across V2 architecture.
"""

import logging
from typing import Optional

from advanced_omi_backend.config import get_speech_detection_settings
from advanced_omi_backend.llm_client import async_generate

logger = logging.getLogger(__name__)


def is_meaningful_speech(combined_results: dict) -> bool:
    """
    Convenience wrapper to check if combined transcription results contain meaningful speech.

    This is a shared helper used by both speech detection and conversation timeout logic.

    Args:
        combined_results: Combined results from TranscriptionResultsAggregator with:
            - "text": str - Full transcript text
            - "words": list - Word-level data with confidence and timing
            - "segments": list - Speaker segments
            - "chunk_count": int - Number of chunks processed

    Returns:
        bool: True if meaningful speech detected, False otherwise

    Example:
        >>> combined = await aggregator.get_combined_results(session_id)
        >>> if is_meaningful_speech(combined):
        >>>     print("Meaningful speech detected!")
    """
    if not combined_results.get("text"):
        return False

    transcript_data = {
        "text": combined_results["text"],
        "words": combined_results.get("words", [])
    }

    speech_analysis = analyze_speech(transcript_data)
    return speech_analysis["has_speech"]


def analyze_speech(transcript_data: dict) -> dict:
    """
    Analyze transcript for meaningful speech to determine if conversation should be created.

    Uses configurable thresholds from environment:
    - SPEECH_DETECTION_MIN_WORDS (default: 5)
    - SPEECH_DETECTION_MIN_CONFIDENCE (default: 0.5)

    Args:
        transcript_data: Dictionary with:
            - "text": str - Full transcript text
            - "words": list - Word-level data with confidence and timing (optional)
                [{"text": str, "confidence": float, "start": float, "end": float}, ...]

    Returns:
        dict: {
            "has_speech": bool,
            "reason": str,
            "word_count": int,
            "duration": float (seconds, 0.0 if no timing data),
            "speech_start": float (optional),
            "speech_end": float (optional),
            "fallback": bool (optional, true if text-only analysis)
        }

    Example:
        >>> result = analyze_speech({"text": "Hello world", "words": [...]})
        >>> if result["has_speech"]:
        >>>     print(f"Speech detected: {result['word_count']} words, {result['duration']}s")
    """
    settings = get_speech_detection_settings()
    words = transcript_data.get("words", [])

    # Method 1: Word-level analysis (preferred - has confidence scores and timing)
    if words:
        # Filter by confidence threshold
        valid_words = [
            w for w in words
            if w.get("confidence", 0) >= settings["min_confidence"]
        ]

        if len(valid_words) < settings["min_words"]:
            return {
                "has_speech": False,
                "reason": f"Not enough valid words ({len(valid_words)} < {settings['min_words']})",
                "word_count": len(valid_words),
                "duration": 0.0
            }

        # Calculate speech duration from word timing
        if valid_words:
            speech_start = valid_words[0].get("start", 0)
            speech_end = valid_words[-1].get("end", 0)
            speech_duration = speech_end - speech_start

            return {
                "has_speech": True,
                "word_count": len(valid_words),
                "speech_start": speech_start,
                "speech_end": speech_end,
                "duration": speech_duration,
                "reason": f"Valid speech detected ({len(valid_words)} words, {speech_duration:.1f}s)"
            }

    # Method 2: Text-only fallback (when no word-level data available)
    text = transcript_data.get("text", "").strip()
    if text:
        word_count = len(text.split())
        if word_count >= settings["min_words"]:
            return {
                "has_speech": True,
                "word_count": word_count,
                "speech_start": 0.0,
                "speech_end": 0.0,
                "duration": 0.0,
                "reason": f"Valid speech detected ({word_count} words, no timing data)",
                "fallback": True
            }

    # No speech detected
    return {
        "has_speech": False,
        "reason": "No meaningful speech content detected",
        "word_count": 0,
        "duration": 0.0
    }


async def generate_title(text: str, segments: Optional[list] = None) -> str:
    """
    Generate an LLM-powered title from conversation text.

    Args:
        text: Conversation transcript (used if segments not provided)
        segments: Optional list of speaker segments with structure:
            [{"speaker": str, "text": str, "start": float, "end": float}, ...]
            If provided, uses speaker-aware conversation formatting

    Returns:
        str: Generated title (3-6 words) or fallback

    Note:
        Title intentionally does NOT include speaker names - focuses on topic/theme only.
    """
    # Format conversation text from segments if provided
    if segments:
        conversation_text = ""
        for segment in segments[:10]:  # Use first 10 segments for title generation
            segment_text = segment.get("text", "").strip()
            if segment_text:
                conversation_text += f"{segment_text}\n"
        text = conversation_text if conversation_text.strip() else text

    if not text or len(text.strip()) < 10:
        return "Conversation"

    try:
        prompt = f"""Generate a concise, descriptive title (3-6 words) for this conversation transcript:

"{text[:500]}"

Rules:
- Maximum 6 words
- Capture the main topic or theme
- Do NOT include speaker names or participants
- No quotes or special characters
- Examples: "Planning Weekend Trip", "Work Project Discussion", "Medical Appointment"

Title:"""

        title = await async_generate(prompt, temperature=0.3)
        return title.strip().strip('"').strip("'") or "Conversation"

    except Exception as e:
        logger.warning(f"Failed to generate LLM title: {e}")
        # Fallback to simple title generation
        words = text.split()[:6]
        title = " ".join(words)
        return title[:40] + "..." if len(title) > 40 else title or "Conversation"


async def generate_short_summary(text: str, segments: Optional[list] = None) -> str:
    """
    Generate a brief LLM-powered summary from conversation text.

    Args:
        text: Conversation transcript (used if segments not provided)
        segments: Optional list of speaker segments with structure:
            [{"speaker": str, "text": str, "start": float, "end": float}, ...]
            If provided, includes speaker context in summary

    Returns:
        str: Generated short summary (1-2 sentences, max 120 chars) or fallback
    """
    # Format conversation text from segments if provided
    conversation_text = text
    include_speakers = False

    if segments:
        formatted_text = ""
        speakers_in_conv = set()
        for segment in segments:
            speaker = segment.get("speaker", "")
            segment_text = segment.get("text", "").strip()
            if segment_text:
                if speaker:
                    formatted_text += f"{speaker}: {segment_text}\n"
                    speakers_in_conv.add(speaker)
                else:
                    formatted_text += f"{segment_text}\n"

        if formatted_text.strip():
            conversation_text = formatted_text
            include_speakers = len(speakers_in_conv) > 0

    if not conversation_text or len(conversation_text.strip()) < 10:
        return "No content"

    try:
        speaker_instruction = "- Include speaker names when relevant (e.g., \"John discusses X with Sarah\")\n" if include_speakers else ""

        prompt = f"""Generate a brief, informative summary (1-2 sentences, max 120 characters) for this conversation:

"{conversation_text[:1000]}"

Rules:
- Maximum 120 characters
- 1-2 complete sentences
{speaker_instruction}- Capture key topics and outcomes
- Use present tense
- Be specific and informative

Summary:"""

        summary = await async_generate(prompt, temperature=0.3)
        return summary.strip().strip('"').strip("'") or "No content"

    except Exception as e:
        logger.warning(f"Failed to generate LLM short summary: {e}")
        # Fallback to simple summary generation
        return conversation_text[:120] + "..." if len(conversation_text) > 120 else conversation_text or "No content"


# Backward compatibility alias
async def generate_summary(text: str) -> str:
    """
    Backward compatibility wrapper for generate_short_summary.

    Deprecated: Use generate_short_summary instead.
    """
    return await generate_short_summary(text)


async def generate_detailed_summary(text: str, segments: Optional[list] = None) -> str:
    """
    Generate a comprehensive, detailed summary of the conversation.

    This summary provides full information about what was discussed and said,
    correcting transcript errors and removing filler words to create a higher
    quality information set. Not word-for-word like the transcript, but captures
    all key points, context, and meaningful content.

    Args:
        text: Conversation transcript (used if segments not provided)
        segments: Optional list of speaker segments with structure:
            [{"speaker": str, "text": str, "start": float, "end": float}, ...]
            If provided, includes speaker attribution in detailed summary

    Returns:
        str: Comprehensive detailed summary (multiple paragraphs) or fallback
    """
    # Format conversation text from segments if provided
    conversation_text = text
    include_speakers = False

    if segments:
        formatted_text = ""
        speakers_in_conv = set()
        for segment in segments:
            speaker = segment.get("speaker", "")
            segment_text = segment.get("text", "").strip()
            if segment_text:
                if speaker:
                    formatted_text += f"{speaker}: {segment_text}\n"
                    speakers_in_conv.add(speaker)
                else:
                    formatted_text += f"{segment_text}\n"

        if formatted_text.strip():
            conversation_text = formatted_text
            include_speakers = len(speakers_in_conv) > 0

    if not conversation_text or len(conversation_text.strip()) < 10:
        return "No meaningful content to summarize"

    try:
        speaker_instruction = """- Attribute key points and statements to specific speakers when relevant
- Capture the flow of conversation between participants
- Note any agreements, disagreements, or important exchanges
""" if include_speakers else ""

        prompt = f"""Generate a comprehensive, detailed summary of this conversation transcript.

TRANSCRIPT:
"{conversation_text}"

INSTRUCTIONS:
Your task is to create a high-quality, detailed summary of a conversation transcription that captures the full information and context of what was discussed. This is NOT a brief summary - provide comprehensive coverage.

Rules:
- We know it's a conversation, so no need to say "This conversation involved..."
- Provide complete coverage of all topics, points, and important details discussed
- Correct obvious transcription errors and remove filler words (um, uh, like, you know)
- Organize information logically by topic or chronologically as appropriate
- Use clear, well-structured paragraphs or bullet points
- Maintain the meaning and intent of what was said, but improve clarity and coherence
- Include relevant context, decisions made, action items mentioned, and conclusions reached
{speaker_instruction}- Write in a natural, flowing narrative style
- Only include word-for-word quotes if it's more efficiency than rephrasing
- Focus on substantive content - what was actually discussed and decided

Think of this as creating a high-quality information set that someone could use to understand everything important that happened in this conversation without reading the full transcript.

DETAILED SUMMARY:"""

        summary = await async_generate(prompt, temperature=0.3)
        return summary.strip().strip('"').strip("'") or "No meaningful content to summarize"

    except Exception as e:
        logger.warning(f"Failed to generate detailed summary: {e}")
        # Fallback to returning cleaned transcript
        lines = conversation_text.split('\n')
        cleaned = '\n'.join(line.strip() for line in lines if line.strip())
        return cleaned[:2000] + "..." if len(cleaned) > 2000 else cleaned or "No meaningful content to summarize"


# Backward compatibility aliases for deprecated speaker-specific methods
async def generate_title_with_speakers(segments: list) -> str:
    """
    Deprecated: Use generate_title(text, segments=segments) instead.

    Backward compatibility wrapper.
    """
    if not segments:
        return "Conversation"
    # Extract text from segments for compatibility
    text = "\n".join(s.get("text", "") for s in segments if s.get("text"))
    return await generate_title(text, segments=segments)


async def generate_summary_with_speakers(segments: list) -> str:
    """
    Deprecated: Use generate_short_summary(text, segments=segments) instead.

    Backward compatibility wrapper.
    """
    if not segments:
        return "No content"
    # Extract text from segments for compatibility
    text = "\n".join(s.get("text", "") for s in segments if s.get("text"))
    return await generate_short_summary(text, segments=segments)
