import logging
import time

from Bio import Entrez

from be_system.schemas import PubMedSearchResult


class PubMedSearchAgent:
    def __init__(self, n_articles: int = 5, pubmed_sleep_sec: float = 1.0):
        self.n_articles = n_articles
        self.pubmed_sleep_sec = pubmed_sleep_sec
        self.logger = logging.getLogger("be_system.agents.pubmed_search")

    def run(self, inn: str) -> PubMedSearchResult:
        query = (
            f'"{inn}"[Title/Abstract] AND '
            "(pharmacokinetics OR bioequivalence OR crossover OR variability OR Cmax OR half-life)"
        )

        with Entrez.esearch(
            db="pubmed",
            term=query,
            retmax=self.n_articles,
            sort="relevance",
        ) as handle:
            payload = Entrez.read(handle)
        time.sleep(self.pubmed_sleep_sec)

        pmids = payload.get("IdList", [])
        return PubMedSearchResult(query=query, pmids=pmids)
