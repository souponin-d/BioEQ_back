from be_system.agents.planner_agent import PlannerAgent


class StubLLMClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return self.responses.pop(0)


def test_planner_agent_repairs_invalid_json():
    llm = StubLLMClient(
        [
            "bad output",
            '{"selected_design":"replicate","washout_days":10,"requires_rsabe":true,"estimated_sample_size":36,"notes":"fixed"}',
        ]
    )
    agent = PlannerAgent(llm)

    result = agent.run({"inn": "drug"})

    assert result.selected_design == "replicate"
    assert result.washout_days == 10
    assert len(llm.calls) == 2


def test_planner_agent_uses_fallback_after_failed_repair():
    llm = StubLLMClient(["still bad", "also bad"])
    agent = PlannerAgent(llm)

    result = agent.run({"inn": "drug"})

    assert result.selected_design == "2x2 crossover"
    assert result.washout_days == 7
    assert result.requires_rsabe is False
    assert result.estimated_sample_size == 24
    assert result.notes == "fallback_planner_output"
    assert len(llm.calls) == 2
