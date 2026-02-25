from typing import Any

from pydantic import BaseModel


class PlannerOutput(BaseModel):
    selected_design: str
    washout_days: int
    requires_rsabe: bool
    estimated_sample_size: int
    notes: str


class ReviewerOutput(BaseModel):
    is_consistent: bool
    comments: str
    risk_flags: list[str]


class OrchestratorResult(BaseModel):
    user_input: dict[str, Any]
    planner_output: PlannerOutput
    reviewer_output: ReviewerOutput
