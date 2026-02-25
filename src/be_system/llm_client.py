import logging
import time

from openai import OpenAI

from be_system.logging_utils import fmt_seconds, timer


class LLMClient:
    def __init__(self, base_url: str, api_key: str, model_name: str):
        self.model_name = model_name
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.logger = logging.getLogger(f"be_system.llm_client.{model_name}")

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> str:
        self.logger.info(
            "Starting LLM call | model=%s | temperature=%s | max_tokens=%s | system_len=%d | user_len=%d",
            self.model_name,
            temperature,
            max_tokens,
            len(system_prompt),
            len(user_prompt),
        )
        self.logger.debug("System prompt preview: %s", system_prompt[:200])
        self.logger.debug("User prompt preview: %s", user_prompt[:200])

        started_at = time.perf_counter()
        try:
            with timer("llm_call", self.logger):
                request_kwargs = {
                    "model": self.model_name,
                    "temperature": temperature,
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

        elapsed = time.perf_counter() - started_at
        content = response.choices[0].message.content or ""
        self.logger.info(
            "Finished LLM call | model=%s | response_len=%d | elapsed=%ss",
            self.model_name,
            len(content),
            fmt_seconds(elapsed),
        )
        return content
