import json
import logging
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from be_system.agents.abstract_evaluator_agent import AbstractEvaluatorAgent
from be_system.agents.pk_extractor_agent import PKExtractorAgent
from be_system.agents.planner_agent import PlannerAgent
from be_system.agents.pmc_resolver_agent import PMCResolverAgent
from be_system.agents.pubmed_fetch_agent import PubMedFetchAgent
from be_system.agents.pubmed_search_agent import PubMedSearchAgent
from be_system.agents.pdf_downloader_agent import PdfDownloaderAgent
from be_system.agents.pdf_parser_agent import PdfParserAgent
from be_system.agents.retrieval_agent import RetrievalAgent
from be_system.agents.reviewer_agent import ReviewerAgent
from be_system.agents.xml_downloader_agent import XmlDownloaderAgent
from be_system.agents.xml_parser_agent import XmlParserAgent
from be_system.logging_utils import fmt_seconds
from be_system.schemas import EvidenceItem, FullTextLink, OrchestratorResult, PdfChunk, XmlChunk


class Orchestrator:
    def __init__(
        self,
        planner_agent: PlannerAgent,
        pubmed_search_agent: PubMedSearchAgent,
        pubmed_fetch_agent: PubMedFetchAgent,
        abstract_evaluator_agent: AbstractEvaluatorAgent,
        pmc_resolver_agent: PMCResolverAgent,
        pdf_downloader_agent: PdfDownloaderAgent,
        xml_downloader_agent: XmlDownloaderAgent,
        pdf_parser_agent: PdfParserAgent,
        xml_parser_agent: XmlParserAgent,
        retrieval_agent: RetrievalAgent,
        pk_extractor_agent: PKExtractorAgent,
        reviewer_agent: ReviewerAgent,
        pubmed_cycles: int = 2,
        pubmed_sleep_sec: float = 1.0,
    ):
        self.planner_agent = planner_agent
        self.pubmed_search_agent = pubmed_search_agent
        self.pubmed_fetch_agent = pubmed_fetch_agent
        self.abstract_evaluator_agent = abstract_evaluator_agent
        self.pmc_resolver_agent = pmc_resolver_agent
        self.pdf_downloader_agent = pdf_downloader_agent
        self.xml_downloader_agent = xml_downloader_agent
        self.pdf_parser_agent = pdf_parser_agent
        self.xml_parser_agent = xml_parser_agent
        self.retrieval_agent = retrieval_agent
        self.pk_extractor_agent = pk_extractor_agent
        self.reviewer_agent = reviewer_agent
        self.pubmed_cycles = max(1, pubmed_cycles)
        self.pubmed_sleep_sec = pubmed_sleep_sec
        self.logger = logging.getLogger("be_system.orchestrator")

    def run(self, user_input_path: str | Path) -> OrchestratorResult:
        user_input = json.loads(Path(user_input_path).read_text(encoding="utf-8"))

        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = Path("data/runs") / run_id
        errors_dir = run_dir / "errors"
        run_dir.mkdir(parents=True, exist_ok=True)

        planner_started = time.perf_counter()
        planner_output = self.planner_agent.run(user_input)
        self.logger.info("Planner done | elapsed=%ss", fmt_seconds(time.perf_counter() - planner_started))

        inn = str(user_input.get("inn", "")).strip()
        search_result = None
        articles = []
        fulltext_links: list[FullTextLink] = []

        for cycle in range(self.pubmed_cycles):
            self.logger.info("Cycle start | cycle=%d/%d", cycle + 1, self.pubmed_cycles)
            self.logger.info("Sleep before PubMed search | seconds=%s", self.pubmed_sleep_sec)
            time.sleep(self.pubmed_sleep_sec)

            search_result = self.pubmed_search_agent.run(inn)
            self.logger.info("PubMed pmids found | cycle=%d | count=%d", cycle + 1, len(search_result.pmids))

            articles = self.pubmed_fetch_agent.run(search_result.pmids)
            self.logger.info("PubMed abstracts fetched | cycle=%d | count=%d", cycle + 1, len(articles))

            pmc_resolved = self.pmc_resolver_agent.run(search_result.pmids)
            pmid_to_pmcid = {item.pmid: item.pmcid for item in pmc_resolved}
            decisions = self.abstract_evaluator_agent.run(articles, pmid_to_pmcid)
            candidate_pmids = {item.pmid for item in decisions if item.candidate_fulltext}

            self.logger.info(
                "AbstractEvaluator decisions | cycle=%d | candidates=%d",
                cycle + 1,
                len(candidate_pmids),
            )

            if candidate_pmids:
                fulltext_links = [item for item in pmc_resolved if item.pmid in candidate_pmids]
                if any(item.has_fulltext_pdf or item.has_fulltext_xml for item in fulltext_links):
                    break

        if not fulltext_links or not any(item.has_fulltext_pdf or item.has_fulltext_xml for item in fulltext_links):
            self.logger.info(
                "No full text available after all retries. Full text not available in OA subset; proceeding with abstracts only."
            )

        for link in fulltext_links:
            self.logger.info(
                "Full text availability | pmid=%s | pmcid=%s | pdf=%s | xml=%s",
                link.pmid,
                link.pmcid,
                link.has_fulltext_pdf,
                link.has_fulltext_xml,
            )

        pmid_to_link = {item.pmid: item for item in fulltext_links}

        inn_folder_prefix = inn or "unknown_inn"
        raw_output_dir = Path("data/raw_pmc") / f"{inn_folder_prefix}_{run_id}"

        pdf_downloads = self.pdf_downloader_agent.run(fulltext_links, output_dir=raw_output_dir / "pdf")
        xml_downloads = self.xml_downloader_agent.run(fulltext_links, output_dir=Path("data/raw_pmc_xml") / f"{inn_folder_prefix}_{run_id}")
        self.logger.info(
            "Download summary | pdf_valid=%d/%d | xml_valid=%d/%d",
            len([f for f in pdf_downloads if f.is_valid_pdf]),
            len(pdf_downloads),
            len([f for f in xml_downloads if f.is_valid_pdf]),
            len(xml_downloads),
        )
        (run_dir / "pdf_manifest.json").write_text(
            json.dumps([item.model_dump() for item in pdf_downloads], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (run_dir / "xml_manifest.json").write_text(
            json.dumps([item.model_dump() for item in xml_downloads], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        pdf_chunks = self.pdf_parser_agent.run([item for item in pdf_downloads if item.is_valid_pdf])
        xml_chunks = self.xml_parser_agent.run([item for item in xml_downloads if item.is_valid_pdf])
        self._save_chunks(run_dir / "pdf_chunks.jsonl", pdf_chunks)
        self._save_xml_chunks(run_dir / "xml_chunks.jsonl", xml_chunks)

        pdf_by_doc: dict[str, list[PdfChunk]] = {}
        for chunk in pdf_chunks:
            pdf_by_doc.setdefault(chunk.doc_id, []).append(chunk)

        xml_by_doc: dict[str, list[XmlChunk]] = {}
        for chunk in xml_chunks:
            xml_by_doc.setdefault(chunk.doc_id, []).append(chunk)

        all_evidence: list[EvidenceItem] = []
        extraction_started = time.perf_counter()

        for article in articles:
            link = pmid_to_link.get(article.pmid)
            pmcid = link.pmcid if link else None
            source_type = "abstract"
            fragments = [{"page": None, "section": None, "text": article.abstract}]

            if pmcid and pmcid in xml_by_doc:
                retrieval = self.retrieval_agent.run_xml(article.pmid, pmcid, xml_by_doc[pmcid])
                source_type = "xml"
                fragments = [
                    {
                        "param_hint": selection.param,
                        "page": None,
                        "section": chunk.section,
                        "chunk_id": chunk.chunk_id,
                        "text": chunk.text,
                    }
                    for selection in retrieval.selected_chunks
                    for chunk in selection.chunks
                ]
            elif pmcid and pmcid in pdf_by_doc:
                retrieval = self.retrieval_agent.run(article.pmid, pmcid, pdf_by_doc[pmcid])
                source_type = "pdf"
                fragments = [
                    {
                        "param_hint": selection.param,
                        "page": chunk.page,
                        "section": None,
                        "chunk_id": chunk.chunk_id,
                        "text": chunk.text,
                    }
                    for selection in retrieval.selected_chunks
                    for chunk in selection.chunks
                ]

            result = self.pk_extractor_agent.run(
                pmid=article.pmid,
                pmcid=pmcid,
                source_type=source_type,
                fragments=fragments,
                errors_dir=errors_dir,
                article_tag=f"{article.pmid}_{source_type}",
            )
            all_evidence.extend(result.evidence)

        self.logger.info(
            "PK extraction summary | evidence_count=%d | elapsed=%ss",
            len(all_evidence),
            fmt_seconds(time.perf_counter() - extraction_started),
        )

        (run_dir / "evidence.json").write_text(
            json.dumps([item.model_dump() for item in all_evidence], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        summary = self._summarize(all_evidence)
        self._log_summary(summary, all_evidence)

        reviewer_started = time.perf_counter()
        reviewer_output = self.reviewer_agent.run(planner_output)
        self.logger.info("Reviewer done | elapsed=%ss", fmt_seconds(time.perf_counter() - reviewer_started))

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

    def _save_xml_chunks(self, path: Path, chunks: list[XmlChunk]) -> None:
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
                "%s: %s %s | pmid=%s | pmcid=%s | src=%s | page=%s | section=%s",
                label,
                item.value,
                item.unit or "",
                item.pmid,
                item.pmcid,
                item.source_type,
                item.page,
                item.section,
            )
