import json
import logging
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from be_system.agents.pk_extractor_agent import PKExtractorAgent
from be_system.agents.planner_agent import PlannerAgent
from be_system.agents.pmc_resolver_agent import PMCResolverAgent
from be_system.agents.pubmed_fetch_agent import PubMedFetchAgent
from be_system.agents.pubmed_search_agent import PubMedSearchAgent
from be_system.agents.pdf_downloader_agent import PdfDownloaderAgent
from be_system.agents.pdf_parser_agent import PdfParserAgent
from be_system.agents.retrieval_agent import RetrievalAgent
from be_system.agents.reviewer_agent import ReviewerAgent
from be_system.logging_utils import fmt_seconds
from be_system.schemas import (
    EvidenceItem,
    FullTextLink,
    OrchestratorResult,
    PdfChunk,
)


class Orchestrator:
    def __init__(
        self,
        planner_agent: PlannerAgent,
        pubmed_search_agent: PubMedSearchAgent,
        pubmed_fetch_agent: PubMedFetchAgent,
        pmc_resolver_agent: PMCResolverAgent,
        pdf_downloader_agent: PdfDownloaderAgent,
        pdf_parser_agent: PdfParserAgent,
        retrieval_agent: RetrievalAgent,
        pk_extractor_agent: PKExtractorAgent,
        reviewer_agent: ReviewerAgent,
    ):
        self.planner_agent = planner_agent
        self.pubmed_search_agent = pubmed_search_agent
        self.pubmed_fetch_agent = pubmed_fetch_agent
        self.pmc_resolver_agent = pmc_resolver_agent
        self.pdf_downloader_agent = pdf_downloader_agent
        self.pdf_parser_agent = pdf_parser_agent
        self.retrieval_agent = retrieval_agent
        self.pk_extractor_agent = pk_extractor_agent
        self.reviewer_agent = reviewer_agent
        self.logger = logging.getLogger("be_system.orchestrator")

    def run(self, user_input_path: str | Path) -> OrchestratorResult:
        user_input = json.loads(Path(user_input_path).read_text(encoding="utf-8"))

        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = Path("data/runs") / run_id
        errors_dir = run_dir / "errors"
        run_dir.mkdir(parents=True, exist_ok=True)

        planner_started = time.perf_counter()
        planner_output = self.planner_agent.run(user_input)
        planner_elapsed = time.perf_counter() - planner_started
        self.logger.info("Planner done | elapsed=%ss", fmt_seconds(planner_elapsed))

        inn = str(user_input.get("inn", "")).strip()
        search_result = self.pubmed_search_agent.run(inn)
        self.logger.info("PubMed search done | pmids=%s", search_result.pmids)

        articles = self.pubmed_fetch_agent.run(search_result.pmids)
        self.logger.info("PubMed fetch done | articles=%d", len(articles))

        fulltext_links = self.pmc_resolver_agent.run(search_result.pmids)
        pmid_to_link = {item.pmid: item for item in fulltext_links}
        links_with_pdf = [item for item in fulltext_links if item.pdf_url]
        self.logger.info(
            "PMC resolve done | with_pdf=%d | fallback_abstract=%d",
            len(links_with_pdf),
            len(articles) - len(links_with_pdf),
        )

        download_started = time.perf_counter()
        downloaded_files = self.pdf_downloader_agent.run(links_with_pdf)
        download_elapsed = time.perf_counter() - download_started
        self.logger.info(
            "PDF download done | downloaded=%d | elapsed=%ss",
            len(downloaded_files),
            fmt_seconds(download_elapsed),
        )
        (run_dir / "pdf_manifest.json").write_text(
            json.dumps([item.model_dump() for item in downloaded_files], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        parse_started = time.perf_counter()
        chunks = self.pdf_parser_agent.run(downloaded_files)
        parse_elapsed = time.perf_counter() - parse_started
        self.logger.info(
            "PDF parse done | chunks_total=%d | elapsed=%ss",
            len(chunks),
            fmt_seconds(parse_elapsed),
        )
        self._save_chunks(run_dir / "pdf_chunks.jsonl", chunks)

        chunks_by_doc: dict[str, list[PdfChunk]] = {}
        for chunk in chunks:
            chunks_by_doc.setdefault(chunk.doc_id, []).append(chunk)

        extraction_started = time.perf_counter()
        all_evidence: list[EvidenceItem] = []

        for article in articles:
            link: FullTextLink | None = pmid_to_link.get(article.pmid)
            pmcid = link.pmcid if link else None
            source_is_pdf = bool(link and link.pdf_url and pmcid in chunks_by_doc)

            if source_is_pdf and pmcid:
                retrieval = self.retrieval_agent.run(
                    pmid=article.pmid,
                    pmcid=pmcid,
                    chunks=chunks_by_doc.get(pmcid, []),
                )
                fragments = []
                for selection in retrieval.selected_chunks:
                    for chunk in selection.chunks:
                        fragments.append(
                            {
                                "param_hint": selection.param,
                                "page": chunk.page,
                                "chunk_id": chunk.chunk_id,
                                "text": chunk.text,
                            }
                        )

                result = self.pk_extractor_agent.run(
                    pmid=article.pmid,
                    pmcid=pmcid,
                    source_type="pdf",
                    fragments=fragments,
                    errors_dir=errors_dir,
                    article_tag=f"{article.pmid}_pdf",
                )
            else:
                fragments = [{"page": None, "text": article.abstract}]
                result = self.pk_extractor_agent.run(
                    pmid=article.pmid,
                    pmcid=pmcid,
                    source_type="abstract",
                    fragments=fragments,
                    errors_dir=errors_dir,
                    article_tag=f"{article.pmid}_abstract",
                )
            all_evidence.extend(result.evidence)

        extraction_elapsed = time.perf_counter() - extraction_started
        self.logger.info(
            "PK extraction done | evidence_count=%d | elapsed=%ss",
            len(all_evidence),
            fmt_seconds(extraction_elapsed),
        )

        (run_dir / "evidence.json").write_text(
            json.dumps([item.model_dump() for item in all_evidence], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        summary = self._summarize(all_evidence)
        self._log_summary(summary, all_evidence)

        reviewer_started = time.perf_counter()
        reviewer_output = self.reviewer_agent.run(planner_output)
        reviewer_elapsed = time.perf_counter() - reviewer_started
        self.logger.info("Reviewer done | elapsed=%ss", fmt_seconds(reviewer_elapsed))

        return OrchestratorResult(
            user_input=user_input,
            planner_output=planner_output,
            pubmed_search=search_result,
            pubmed_articles=articles,
            fulltext_links=fulltext_links,
            evidence=all_evidence,
            reviewer_output=reviewer_output,
            t_half_values=summary["t_half_values"],
            cmax_values=summary["cmax_values"],
            mean_t_half=summary["mean_t_half"],
            median_t_half=summary["median_t_half"],
            mean_cmax=summary["mean_cmax"],
            median_cmax=summary["median_cmax"],
        )

    def _save_chunks(self, path: Path, chunks: list[PdfChunk]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for chunk in chunks:
                f.write(json.dumps(chunk.model_dump(), ensure_ascii=False) + "\n")

    def _summarize(self, evidence: list[EvidenceItem]) -> dict:
        t_half_items = [item for item in evidence if item.param == "t_half"]
        cmax_items = [item for item in evidence if item.param == "cmax"]

        return {
            "t_half_values": [item.value for item in t_half_items],
            "cmax_values": [item.value for item in cmax_items],
            "mean_t_half": self._compute_mean_if_compatible(t_half_items),
            "median_t_half": self._compute_median_if_compatible(t_half_items),
            "mean_cmax": self._compute_mean_if_compatible(cmax_items),
            "median_cmax": self._compute_median_if_compatible(cmax_items),
        }

    def _compute_mean_if_compatible(self, items: list[EvidenceItem]) -> float | None:
        if not items or not self._units_compatible(items):
            return None
        return statistics.fmean(item.value for item in items)

    def _compute_median_if_compatible(self, items: list[EvidenceItem]) -> float | None:
        if not items or not self._units_compatible(items):
            return None
        return statistics.median(item.value for item in items)

    def _units_compatible(self, items: list[EvidenceItem]) -> bool:
        normalized_units = {
            (item.unit or "").strip().lower() for item in items if (item.unit or "").strip()
        }
        return len(normalized_units) == 1 and len(items) > 0

    def _log_summary(self, summary: dict, evidence: list[EvidenceItem]) -> None:
        self.logger.info("PK summary:")
        self._log_param("t_half", evidence)
        self._log_param("cmax", evidence)

        t_half_note = (
            f"mean={summary['mean_t_half']:.4f}, median={summary['median_t_half']:.4f}"
            if summary["mean_t_half"] is not None and summary["median_t_half"] is not None
            else "not computed"
        )
        cmax_note = (
            f"mean={summary['mean_cmax']:.4f}, median={summary['median_cmax']:.4f}"
            if summary["mean_cmax"] is not None and summary["median_cmax"] is not None
            else "not computed"
        )
        self.logger.info("T1/2 aggregates: %s", t_half_note)
        self.logger.info("Cmax aggregates: %s", cmax_note)

    def _log_param(self, param: str, evidence: list[EvidenceItem]) -> None:
        label = "T1/2" if param == "t_half" else "Cmax"
        items = [item for item in evidence if item.param == param]
        if not items:
            self.logger.info("%s: none", label)
            return
        for item in items:
            self.logger.info(
                "%s: %s %s | pmid=%s | pmcid=%s | src=%s | page=%s",
                label,
                item.value,
                item.unit or "",
                item.pmid,
                item.pmcid,
                item.source_type,
                item.page,
            )
