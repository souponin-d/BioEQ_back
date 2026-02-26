import logging
import os
import time

from openai import OpenAI

from be_system.logging_utils import fmt_seconds


class LLMClient:
    def __init__(self, base_url: str, api_key: str, model_name: str):
        self.model_name = model_name
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.logger = logging.getLogger(f"be_system.llm_client.{model_name}")

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        self.logger.debug(
            "LLM prompt lengths | model=%s | system_len=%d | user_len=%d",
            self.model_name,
            len(system_prompt),
            len(user_prompt),
        )

        started_at = time.perf_counter()
        try:
            resolved_temperature = (
                float(os.getenv("LLM_TEMPERATURE", "0.0"))
                if temperature is None
                else temperature
            )
            request_kwargs = {
                "model": self.model_name,
                "temperature": resolved_temperature,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
            if max_tokens is not None:
                request_kwargs["max_tokens"] = max_tokens
            response = self.client.chat.completions.create(**request_kwargs)
        except Exception:
            elapsed = time.perf_counter() - started_at
            self.logger.exception(
                "LLM call failed | model=%s | elapsed=%ss",
                self.model_name,
                fmt_seconds(elapsed),
            )
            raise

        content = response.choices[0].message.content or ""
        self.logger.debug("Raw LLM response | model=%s | content=%s", self.model_name, content)
        return content
