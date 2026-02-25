import json
import logging
from pathlib import Path

from be_system.agents.json_utils import extract_json
from be_system.llm_client import LLMClient
from be_system.prompts import PK_EXTRACTOR_SYSTEM_PROMPT, PK_EXTRACTOR_USER_PROMPT_TEMPLATE
from be_system.schemas import PKExtractionResult


class PKExtractorAgent:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.logger = logging.getLogger("be_system.agents.pk_extractor")

    def run(
        self,
        pmid: str,
        pmcid: str | None,
        source_type: str,
        fragments: list[dict],
        errors_dir: str | Path,
        article_tag: str,
    ) -> PKExtractionResult:
        metadata = {"pmid": pmid, "pmcid": pmcid, "source_type": source_type}
        prompt = PK_EXTRACTOR_USER_PROMPT_TEMPLATE.format(
            metadata_json=json.dumps(metadata, ensure_ascii=False, indent=2),
            fragments_json=json.dumps(fragments, ensure_ascii=False, indent=2),
        )
        raw = self.llm_client.chat(PK_EXTRACTOR_SYSTEM_PROMPT, prompt)

        try:
            data = extract_json(raw)
            return PKExtractionResult.model_validate(data)
        except Exception:
            self.logger.exception(
                "PK extractor JSON parse failed | pmid=%s | pmcid=%s | source=%s",
                pmid,
                pmcid,
                source_type,
            )
            errors_path = Path(errors_dir)
            errors_path.mkdir(parents=True, exist_ok=True)
            raw_path = errors_path / f"pk_extractor_{article_tag}_raw.txt"
            raw_path.write_text(raw, encoding="utf-8")
            self.logger.debug("PK extractor raw response saved: %s", raw_path)
            return PKExtractionResult(evidence=[], notes="Failed to parse LLM response")
