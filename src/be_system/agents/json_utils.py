import json
import logging
import re
from collections.abc import Iterator


LOGGER = logging.getLogger("be_system.agents.json_utils")


def _iter_json_object_candidates(text: str) -> Iterator[str]:
    in_string = False
    escaped = False
    depth = 0
    start_idx: int | None = None

    for idx, ch in enumerate(text):
        if escaped:
            escaped = False
            continue

        if ch == "\\":
            escaped = in_string
            continue

        if ch == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if ch == "{":
            if depth == 0:
                start_idx = idx
            depth += 1
            continue

        if ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start_idx is not None:
                yield text[start_idx : idx + 1]
                start_idx = None


def _sanitize_json_candidate(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"[\u200b\u200c\u200d\ufeff\x00-\x1f]", "", cleaned)
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
    return cleaned


def extract_json(text: str) -> dict:
    text = text.strip()

    candidates: list[str] = [text]

    fenced_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced_match:
        candidates.append(fenced_match.group(1))

    first_object_match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if first_object_match:
        candidates.append(first_object_match.group(0))

    candidates.extend(_iter_json_object_candidates(text))

    for candidate in candidates:
        sanitized = _sanitize_json_candidate(candidate)
        try:
            return json.loads(sanitized)
        except json.JSONDecodeError:
            LOGGER.debug("Failed to parse JSON candidate: %s", sanitized)

    LOGGER.debug("Failed to parse raw LLM output as JSON: %s", text)
    raise ValueError("LLM response is not valid JSON.")
