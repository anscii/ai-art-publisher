PROVIDER_MODEL_PRICING: dict[str, tuple[float, float]] = {
    # (input $/MTok, output $/MTok)
    "claude-opus-4-7": (5.00, 25.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "gpt-5.4": (2.50, 15.00),
    "gpt-5.4-mini": (0.75, 4.50),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-3.1-flash-lite": (0.25, 1.50),
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
        {"id": "claude-haiku-4-5-20251001", "label": "Haiku 4.5 — fast"},
    ],
    "openai": [
        {"id": "gpt-5.4", "label": "GPT-5.4 — most capable"},
        {"id": "gpt-5.4-mini", "label": "GPT-5.4 mini — balanced"},
        {"id": "gpt-4o", "label": "GPT-4o — capable"},
        {"id": "gpt-4o-mini", "label": "GPT-4o mini — fast/cheap"},
    ],
    "google": [
        {"id": "gemini-3.1-flash-lite", "label": "Gemini 3.1 Flash Lite — fast"},
        {"id": "gemini-2.5-flash", "label": "Gemini 2.5 Flash — balanced"},
        {"id": "gemini-2.5-flash-lite", "label": "Gemini 2.5 Flash Lite — fast"},
    ],
}

# Fallback defaults when no per-provider model is configured in DB settings.
# Intentionally mid-tier (balanced cost/quality).
PROVIDER_DEFAULT_MODELS: dict[str, str] = {
    "anthropic": "claude-sonnet-4-6",
    "openai": "gpt-5.4-mini",
    "google": "gemini-2.5-flash",
}
