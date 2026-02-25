import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from be_system.schemas import DownloadedFile, XmlChunk


class XmlParserAgent:
    def __init__(self, chunk_size: int = 2000, overlap: int = 200):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.logger = logging.getLogger("be_system.agents.xml_parser")

    def run(self, files: list[DownloadedFile]) -> list[XmlChunk]:
        chunks: list[XmlChunk] = []
        for file in files:
            if file.is_valid_pdf:
                chunks.extend(self._parse_file(file))
        return chunks

    def _parse_file(self, file: DownloadedFile) -> list[XmlChunk]:
        raw = Path(file.local_path).read_text(encoding="utf-8", errors="ignore")
        self.logger.debug("Raw BioC/XML | doc_id=%s | body_prefix=%s", file.id, raw[:500])

        root = ET.fromstring(raw)
        section_texts: list[tuple[str | None, str]] = []

        for passage in root.findall(".//passage"):
            section = None
            infon = passage.find("infon[@key='section_type']")
            if infon is not None and infon.text:
                section = infon.text.strip()
            text_el = passage.find("text")
            if text_el is not None and text_el.text:
                section_texts.append((section, self._normalize(text_el.text)))

        if not section_texts:
            for node in root.findall(".//body"):
                section_texts.append(("body", self._normalize(" ".join(node.itertext()))))

        out: list[XmlChunk] = []
        for idx, (section, text) in enumerate(section_texts, start=1):
            if not text:
                continue
            for cidx, chunk_text in enumerate(self._split_text(text), start=1):
                out.append(
                    XmlChunk(
                        doc_id=file.id,
                        section=section,
                        chunk_id=f"{file.id}:s{idx}:c{cidx}",
                        text=chunk_text,
                    )
                )
        return out

    def _normalize(self, text: str) -> str:
        text = text.replace("\x00", " ")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _split_text(self, text: str) -> list[str]:
        if len(text) <= self.chunk_size:
            return [text]

        chunks: list[str] = []
        step = max(1, self.chunk_size - self.overlap)
        start = 0
        while start < len(text):
            end = min(len(text), start + self.chunk_size)
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(text):
                break
            start += step
        return chunks
