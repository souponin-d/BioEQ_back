import json

from be_system.llm_client import LLMClient
from be_system.schemas import PlannerOutput, ReviewerOutput


class ReviewerAgent:
    SYSTEM_PROMPT = (
        "Ты независимый эксперт по контролю качества дизайна биоэквивалентности. "
        "Проверяй логическую согласованность. Отвечай строго JSON."
    )

    USER_PROMPT_TEMPLATE = """Проверь предложенный дизайн биоэквивалентности на логическую согласованность.

Planner output:
{planner_output}

Output строго:
{{
  "is_consistent": true/false,
  "comments": "...",
  "risk_flags": []
}}
"""

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def run(self, planner_output: PlannerOutput) -> ReviewerOutput:
        prompt = self.USER_PROMPT_TEMPLATE.format(
            planner_output=planner_output.model_dump_json(indent=2)
        )
        raw = self.llm_client.chat(self.SYSTEM_PROMPT, prompt)
        data = json.loads(raw)
        return ReviewerOutput.model_validate(data)
