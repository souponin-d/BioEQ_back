import json
import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from be_system.agents.planner_agent import PlannerAgent
from be_system.agents.reviewer_agent import ReviewerAgent
from be_system.llm_client import LLMClient
from be_system.logging_utils import fmt_seconds, setup_logging, timer
from be_system.orchestrator import Orchestrator

load_dotenv()

DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct"


def main() -> None:
    log_level = os.getenv("LOG_LEVEL", "INFO")
    logger = setup_logging(log_level)
    t0 = time.perf_counter()

    logger.info("Application start")
    try:
        base_url = os.getenv("VLLM_BASE_URL", "http://127.0.0.1:8000/v1")
        api_key = os.getenv("VLLM_API_KEY", "local")
        input_path = Path(os.getenv("USER_INPUT_PATH", "configs/user_input.json"))

        planner_model = os.getenv("PLANNER_MODEL", os.getenv("VLLM_MODEL", DEFAULT_MODEL))
        reviewer_model = os.getenv("REVIEWER_MODEL", os.getenv("VLLM_MODEL", DEFAULT_MODEL))

        logger.info(
            "Selected models | planner=%s | reviewer=%s", planner_model, reviewer_model
        )
        logger.info("Paths | project_root=%s | input_path=%s", PROJECT_ROOT, input_path)

        planner_llm = LLMClient(base_url=base_url, api_key=api_key, model_name=planner_model)
        reviewer_llm = LLMClient(base_url=base_url, api_key=api_key, model_name=reviewer_model)

        orchestrator = Orchestrator(
            planner_agent=PlannerAgent(planner_llm),
            reviewer_agent=ReviewerAgent(reviewer_llm),
        )

        with timer("orchestrator_run", logger):
            result = orchestrator.run(input_path)

        logger.info("Printing outputs")
        print("Planner output:")
        print(json.dumps(result.planner_output.model_dump(), ensure_ascii=False, indent=2))
        print("\nReviewer output:")
        print(json.dumps(result.reviewer_output.model_dump(), ensure_ascii=False, indent=2))

        logger.info("Application finished successfully")
    except Exception:
        logger.exception("Application failed")
        raise
    finally:
        total_elapsed = time.perf_counter() - t0
        logger.info("Total elapsed | elapsed=%ss", fmt_seconds(total_elapsed))


if __name__ == "__main__":
    main()
