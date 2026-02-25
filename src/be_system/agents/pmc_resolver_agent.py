import logging

from Bio import Entrez

from be_system.schemas import FullTextLink


class PMCResolverAgent:
    def __init__(self):
        self.logger = logging.getLogger("be_system.agents.pmc_resolver")

    def run(self, pmids: list[str]) -> list[FullTextLink]:
        if not pmids:
            return []

        pmid_to_uid = {pmid: None for pmid in pmids}
        with Entrez.elink(dbfrom="pubmed", db="pmc", id=pmids) as handle:
            payload = Entrez.read(handle)

        for linkset in payload:
            id_list = linkset.get("IdList", [])
            pmid = str(id_list[0]) if id_list else ""
            uid: str | None = None
            for db_block in linkset.get("LinkSetDb", []):
                links = db_block.get("Link", [])
                if links:
                    uid = str(links[0].get("Id", ""))
                    break
            if pmid in pmid_to_uid:
                pmid_to_uid[pmid] = uid

        uid_to_pmcid = self._resolve_pmcids([uid for uid in pmid_to_uid.values() if uid])

        results: list[FullTextLink] = []
        for pmid in pmids:
            uid = pmid_to_uid.get(pmid)
            pmcid = uid_to_pmcid.get(uid) if uid else None
            article_url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/" if pmcid else None
            has_pmc = pmcid is not None
            results.append(
                FullTextLink(
                    pmid=pmid,
                    pmcid=pmcid,
                    has_pmc=has_pmc,
                    pdf_url=None,
                    article_url=article_url,
                    pdf_page_url=article_url,
                    pdf_url_resolved=None,
                    source="pmc" if has_pmc else "none",
                )
            )

        return results

    def _resolve_pmcids(self, uids: list[str]) -> dict[str, str]:
        if not uids:
            return {}

        out: dict[str, str] = {}
        with Entrez.esummary(db="pmc", id=",".join(uids)) as handle:
            payload = Entrez.read(handle)

        for docsum in payload:
            uid = str(docsum.get("Id", ""))
            pmcid = None
            article_ids = docsum.get("ArticleIds", {})
            if isinstance(article_ids, dict):
                for value in article_ids.values():
                    text = str(value)
                    if text.upper().startswith("PMC"):
                        pmcid = text.upper()
                        break
            if not pmcid:
                pmcid = str(docsum.get("AccessionVersion", "")).upper()
                if not pmcid.startswith("PMC"):
                    pmcid = None
            if uid and pmcid:
                out[uid] = pmcid

        return out
