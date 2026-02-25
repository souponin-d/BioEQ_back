import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from Bio import Entrez

from be_system.schemas import FullTextLink


class PMCResolverAgent:
    def __init__(self, timeout_sec: float = 10.0):
        self.timeout_sec = timeout_sec
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
            pdf_url = None
            if pmcid:
                candidate = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/pdf/"
                if self._is_pdf_url_available(candidate):
                    pdf_url = candidate

            has_pmc = pmcid is not None
            results.append(
                FullTextLink(
                    pmid=pmid,
                    pmcid=pmcid,
                    has_pmc=has_pmc,
                    pdf_url=pdf_url,
                    source="pmc" if pdf_url else "none",
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

    def _is_pdf_url_available(self, url: str) -> bool:
        methods = ["HEAD", "GET"]
        for method in methods:
            try:
                req = Request(url=url, method=method)
                with urlopen(req, timeout=self.timeout_sec) as response:
                    status = getattr(response, "status", 200)
                    if status == 200:
                        return True
            except HTTPError as exc:
                if exc.code in (403, 404):
                    return False
                self.logger.debug("PDF URL check error %s for %s", exc.code, url)
            except URLError:
                self.logger.debug("Network error while checking PDF URL: %s", url)
        return False
