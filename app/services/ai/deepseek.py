from typing import Any

import openai as _openai

from app.services.ai.openai import OpenAIProvider


class DeepSeekProvider(OpenAIProvider):
    def __init__(self, api_key: str):
        self._client = _openai.OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    def _call_api(self, model: str, messages: list[Any]) -> Any:
        return self._client.chat.completions.create(
            model=model, messages=messages, max_tokens=2048, temperature=1.0
        )
