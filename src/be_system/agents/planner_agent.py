import json
import logging

from be_system.agents.json_utils import extract_json
from be_system.llm_client import LLMClient
from be_system.prompts import PLANNER_SYSTEM_PROMPT, PLANNER_USER_PROMPT_TEMPLATE
from be_system.schemas import PlannerOutput


class PlannerAgent:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.logger = logging.getLogger("be_system.agents.planner")

    def run(self, user_input: dict) -> PlannerOutput:
        input_json = json.dumps(user_input, ensure_ascii=False, indent=2)
        prompt = PLANNER_USER_PROMPT_TEMPLATE.format(input_json=input_json)

        self.logger.info("PlannerAgent start | input_size=%d", len(input_json))
        self.logger.debug("Planner prompt preview: %s", prompt[:200])
        self.logger.info("PlannerAgent sending request")

        raw = self.llm_client.chat(PLANNER_SYSTEM_PROMPT, prompt)
        self.logger.info("PlannerAgent received raw response | response_len=%d", len(raw))
        self.logger.debug("Planner raw response preview: %s", raw[:200])

        try:
            data = extract_json(raw)
            self.logger.info("PlannerAgent JSON parse completed")
        except Exception as exc:
            self.logger.exception("PlannerAgent JSON parse failed")
            raise ValueError("PlannerAgent failed to parse JSON response.") from exc

        result = PlannerOutput.model_validate(data)
        self.logger.info("PlannerAgent end")
        return result
