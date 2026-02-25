import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from be_system.agents.planner_agent import PlannerAgent
from be_system.agents.reviewer_agent import ReviewerAgent
from be_system.llm_client import LLMClient
from be_system.orchestrator import Orchestrator

load_dotenv()

PLANNER_MODEL = "qwen2.5-7b"
REVIEWER_MODEL = "qwen2.5-7b"


def main() -> None:
    base_url = os.getenv("VLLM_BASE_URL", "http://127.0.0.1:8000/v1")
    api_key = os.getenv("VLLM_API_KEY", "local")

    planner_llm = LLMClient(base_url=base_url, api_key=api_key, model_name=PLANNER_MODEL)
    reviewer_llm = LLMClient(base_url=base_url, api_key=api_key, model_name=REVIEWER_MODEL)

    orchestrator = Orchestrator(
        planner_agent=PlannerAgent(planner_llm),
        reviewer_agent=ReviewerAgent(reviewer_llm),
    )

    result = orchestrator.run(Path("configs/user_input.json"))

    print("Planner output:")
    print(json.dumps(result.planner_output.model_dump(), ensure_ascii=False, indent=2))
    print("\nReviewer output:")
    print(json.dumps(result.reviewer_output.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
