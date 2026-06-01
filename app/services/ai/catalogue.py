PROVIDER_MODEL_PRICING: dict[str, tuple[float, float]] = {
    # (input $/MTok, output $/MTok)
    "claude-opus-4-7": (5.00, 25.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "deepseek-v4-flash": (0.14, 0.28),
    "gpt-5.5": (5.00, 30.00),
    "gpt-5.4": (2.50, 15.00),
    "gpt-5.4-mini": (0.75, 4.50),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-3.1-flash-lite": (0.25, 1.50),
    # OpenRouter free tier — no cost
    "openrouter/free": (0.0, 0.0),
    "openrouter/owl-alpha": (0.0, 0.0),
    "nvidia/nemotron-3-super-120b-a12b-20230311:free": (0.0, 0.0),
    "google/gemma-4-31b-it:free": (0.0, 0.0),
    "openai/gpt-oss-120b:free": (0.0, 0.0),
    "deepseek/deepseek-v4-flash:free": (0.0, 0.0),
}


def calc_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    p = PROVIDER_MODEL_PRICING.get(model)
    if not p:
        return 0.0
    return (input_tokens * p[0] + output_tokens * p[1]) / 1_000_000


PROVIDER_MODELS: dict[str, list[dict[str, str]]] = {
    "anthropic": [
        {"id": "claude-opus-4-7", "label": "Opus 4.7 — most capable"},
        {"id": "claude-sonnet-4-6", "label": "Sonnet 4.6 — balanced"},
        {"id": "claude-haiku-4-5", "label": "Haiku 4.5 — fast"},
    ],
    "deepseek": [
        {"id": "deepseek-v4-flash", "label": "DeepSeek V4 Flash — fast"},
    ],
    "openai": [
        {"id": "gpt-5.5", "label": "GPT-5.5 — most capable"},
        {"id": "gpt-5.4", "label": "GPT-5.4 — capable"},
        {"id": "gpt-5.4-mini", "label": "GPT-5.4 mini — balanced"},
    ],
    "google": [
        {"id": "gemini-3.1-flash-lite", "label": "Gemini 3.1 Flash Lite — fast"},
        {"id": "gemini-2.5-flash", "label": "Gemini 2.5 Flash — balanced"},
        {"id": "gemini-2.5-flash-lite", "label": "Gemini 2.5 Flash Lite — fast"},
    ],
    "openrouter": [
        {"id": "openrouter/free", "label": "Auto-select free model"},
        {"id": "openrouter/owl-alpha", "label": "Owl Alpha"},
        {
            "id": "nvidia/nemotron-3-super-120b-a12b-20230311:free",
            "label": "Nvidia Nemotron 3 Super 120b (free)",
        },
        {"id": "google/gemma-4-31b-it:free", "label": "Gemma 4 31B (free)"},
        {"id": "openai/gpt-oss-120b:free", "label": "GPT OSS 120B (free)"},
        {"id": "deepseek/deepseek-v4-flash:free", "label": "DeepSeek V4 Flash (free)"},
    ],
}

# Fallback defaults when no per-provider model is configured in DB settings.
# Intentionally mid-tier (balanced cost/quality).
PROVIDER_DEFAULT_MODELS: dict[str, str] = {
    "anthropic": "claude-sonnet-4-6",
    "openai": "gpt-5.4-mini",
    "google": "gemini-2.5-flash",
    "deepseek": "deepseek-v4-flash",
    "openrouter": "openrouter/free",
}
