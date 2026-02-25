import json

from be_system.llm_client import LLMClient
from be_system.schemas import PlannerOutput


class PlannerAgent:
    SYSTEM_PROMPT = (
        "Ты эксперт по дизайну исследований биоэквивалентности. "
        "Отвечай строго JSON без текста вне JSON."
    )

    USER_PROMPT_TEMPLATE = """Передаётся JSON вход. Нужно синтетически спланировать исследование биоэквивалентности.

Input:
{input_json}

Output строго:
{{
  "selected_design": "...",
  "washout_days": int,
  "requires_rsabe": bool,
  "estimated_sample_size": int,
  "notes": "..."
}}
"""

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def run(self, user_input: dict) -> PlannerOutput:
        prompt = self.USER_PROMPT_TEMPLATE.format(
            input_json=json.dumps(user_input, ensure_ascii=False, indent=2)
        )
        raw = self.llm_client.chat(self.SYSTEM_PROMPT, prompt)
        data = json.loads(raw)
        return PlannerOutput.model_validate(data)
