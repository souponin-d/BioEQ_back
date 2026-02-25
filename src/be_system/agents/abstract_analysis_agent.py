import json
import logging

from be_system.agents.json_utils import extract_json
from be_system.llm_client import LLMClient
from be_system.prompts import (
    ABSTRACT_ANALYSIS_SYSTEM_PROMPT,
    ABSTRACT_ANALYSIS_USER_PROMPT_TEMPLATE,
)
from be_system.schemas import PubMedArticle, PubMedPKAnalysis


class AbstractAnalysisAgent:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.logger = logging.getLogger("be_system.agents.abstract_analysis")

    def run(self, articles: list[PubMedArticle]) -> PubMedPKAnalysis:
        articles_json = json.dumps(
            [article.model_dump() for article in articles],
            ensure_ascii=False,
            indent=2,
        )
        prompt = ABSTRACT_ANALYSIS_USER_PROMPT_TEMPLATE.format(articles_json=articles_json)

        self.logger.debug("Abstract analysis prompt_len=%d", len(prompt))
        raw = self.llm_client.chat(ABSTRACT_ANALYSIS_SYSTEM_PROMPT, prompt)
        self.logger.debug("Abstract analysis raw response: %s", raw)

        try:
            data = extract_json(raw)
        except Exception as exc:
            self.logger.exception("Abstract analysis JSON parse failed")
            raise ValueError("AbstractAnalysisAgent failed to parse JSON response.") from exc

        return PubMedPKAnalysis.model_validate(data)
