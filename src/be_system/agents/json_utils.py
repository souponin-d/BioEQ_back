import json
import logging
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


def extract_json(text: str) -> dict:
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    if text.startswith("```"):
        lines = [line for line in text.splitlines() if not line.startswith("```")]
        fenced_candidate = "\n".join(lines).strip()
        try:
            return json.loads(fenced_candidate)
        except json.JSONDecodeError:
            LOGGER.debug("Failed to parse fenced JSON candidate: %s", fenced_candidate)

    for candidate in _iter_json_object_candidates(text):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            LOGGER.debug("Failed to parse extracted JSON candidate: %s", candidate)

    LOGGER.debug("Failed to parse raw LLM output as JSON: %s", text)
    raise ValueError("LLM response is not valid JSON.")
