import logging

from Bio import Entrez

from be_system.schemas import PubMedArticle


class PubMedFetchAgent:
    def __init__(self):
        self.logger = logging.getLogger("be_system.agents.pubmed_fetch")

    def run(self, pmids: list[str]) -> list[PubMedArticle]:
        if not pmids:
            return []

        with Entrez.efetch(
            db="pubmed",
            id=",".join(pmids),
            rettype="abstract",
            retmode="xml",
        ) as handle:
            payload = Entrez.read(handle)

        articles: list[PubMedArticle] = []
        for item in payload.get("PubmedArticle", []):
            citation = item.get("MedlineCitation", {})
            article = citation.get("Article", {})
            journal = article.get("Journal", {})
            journal_issue = journal.get("JournalIssue", {})
            pub_date = journal_issue.get("PubDate", {})

            abstract = ""
            abstract_data = article.get("Abstract", {}).get("AbstractText", [])
            if abstract_data:
                abstract = " ".join(str(chunk) for chunk in abstract_data)

            pmid = str(citation.get("PMID", ""))
            title = str(article.get("ArticleTitle", ""))
            journal_title = str(journal.get("Title", ""))
            year = str(pub_date.get("Year", ""))

            articles.append(
                PubMedArticle(
                    pmid=pmid,
                    title=title,
                    journal=journal_title,
                    year=year,
                    abstract=abstract,
                )
            )

        return articles
