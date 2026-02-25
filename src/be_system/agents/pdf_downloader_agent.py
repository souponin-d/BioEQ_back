import hashlib
import logging
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from be_system.schemas import DownloadedFile, FullTextLink

MIN_PDF_BYTES = 50_000


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

    def run(self, links: list[FullTextLink], output_dir: str | Path | None = None) -> list[DownloadedFile]:
        base_dir = Path(output_dir) if output_dir else self.output_dir
        base_dir.mkdir(parents=True, exist_ok=True)
        invalid_dir = base_dir / "invalid"
        invalid_dir.mkdir(parents=True, exist_ok=True)

        files: list[DownloadedFile] = []

        for link in links:
            if not link.pmcid:
                continue

            candidate_url = link.pdf_url_resolved or f"https://pmc.ncbi.nlm.nih.gov/articles/{link.pmcid}/pdf/"
            target_path = base_dir / f"{link.pmcid}.pdf"
            debug_html_path = invalid_dir / f"{link.pmcid}.html"
            downloaded = self._download_file(link.pmcid, candidate_url, target_path, debug_html_path)
            files.append(downloaded)

        ok_count = len([f for f in files if f.is_valid_pdf])
        invalid_count = len(files) - ok_count
        self.logger.info("PDF download done | ok=%d | invalid=%d", ok_count, invalid_count)
        return files

    def _download_file(
        self,
        doc_id: str,
        url: str,
        target_path: Path,
        debug_html_path: Path,
    ) -> DownloadedFile:
        status_code: int | None = None
        content_type: str | None = None
        body = b""
        reason: str | None = None

        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=self.timeout_sec) as response:
                status_code = getattr(response, "status", 200)
                content_type = response.headers.get("Content-Type")
                body = response.read(self.max_bytes + 1)
        except HTTPError as exc:
            status_code = exc.code
            content_type = exc.headers.get("Content-Type") if exc.headers else None
            body = exc.read() if hasattr(exc, "read") else b""
        except Exception:
            self.logger.exception("Failed to download PDF | pmcid=%s | url=%s", doc_id, url)
            reason = "download_error"

        if reason is None:
            reason = self._validate_pdf(status_code, content_type, body)

        if reason is None:
            if len(body) > self.max_bytes:
                target_path.unlink(missing_ok=True)
                return DownloadedFile(
                    id=doc_id,
                    url=url,
                    local_path=str(target_path),
                    sha256="",
                    bytes=len(body),
                    is_valid_pdf=False,
                    validation_reason="too_large",
                    content_type=content_type,
                    status_code=status_code,
                )
            sha256 = hashlib.sha256(body).hexdigest()
            target_path.write_bytes(body)
            return DownloadedFile(
                id=doc_id,
                url=url,
                local_path=str(target_path),
                sha256=sha256,
                bytes=len(body),
                is_valid_pdf=True,
                validation_reason=None,
                content_type=content_type,
                status_code=status_code,
            )

        target_path.unlink(missing_ok=True)
        if body.startswith(b"<html") or b"<html" in body[:1000].lower():
            debug_html_path.write_bytes(body)

        self.logger.info(
            "PDF invalid | pmcid=%s | status=%s | content_type=%s | reason=%s | first_bytes=%s",
            doc_id,
            status_code,
            content_type,
            reason,
            body[:20],
        )
        return DownloadedFile(
            id=doc_id,
            url=url,
            local_path=str(target_path),
            sha256="",
            bytes=len(body),
            is_valid_pdf=False,
            validation_reason=reason,
            content_type=content_type,
            status_code=status_code,
        )

    def _validate_pdf(self, status_code: int | None, content_type: str | None, content: bytes) -> str | None:
        if status_code != 200:
            return f"status_{status_code}"

        normalized_content_type = (content_type or "").lower()
        if "application/pdf" not in normalized_content_type:
            if content[:200].lstrip().lower().startswith(b"<html"):
                return "not_pdf_html"
            return "content_type_mismatch"

        if not content.startswith(b"%PDF"):
            if content[:200].lstrip().lower().startswith(b"<html"):
                return "not_pdf_html"
            return "invalid_pdf_header"

        if len(content) < MIN_PDF_BYTES:
            return "too_small"

        return None
