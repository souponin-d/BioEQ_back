import json
import logging
from pathlib import Path

from be_system.agents.planner_agent import PlannerAgent
from be_system.agents.reviewer_agent import ReviewerAgent
from be_system.logging_utils import timer
from be_system.schemas import OrchestratorResult


class Orchestrator:
    def __init__(self, planner_agent: PlannerAgent, reviewer_agent: ReviewerAgent):
        self.planner_agent = planner_agent
        self.reviewer_agent = reviewer_agent
        self.logger = logging.getLogger("be_system.orchestrator")

    def run(self, user_input_path: str | Path) -> OrchestratorResult:
        self.logger.info("Orchestrator run start | input_path=%s", user_input_path)

        with timer("load_input", self.logger):
            user_input = json.loads(Path(user_input_path).read_text(encoding="utf-8"))
        self.logger.info("Loaded user input | top_level_keys=%s", list(user_input.keys()))

        with timer("planner_call", self.logger):
            self.logger.info("Calling PlannerAgent")
            planner_output = self.planner_agent.run(user_input)
        self.logger.info("Planner output ready")

        with timer("reviewer_call", self.logger):
            self.logger.info("Calling ReviewerAgent")
            reviewer_output = self.reviewer_agent.run(planner_output)
        self.logger.info("Reviewer output ready")

        result = OrchestratorResult(
            user_input=user_input,
            planner_output=planner_output,
            reviewer_output=reviewer_output,
        )
        self.logger.info("Orchestrator run end")
        return result
