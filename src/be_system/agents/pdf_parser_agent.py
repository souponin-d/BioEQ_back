import logging
import re
from pathlib import Path

from pypdf import PdfReader

from be_system.schemas import DownloadedFile, PdfChunk


class PdfParserAgent:
    def __init__(self, chunk_size: int = 2000, overlap: int = 200):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.logger = logging.getLogger("be_system.agents.pdf_parser")

    def run(self, files: list[DownloadedFile]) -> list[PdfChunk]:
        chunks: list[PdfChunk] = []
        for file in files:
            chunks.extend(self._parse_file(file))
        return chunks

    def _parse_file(self, file: DownloadedFile) -> list[PdfChunk]:
        path = Path(file.local_path)
        reader = PdfReader(str(path))
        out: list[PdfChunk] = []

        for i, page in enumerate(reader.pages, start=1):
            raw_text = page.extract_text() or ""
            text = self._normalize(raw_text)
            if not text:
                continue
            page_chunks = self._split_text(text)
            for j, chunk_text in enumerate(page_chunks, start=1):
                out.append(
                    PdfChunk(
                        doc_id=file.id,
                        page=i,
                        chunk_id=f"{file.id}:p{i}:c{j}",
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
