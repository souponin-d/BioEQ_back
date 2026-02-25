import json
import os
import sys
import time
from pathlib import Path

from Bio import Entrez
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from be_system.agents.planner_agent import PlannerAgent
from be_system.agents.pk_extractor_agent import PKExtractorAgent
from be_system.agents.abstract_evaluator_agent import AbstractEvaluatorAgent
from be_system.agents.pmc_resolver_agent import PMCResolverAgent
from be_system.agents.pubmed_fetch_agent import PubMedFetchAgent
from be_system.agents.pdf_downloader_agent import PdfDownloaderAgent
from be_system.agents.pdf_parser_agent import PdfParserAgent
from be_system.agents.retrieval_agent import RetrievalAgent
from be_system.agents.pubmed_search_agent import PubMedSearchAgent
from be_system.agents.reviewer_agent import ReviewerAgent
from be_system.agents.xml_downloader_agent import XmlDownloaderAgent
from be_system.agents.xml_parser_agent import XmlParserAgent
from be_system.llm_client import LLMClient
from be_system.logging_utils import fmt_seconds, setup_logging
from be_system.orchestrator import Orchestrator

load_dotenv()

DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct"
ENTREZ_EMAIL = "example@example.com"
ENTREZ_TOOL = "be_system_proto"
PUBMED_N_ARTICLES = 5
LOG_LEVEL = "INFO"
PUBMED_CYCLES = 2
PUBMED_SLEEP_SEC = 1.0


def main() -> None:
    log_level = os.getenv("LOG_LEVEL", LOG_LEVEL)
    logger = setup_logging(log_level)
    t0 = time.perf_counter()

    logger.info("Application start")
    try:
        Entrez.email = os.getenv("ENTREZ_EMAIL", ENTREZ_EMAIL)
        Entrez.tool = os.getenv("ENTREZ_TOOL", ENTREZ_TOOL)

        base_url = os.getenv("VLLM_BASE_URL", "http://127.0.0.1:8000/v1")
        api_key = os.getenv("VLLM_API_KEY", "local")
        input_path = Path(os.getenv("USER_INPUT_PATH", "configs/user_input.json"))
        pubmed_n_articles = int(os.getenv("PUBMED_N_ARTICLES", str(PUBMED_N_ARTICLES)))
        pubmed_cycles = int(os.getenv("PUBMED_CYCLES", str(PUBMED_CYCLES)))
        pubmed_sleep_sec = float(os.getenv("PUBMED_SLEEP_SEC", str(PUBMED_SLEEP_SEC)))

        planner_model = os.getenv("PLANNER_MODEL", os.getenv("VLLM_MODEL", DEFAULT_MODEL))
        reviewer_model = os.getenv("REVIEWER_MODEL", os.getenv("VLLM_MODEL", DEFAULT_MODEL))
        analysis_model = os.getenv(
            "ABSTRACT_ANALYSIS_MODEL", os.getenv("VLLM_MODEL", DEFAULT_MODEL)
        )

        logger.info(
            "Selected models | planner=%s | abstract_analysis=%s | reviewer=%s",
            planner_model,
            analysis_model,
            reviewer_model,
        )

        planner_llm = LLMClient(base_url=base_url, api_key=api_key, model_name=planner_model)
        reviewer_llm = LLMClient(base_url=base_url, api_key=api_key, model_name=reviewer_model)
        analysis_llm = LLMClient(base_url=base_url, api_key=api_key, model_name=analysis_model)

        orchestrator = Orchestrator(
            planner_agent=PlannerAgent(planner_llm),
            pubmed_search_agent=PubMedSearchAgent(
                n_articles=pubmed_n_articles,
                pubmed_sleep_sec=pubmed_sleep_sec,
            ),
            pubmed_fetch_agent=PubMedFetchAgent(pubmed_sleep_sec=pubmed_sleep_sec),
            abstract_evaluator_agent=AbstractEvaluatorAgent(),
            pmc_resolver_agent=PMCResolverAgent(pubmed_sleep_sec=pubmed_sleep_sec),
            pdf_downloader_agent=PdfDownloaderAgent(),
            xml_downloader_agent=XmlDownloaderAgent(),
            pdf_parser_agent=PdfParserAgent(),
            xml_parser_agent=XmlParserAgent(),
            retrieval_agent=RetrievalAgent(),
            pk_extractor_agent=PKExtractorAgent(analysis_llm),
            reviewer_agent=ReviewerAgent(reviewer_llm),
            pubmed_cycles=pubmed_cycles,
            pubmed_sleep_sec=pubmed_sleep_sec,
        )

        result = orchestrator.run(input_path)

        logger.info("PK parameters summary:")
        logger.info("T1/2 values found: %s", result.t_half_values)
        logger.info("Cmax values found: %s", result.cmax_values)
        logger.info("Mean T1/2: %s", result.mean_t_half)
        logger.info("Median T1/2: %s", result.median_t_half)
        logger.info("Mean Cmax: %s", result.mean_cmax)
        logger.info("Median Cmax: %s", result.median_cmax)

        print("Planner output:")
        print(json.dumps(result.planner_output.model_dump(), ensure_ascii=False, indent=2))
        print("\nReviewer output:")
        print(json.dumps(result.reviewer_output.model_dump(), ensure_ascii=False, indent=2))
    except Exception:
        logger.exception("Application failed")
        raise
    finally:
        total_elapsed = time.perf_counter() - t0
        logger.info("Total elapsed | elapsed=%ss", fmt_seconds(total_elapsed))


if __name__ == "__main__":
    main()
