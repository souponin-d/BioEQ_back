import logging
import re

from be_system.schemas import AbstractEvaluation, PubMedArticle


class AbstractEvaluatorAgent:
    def __init__(self):
        self.logger = logging.getLogger("be_system.agents.abstract_evaluator")
        self.pk_patterns = [
            re.compile(r"\bt\s*1\s*/\s*2\b", re.IGNORECASE),
            re.compile(r"\bhalf[-\s]?life\b", re.IGNORECASE),
            re.compile(r"\bc\s*max\b", re.IGNORECASE),
            re.compile(r"\bmaximum\s+concentration\b", re.IGNORECASE),
        ]

    def run(self, articles: list[PubMedArticle], pmcids: dict[str, str | None]) -> list[AbstractEvaluation]:
        decisions: list[AbstractEvaluation] = []
        for article in articles:
            has_pmcid = bool(pmcids.get(article.pmid))
            has_pk_signal = self._has_pk_signal(article.abstract)
            candidate = bool(has_pmcid and has_pk_signal)
            decisions.append(AbstractEvaluation(pmid=article.pmid, candidate_fulltext=candidate))
            self.logger.info(
                "AbstractEvaluator decision | pmid=%s | has_pmcid=%s | has_pk_signal=%s | candidate_fulltext=%s",
                article.pmid,
                has_pmcid,
                has_pk_signal,
                candidate,
            )
        return decisions

    def _has_pk_signal(self, text: str) -> bool:
        if not text.strip():
            return False
        return any(pattern.search(text) for pattern in self.pk_patterns)
