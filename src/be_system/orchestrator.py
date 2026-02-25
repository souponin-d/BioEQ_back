import json
import logging
import time
from pathlib import Path

from be_system.agents.abstract_analysis_agent import AbstractAnalysisAgent
from be_system.agents.planner_agent import PlannerAgent
from be_system.agents.pubmed_fetch_agent import PubMedFetchAgent
from be_system.agents.pubmed_search_agent import PubMedSearchAgent
from be_system.agents.reviewer_agent import ReviewerAgent
from be_system.logging_utils import fmt_seconds
from be_system.schemas import OrchestratorResult


class Orchestrator:
    def __init__(
        self,
        planner_agent: PlannerAgent,
        pubmed_search_agent: PubMedSearchAgent,
        pubmed_fetch_agent: PubMedFetchAgent,
        abstract_analysis_agent: AbstractAnalysisAgent,
        reviewer_agent: ReviewerAgent,
    ):
        self.planner_agent = planner_agent
        self.pubmed_search_agent = pubmed_search_agent
        self.pubmed_fetch_agent = pubmed_fetch_agent
        self.abstract_analysis_agent = abstract_analysis_agent
        self.reviewer_agent = reviewer_agent
        self.logger = logging.getLogger("be_system.orchestrator")

    def run(self, user_input_path: str | Path) -> OrchestratorResult:
        user_input = json.loads(Path(user_input_path).read_text(encoding="utf-8"))

        planner_started = time.perf_counter()
        planner_output = self.planner_agent.run(user_input)
        planner_elapsed = time.perf_counter() - planner_started
        self.logger.info("Planner done | elapsed=%ss", fmt_seconds(planner_elapsed))

        inn = str(user_input.get("inn", "")).strip()
        search_result = self.pubmed_search_agent.run(inn)
        self.logger.info("PubMed search done | pmids=%s", search_result.pmids)

        articles = self.pubmed_fetch_agent.run(search_result.pmids)
        self.logger.info("PubMed fetch done | articles=%d", len(articles))

        analysis_started = time.perf_counter()
        pk_analysis = self.abstract_analysis_agent.run(articles)
        analysis_elapsed = time.perf_counter() - analysis_started
        self.logger.info("Abstract analysis done | elapsed=%ss", fmt_seconds(analysis_elapsed))

        t_half_values = [item.value for item in pk_analysis.t_half]
        cmax_values = [item.value for item in pk_analysis.cmax]
        mean_t_half = sum(t_half_values) / len(t_half_values) if t_half_values else None
        mean_cmax = sum(cmax_values) / len(cmax_values) if cmax_values else None

        reviewer_started = time.perf_counter()
        reviewer_output = self.reviewer_agent.run(planner_output)
        reviewer_elapsed = time.perf_counter() - reviewer_started
        self.logger.info("Reviewer done | elapsed=%ss", fmt_seconds(reviewer_elapsed))

        return OrchestratorResult(
            user_input=user_input,
            planner_output=planner_output,
            pubmed_search=search_result,
            pubmed_articles=articles,
            pk_analysis=pk_analysis,
            reviewer_output=reviewer_output,
            t_half_values=t_half_values,
            cmax_values=cmax_values,
            mean_t_half=mean_t_half,
            mean_cmax=mean_cmax,
        )
