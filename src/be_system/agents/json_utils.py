import json
import logging


LOGGER = logging.getLogger("be_system.agents.json_utils")


def extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    first_open = text.find("{")
    last_close = text.rfind("}")

    if first_open != -1 and last_close != -1 and first_open < last_close:
        candidate = text[first_open : last_close + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            LOGGER.debug("Failed to parse extracted JSON candidate: %s", candidate)

    LOGGER.debug("Failed to parse raw LLM output as JSON: %s", text)
    raise ValueError("LLM response is not valid JSON.")
