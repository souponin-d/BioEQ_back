import json
import logging

from be_system.agents.json_utils import extract_json
from be_system.llm_client import LLMClient
from be_system.prompts import PLANNER_SYSTEM_PROMPT, PLANNER_USER_PROMPT_TEMPLATE
from be_system.schemas import PlannerOutput


class PlannerAgent:
    _FALLBACK_OUTPUT = {
        "selected_design": "2x2 crossover",
        "washout_days": 7,
        "requires_rsabe": False,
        "estimated_sample_size": 24,
        "notes": "fallback_planner_output",
    }

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.logger = logging.getLogger("be_system.agents.planner")

    def run(self, user_input: dict) -> PlannerOutput:
        input_json = json.dumps(user_input, ensure_ascii=False, indent=2)
        prompt = PLANNER_USER_PROMPT_TEMPLATE.format(input_json=input_json)
        self.logger.debug("Planner prompt_len=%d", len(prompt))

        raw = self.llm_client.chat(PLANNER_SYSTEM_PROMPT, prompt)
        self.logger.debug("Planner raw LLM response: %s", raw)

        try:
            data = extract_json(raw)
        except Exception:
            self.logger.warning("Planner JSON invalid, attempting repair")
            self.logger.debug("Raw LLM response: %s", raw[:500])
            repair_prompt = (
                "Fix the following response so that it becomes STRICTLY valid JSON.\n"
                "Return ONLY JSON.\n"
                "Do not explain.\n"
                "Response:\n" + raw
            )
            repaired = self.llm_client.chat(PLANNER_SYSTEM_PROMPT, repair_prompt)

            try:
                data = extract_json(repaired)
            except Exception:
                self.logger.error("Planner JSON repair failed, using fallback")
                self.logger.debug("Raw LLM response: %s", raw[:500])
                data = self._FALLBACK_OUTPUT.copy()

        return PlannerOutput.model_validate(data)
