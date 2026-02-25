import hashlib
import logging
from pathlib import Path
from urllib.request import urlopen

from be_system.schemas import DownloadedFile, FullTextLink


class PdfDownloaderAgent:
    def __init__(
        self,
        output_dir: str | Path = "data/raw_pmc",
        timeout_sec: float = 60.0,
        max_bytes: int = 100 * 1024 * 1024,
    ):
        self.output_dir = Path(output_dir)
        self.timeout_sec = timeout_sec
        self.max_bytes = max_bytes
        self.logger = logging.getLogger("be_system.agents.pdf_downloader")

    def run(self, links: list[FullTextLink]) -> list[DownloadedFile]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        files: list[DownloadedFile] = []

        for link in links:
            if not link.pdf_url or not link.pmcid:
                continue
            target_path = self.output_dir / f"{link.pmcid}.pdf"
            downloaded = self._download_file(link.pmcid, link.pdf_url, target_path)
            if downloaded:
                files.append(downloaded)
        return files

    def _download_file(self, doc_id: str, url: str, target_path: Path) -> DownloadedFile | None:
        sha256 = hashlib.sha256()
        total = 0
        try:
            with urlopen(url, timeout=self.timeout_sec) as response:
                with target_path.open("wb") as f:
                    while True:
                        chunk = response.read(64 * 1024)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > self.max_bytes:
                            self.logger.warning("Skipping %s: file too large (> %d bytes)", url, self.max_bytes)
                            target_path.unlink(missing_ok=True)
                            return None
                        sha256.update(chunk)
                        f.write(chunk)
        except Exception:
            self.logger.exception("Failed to download PDF: %s", url)
            target_path.unlink(missing_ok=True)
            return None

        return DownloadedFile(
            id=doc_id,
            url=url,
            local_path=str(target_path),
            sha256=sha256.hexdigest(),
            bytes=total,
        )
