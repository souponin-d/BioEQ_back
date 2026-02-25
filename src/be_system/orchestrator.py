import json
from pathlib import Path

from be_system.agents.planner_agent import PlannerAgent
from be_system.agents.reviewer_agent import ReviewerAgent
from be_system.schemas import OrchestratorResult


class Orchestrator:
    def __init__(self, planner_agent: PlannerAgent, reviewer_agent: ReviewerAgent):
        self.planner_agent = planner_agent
        self.reviewer_agent = reviewer_agent

    def run(self, user_input_path: str | Path) -> OrchestratorResult:
        user_input = json.loads(Path(user_input_path).read_text(encoding="utf-8"))
        planner_output = self.planner_agent.run(user_input)
        reviewer_output = self.reviewer_agent.run(planner_output)
        return OrchestratorResult(
            user_input=user_input,
            planner_output=planner_output,
            reviewer_output=reviewer_output,
        )
