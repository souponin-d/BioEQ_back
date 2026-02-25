import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from urllib.request import Request, urlopen

from be_system.schemas import FullTextLink


class PmcPdfLinkAgent:
    def __init__(self, timeout_sec: float = 30.0):
        self.timeout_sec = timeout_sec
        self.logger = logging.getLogger("be_system.agents.pmc_pdf_link")

    def run(self, links: list[FullTextLink]) -> list[FullTextLink]:
        out: list[FullTextLink] = []
        resolved = 0

        for link in links:
            if not link.article_url or not link.pmcid:
                out.append(link)
                continue

            resolved_url = self._resolve_pdf_url(link.article_url, link.pmcid)
            if resolved_url:
                resolved += 1

            out.append(
                link.model_copy(
                    update={
                        "pdf_url_resolved": resolved_url,
                        "pdf_url": resolved_url,
                    }
                )
            )

        missing = len([item for item in out if item.has_pmc]) - resolved
        self.logger.info("PMC pdf link resolve done | resolved=%d | missing=%d", resolved, missing)
        return out

    def _resolve_pdf_url(self, article_url: str, pmcid: str) -> str | None:
        try:
            req = Request(article_url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=self.timeout_sec) as response:
                html = response.read().decode("utf-8", errors="ignore")
        except Exception:
            self.logger.exception("Failed to open PMC article page | pmcid=%s", pmcid)
            return None

        soup = BeautifulSoup(html, "html.parser")
        for anchor in soup.find_all("a", href=True):
            href = str(anchor["href"])
            if ".pdf" not in href.lower():
                continue
            if "/articles/" not in href and not href.lower().startswith("http"):
                continue
            return urljoin(article_url, href)

        return None
