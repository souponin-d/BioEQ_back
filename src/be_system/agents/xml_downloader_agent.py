import hashlib
import json
import logging
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from be_system.schemas import DownloadedFile, FullTextLink


class XmlDownloaderAgent:
    def __init__(self, output_dir: str | Path = "data/raw_pmc", timeout_sec: float = 60.0):
        self.output_dir = Path(output_dir)
        self.timeout_sec = timeout_sec
        self.logger = logging.getLogger("be_system.agents.xml_downloader")

    def run(self, links: list[FullTextLink], output_dir: str | Path | None = None) -> list[DownloadedFile]:
        base_dir = Path(output_dir) if output_dir else self.output_dir
        base_dir.mkdir(parents=True, exist_ok=True)
        invalid_dir = base_dir / "invalid"
        invalid_dir.mkdir(parents=True, exist_ok=True)

        files: list[DownloadedFile] = []
        for link in links:
            if not (link.pmcid and link.has_fulltext_xml and link.xml_url_resolved):
                continue
            target_path = base_dir / f"{link.pmcid}.xml"
            downloaded = self._download(link.pmcid, link.xml_url_resolved, target_path, invalid_dir)
            files.append(downloaded)

        ok_count = len([f for f in files if f.is_valid_pdf])
        self.logger.info("XML download done | ok=%d | invalid=%d", ok_count, len(files) - ok_count)
        return files

    def _download(self, doc_id: str, url: str, target_path: Path, invalid_dir: Path) -> DownloadedFile:
        status_code: int | None = None
        content_type: str | None = None
        body = b""
        reason: str | None = None

        try:
            req = Request(url, headers={"User-Agent": "be_system/1.0"})
            with urlopen(req, timeout=self.timeout_sec) as response:
                status_code = getattr(response, "status", 200)
                content_type = response.headers.get("Content-Type")
                body = response.read()
        except HTTPError as exc:
            status_code = exc.code
            content_type = exc.headers.get("Content-Type") if exc.headers else None
            body = exc.read() if hasattr(exc, "read") else b""
        except Exception:
            self.logger.exception("Failed to download XML | pmcid=%s | url=%s", doc_id, url)
            reason = "download_error"

        self.logger.debug(
            "XML URL response | pmcid=%s | url=%s | status=%s | content_type=%s",
            doc_id,
            url,
            status_code,
            content_type,
        )

        if reason is None and status_code != 200:
            reason = f"status_{status_code}"

        if reason is None and not body.strip():
            reason = "empty_body"

        if reason is None:
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
        (invalid_dir / f"{doc_id}_xml_invalid.json").write_text(
            json.dumps(
                {
                    "id": doc_id,
                    "url": url,
                    "status_code": status_code,
                    "content_type": content_type,
                    "reason": reason,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
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
