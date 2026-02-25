import logging

from be_system.schemas import (
    PdfChunk,
    RetrievalResult,
    RetrievalSelection,
    XmlChunk,
    XmlRetrievalResult,
    XmlRetrievalSelection,
)


class RetrievalAgent:
    def __init__(self, top_k: int = 6):
        self.top_k = top_k
        self.logger = logging.getLogger("be_system.agents.retrieval")
        self.keywords = {
            "t_half": [
                "t1/2",
                "half-life",
                "half life",
                "terminal half life",
                "elimination half-life",
                "elimination half life",
                "t½",
            ],
            "cmax": ["cmax", "maximum concentration"],
        }

    def run(self, pmid: str, pmcid: str, chunks: list[PdfChunk]) -> RetrievalResult:
        selections: list[RetrievalSelection] = []
        for param in ("t_half", "cmax"):
            selected = self._top_chunks(param, chunks)
            for chunk in selected:
                self.logger.debug(
                    "Selected chunk | pmid=%s | pmcid=%s | param=%s | page=%d | text=%s",
                    pmid,
                    pmcid,
                    param,
                    chunk.page,
                    chunk.text[:200],
                )
            selections.append(RetrievalSelection(param=param, chunks=selected))

        return RetrievalResult(pmid=pmid, pmcid=pmcid, selected_chunks=selections)

    def run_xml(self, pmid: str, pmcid: str, chunks: list[XmlChunk]) -> XmlRetrievalResult:
        selections: list[XmlRetrievalSelection] = []
        for param in ("t_half", "cmax"):
            selected = self._top_chunks(param, chunks)
            selections.append(XmlRetrievalSelection(param=param, chunks=selected))

        return XmlRetrievalResult(pmid=pmid, pmcid=pmcid, selected_chunks=selections)

    def _top_chunks(self, param: str, chunks: list[PdfChunk | XmlChunk]) -> list[PdfChunk | XmlChunk]:
        keys = self.keywords[param]
        scored: list[tuple[int, int, PdfChunk | XmlChunk]] = []
        for idx, chunk in enumerate(chunks):
            lowered = chunk.text.lower()
            score = 0
            for key in keys:
                score += lowered.count(key.lower())
            if score > 0:
                scored.append((score, -idx, chunk))

        scored.sort(reverse=True)
        return [item[2] for item in scored[: self.top_k]]
