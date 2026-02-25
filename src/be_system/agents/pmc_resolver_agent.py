import logging
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from be_system.schemas import FullTextLink

OA_API_BASE = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi"
BIOC_API_TEMPLATE = "https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_xml/{pmcid}/unicode"


class PMCResolverAgent:
    def __init__(self, pubmed_sleep_sec: float = 1.0, timeout_sec: float = 30.0):
        self.pubmed_sleep_sec = pubmed_sleep_sec
        self.timeout_sec = timeout_sec
        self.logger = logging.getLogger("be_system.agents.pmc_resolver")

    def run(self, pmids: list[str]) -> list[FullTextLink]:
        from Bio import Entrez

        if not pmids:
            return []

        pmid_to_uid = {pmid: None for pmid in pmids}
        with Entrez.elink(dbfrom="pubmed", db="pmc", id=pmids) as handle:
            payload = Entrez.read(handle)

        time.sleep(self.pubmed_sleep_sec)

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
            oa_record = (
                self._resolve_oa_links(pmcid) if pmcid else {"pdf": None, "xml": None, "has_oa": False}
            )
            pdf_url = oa_record.get("pdf")
            xml_url = oa_record.get("xml")
            has_oa = bool(oa_record.get("has_oa"))
            if not xml_url and has_oa and pmcid:
                xml_url = BIOC_API_TEMPLATE.format(pmcid=pmcid)
            results.append(
                FullTextLink(
                    pmid=pmid,
                    pmcid=pmcid,
                    has_pmc=has_pmc,
                    has_fulltext_pdf=pdf_url is not None,
                    has_fulltext_xml=xml_url is not None,
                    pdf_url=pdf_url,
                    xml_url=xml_url,
                    article_url=article_url,
                    pdf_page_url=article_url,
                    pdf_url_resolved=pdf_url,
                    xml_url_resolved=xml_url,
                    source="pmc" if has_pmc else "none",
                )
            )

        fulltext_count = len([item for item in results if item.has_fulltext_pdf or item.has_fulltext_xml])
        pdf_count = len([item for item in results if item.has_fulltext_pdf])
        xml_count = len([item for item in results if item.has_fulltext_xml])
        self.logger.info(
            "PMC OA resolve summary | total=%d | fulltext_candidates=%d | pdf=%d | xml=%d",
            len(results),
            fulltext_count,
            pdf_count,
            xml_count,
        )
        return results

    def _resolve_pmcids(self, uids: list[str]) -> dict[str, str]:
        from Bio import Entrez

        if not uids:
            return {}

        out: dict[str, str] = {}
        with Entrez.esummary(db="pmc", id=",".join(uids)) as handle:
            payload = Entrez.read(handle)

        time.sleep(self.pubmed_sleep_sec)

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

    def _resolve_oa_links(self, pmcid: str) -> dict[str, str | bool | None]:
        query = urlencode({"id": pmcid})
        url = f"{OA_API_BASE}?{query}"

        try:
            req = Request(url, headers={"User-Agent": "be_system/1.0"})
            with urlopen(req, timeout=self.timeout_sec) as response:
                raw_xml = response.read().decode("utf-8", errors="ignore")
        except Exception:
            self.logger.exception("OA API request failed | pmcid=%s", pmcid)
            return {"pdf": None, "xml": None, "has_oa": False}

        self.logger.debug("Raw OA Web API XML | pmcid=%s | xml=%s", pmcid, raw_xml)

        return self._parse_oa_xml(raw_xml=raw_xml, pmcid=pmcid)

    def _parse_oa_xml(self, raw_xml: str, pmcid: str) -> dict[str, str | bool | None]:

        try:
            root = ET.fromstring(raw_xml)
        except ET.ParseError:
            self.logger.exception("OA API XML parse failed | pmcid=%s", pmcid)
            return {"pdf": None, "xml": None, "has_oa": False}

        pdf_url = None
        xml_url = None
        has_oa = False
        discovered_links: list[tuple[str, str]] = []

        for record in root.findall(".//record"):
            has_oa = True
            for link in record.findall(".//link"):
                fmt = (link.get("format") or "").lower()
                href = link.get("href")
                if not href:
                    continue
                discovered_links.append((fmt, href))
                if fmt == "pdf" and not pdf_url:
                    pdf_url = href
                if fmt in {"xml", "pmc_bioc_xml", "biocxml", "bioc"} and not xml_url:
                    if "bioc" in href.lower() or href.lower().endswith(".xml"):
                        xml_url = href

        self.logger.debug("OA API links | pmcid=%s | links=%s", pmcid, discovered_links)

        return {"pdf": pdf_url, "xml": xml_url, "has_oa": has_oa}
