import logging

from Bio import Entrez

from be_system.schemas import PubMedSearchResult


class PubMedSearchAgent:
    def __init__(self, n_articles: int = 5):
        self.n_articles = n_articles
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

        pmids = payload.get("IdList", [])
        return PubMedSearchResult(query=query, pmids=pmids)
