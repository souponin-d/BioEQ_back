from openai import OpenAI


class LLMClient:
    def __init__(self, base_url: str, api_key: str, model_name: str):
        self.model_name = model_name
        self.client = OpenAI(base_url=base_url, api_key=api_key)

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        response = self.client.chat.completions.create(
            model=self.model_name,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content or ""
