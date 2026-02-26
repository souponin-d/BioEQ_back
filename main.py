import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
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
TEST_MODE = True
TEST_ITERATIONS_PER_DRUG = 5


def _safe_error_metrics(predicted: float | None, ground_truth: float | None) -> tuple[float | None, float | None]:
    if predicted is None or ground_truth is None:
        return None, None
    absolute_error = abs(predicted - ground_truth)
    if ground_truth == 0:
        return absolute_error, None
    return absolute_error, absolute_error / abs(ground_truth)


def _mean_nullable(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return statistics.fmean(present)


def _std_nullable(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    if len(present) == 1:
        return 0.0
    return statistics.pstdev(present)


def _build_test_fragments(drug_row: dict) -> list[dict]:
    drug = drug_row["drug"]
    cmax = drug_row["Cmax"]
    t_half = drug_row["T_half"]
    return [
        {
            "param_hint": "cmax",
            "page": None,
            "section": "results",
            "chunk_id": f"{drug}_cmax_1",
            "text": f"For {drug}, the observed Cmax was {cmax} ng/mL.",
        },
        {
            "param_hint": "t_half",
            "page": None,
            "section": "results",
            "chunk_id": f"{drug}_thalf_1",
            "text": f"The elimination half-life (T1/2) was {t_half} h in healthy volunteers.",
        },
    ]


def _run_test_mode(
    logger,
    planner_model: str,
    pk_model: str,
    reviewer_model: str,
    planner_llm: LLMClient,
    pk_llm: LLMClient,
    reviewer_llm: LLMClient,
) -> None:
    test_dataset_path = Path("configs/test_dataset.json")
    test_report_path = Path("reports/test_report.json")
    test_report_path.parent.mkdir(parents=True, exist_ok=True)

    dataset = json.loads(test_dataset_path.read_text(encoding="utf-8"))
    planner_agent = PlannerAgent(planner_llm)
    pk_extractor_agent = PKExtractorAgent(pk_llm)
    reviewer_agent = ReviewerAgent(reviewer_llm)
    base_user_input = json.loads(Path("configs/user_input.json").read_text(encoding="utf-8"))
    errors_dir = Path("data/runs/test_mode/errors")
    errors_dir.mkdir(parents=True, exist_ok=True)

    report: dict = {
        "meta": {
            "iterations_per_drug": TEST_ITERATIONS_PER_DRUG,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model_config": {
                "planner_model": planner_model,
                "pk_model": pk_model,
                "reviewer_model": reviewer_model,
            },
        },
        "drugs": [],
    }

    all_rel_errors_t_half: list[float | None] = []
    all_rel_errors_cmax: list[float | None] = []
    found_t_half = 0
    found_cmax = 0
    total_iterations = len(dataset) * TEST_ITERATIONS_PER_DRUG

    for drug_row in dataset:
        drug = drug_row["drug"]
        gt_t_half = drug_row["T_half"]
        gt_cmax = drug_row["Cmax"]
        logger.info("Test mode | drug start | drug=%s", drug)

        user_input = dict(base_user_input)
        user_input["inn"] = drug

        planner_output = planner_agent.run(user_input)
        reviewer_agent.run(planner_output)

        drug_runs = []
        for iteration in range(1, TEST_ITERATIONS_PER_DRUG + 1):
            logger.info("Test mode | iteration start | drug=%s | iteration=%d", drug, iteration)
            fragments = _build_test_fragments(drug_row)
            extraction = pk_extractor_agent.run(
                pmid=f"test-{drug.lower().replace(' ', '-')}",
                pmcid=None,
                source_type="abstract",
                fragments=fragments,
                errors_dir=errors_dir,
                article_tag=f"{drug.lower().replace(' ', '_')}_{iteration}",
            )

            t_half_values = [item.value for item in extraction.evidence if item.param == "t_half"]
            cmax_values = [item.value for item in extraction.evidence if item.param == "cmax"]
            predicted_mean_t_half = statistics.fmean(t_half_values) if t_half_values else None
            predicted_mean_cmax = statistics.fmean(cmax_values) if cmax_values else None

            if predicted_mean_t_half is not None:
                found_t_half += 1
            if predicted_mean_cmax is not None:
                found_cmax += 1

            abs_t_half, rel_t_half = _safe_error_metrics(predicted_mean_t_half, gt_t_half)
            abs_cmax, rel_cmax = _safe_error_metrics(predicted_mean_cmax, gt_cmax)
            all_rel_errors_t_half.append(rel_t_half)
            all_rel_errors_cmax.append(rel_cmax)

            run_result = {
                "iteration": iteration,
                "found_t_half_values": t_half_values,
                "found_cmax_values": cmax_values,
                "predicted_mean_T_half": predicted_mean_t_half,
                "predicted_mean_Cmax": predicted_mean_cmax,
                "absolute_error_T_half": abs_t_half,
                "relative_error_T_half": rel_t_half,
                "absolute_error_Cmax": abs_cmax,
                "relative_error_Cmax": rel_cmax,
            }
            drug_runs.append(run_result)
            logger.info("Test mode | iteration end | drug=%s | iteration=%d", drug, iteration)

        report["drugs"].append(
            {
                "drug": drug,
                "ground_truth": {"T_half": gt_t_half, "Cmax": gt_cmax},
                "runs": drug_runs,
                "summary": {
                    "mean_relative_error_T_half": _mean_nullable(
                        [run["relative_error_T_half"] for run in drug_runs]
                    ),
                    "mean_relative_error_Cmax": _mean_nullable(
                        [run["relative_error_Cmax"] for run in drug_runs]
                    ),
                    "std_relative_error_T_half": _std_nullable(
                        [run["relative_error_T_half"] for run in drug_runs]
                    ),
                    "std_relative_error_Cmax": _std_nullable(
                        [run["relative_error_Cmax"] for run in drug_runs]
                    ),
                },
            }
        )

    mean_rel_t_half = _mean_nullable(all_rel_errors_t_half)
    mean_rel_cmax = _mean_nullable(all_rel_errors_cmax)
    coverage_t_half = found_t_half / total_iterations if total_iterations else 0.0
    coverage_cmax = found_cmax / total_iterations if total_iterations else 0.0
    coverage_rate = (found_t_half + found_cmax) / (2 * total_iterations) if total_iterations else 0.0

    report["aggregate"] = {
        "mean_relative_error_T_half": mean_rel_t_half,
        "mean_relative_error_Cmax": mean_rel_cmax,
        "coverage_rate_T_half": coverage_t_half,
        "coverage_rate_Cmax": coverage_cmax,
        "coverage_rate_overall": coverage_rate,
    }
    test_report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("Test mode aggregate | mean relative error T1/2=%s", mean_rel_t_half)
    logger.info("Test mode aggregate | mean relative error Cmax=%s", mean_rel_cmax)
    logger.info("Test mode aggregate | coverage rate=%s", coverage_rate)
    logger.info("Test report saved | path=%s", test_report_path)


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
        pk_model = os.getenv("PK_MODEL", os.getenv("ABSTRACT_ANALYSIS_MODEL", os.getenv("VLLM_MODEL", DEFAULT_MODEL)))

        logger.info(
            "Selected models | planner=%s | abstract_analysis=%s | reviewer=%s",
            planner_model,
            pk_model,
            reviewer_model,
        )

        planner_llm = LLMClient(base_url=base_url, api_key=api_key, model_name=planner_model)
        reviewer_llm = LLMClient(base_url=base_url, api_key=api_key, model_name=reviewer_model)
        pk_llm = LLMClient(base_url=base_url, api_key=api_key, model_name=pk_model)

        if TEST_MODE:
            _run_test_mode(
                logger=logger,
                planner_model=planner_model,
                pk_model=pk_model,
                reviewer_model=reviewer_model,
                planner_llm=planner_llm,
                pk_llm=pk_llm,
                reviewer_llm=reviewer_llm,
            )
            return

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
            pk_extractor_agent=PKExtractorAgent(pk_llm),
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
