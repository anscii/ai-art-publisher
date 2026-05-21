import os


class FakeSettings:
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    openai_api_key = os.environ.get("OPENAI_API_KEY", "")
    google_api_key = os.environ.get("GOOGLE_API_KEY", "")
    deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    openrouter_api_key = os.environ.get("OPENROUTER_API_KEY", "")
