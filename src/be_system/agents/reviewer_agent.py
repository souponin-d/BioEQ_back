import logging

from be_system.agents.json_utils import extract_json
from be_system.llm_client import LLMClient
from be_system.prompts import REVIEWER_SYSTEM_PROMPT, REVIEWER_USER_PROMPT_TEMPLATE
from be_system.schemas import PlannerOutput, ReviewerOutput


class ReviewerAgent:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.logger = logging.getLogger("be_system.agents.reviewer")

    def run(self, planner_output: PlannerOutput) -> ReviewerOutput:
        planner_json = planner_output.model_dump_json(indent=2)
        prompt = REVIEWER_USER_PROMPT_TEMPLATE.format(planner_output=planner_json)
        self.logger.debug("Reviewer prompt_len=%d", len(prompt))

        raw = self.llm_client.chat(REVIEWER_SYSTEM_PROMPT, prompt)
        self.logger.debug("Reviewer raw LLM response: %s", raw)

        try:
            data = extract_json(raw)
        except Exception as exc:
            self.logger.exception("Reviewer JSON parse failed")
            raise ValueError("ReviewerAgent failed to parse JSON response.") from exc

        return ReviewerOutput.model_validate(data)
