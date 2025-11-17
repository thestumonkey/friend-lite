"""Prompt formatting for conversation extraction."""

from datetime import timedelta
from pathlib import Path

import yaml

from convos.utils import get_silence_message, get_timestamp_message




def chunk_to_prompt(chunk: list[dict]):
    """Convert conversation chunk to LLM prompt format."""
    earliest = chunk[0]["start"]
    latest = chunk[0]["end"]
    strings = [get_timestamp_message(earliest)]

    for c in chunk:
        gap = (c["start"] - latest)
        if gap > timedelta(seconds=30):
            strings.append(get_timestamp_message(latest))
            strings.append(get_silence_message(gap))
            strings.append(get_timestamp_message(c["start"]))
        strings.append(c["text"])
        latest = max(latest, c["end"])

    strings.append(get_timestamp_message(latest))
    return "\n".join(strings), earliest, latest


def get_prompts():
    with open(Path(__file__).parent / "prompts.yml", "r") as f:
        return yaml.safe_load(f)