PROVIDER_MODEL_PRICING: dict[str, tuple[float, float]] = {
    # (input $/MTok, output $/MTok) — standard tier, verified 2026-10-02
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
    # DeepSeek: peak-hour price (off-peak is half)
    "deepseek-v4-pro": (1.32, 3.96),
    "deepseek-flash": (0.30, 1.20),
    "deepseek-v4-flash": (0.30, 1.20),  # legacy id, routes to deepseek-flash
    # OpenAI: short-context (<=272K) price; long context is 2x
    "gpt-6-astra": (10.00, 50.00),
    "gpt-6.1-sol": (2.00, 10.00),
    "gpt-6-luna": (0.10, 0.50),
    # Google: 3.8 Flash promo price until 2027-01-01 (then 1.50 / 7.50)
    "gemini-3.8-flash": (0.75, 3.75),
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.1-flash-lite": (0.25, 1.50),
    # OpenRouter free tier — no cost
    "openrouter/free": (0.0, 0.0),
    "nvidia/nemotron-3.5-lightning:free": (0.0, 0.0),
    "nvidia/nemotron-3-ultra-550b-a55b:free": (0.0, 0.0),
    "nvidia/nemotron-3-super-120b-a12b:free": (0.0, 0.0),
    "google/gemma-4-31b-it:free": (0.0, 0.0),
    "qwen/qwen3.8-27b:free": (0.0, 0.0),
}


def calc_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    p = PROVIDER_MODEL_PRICING.get(model)
    if not p:
        return 0.0
    return (input_tokens * p[0] + output_tokens * p[1]) / 1_000_000


PROVIDER_MODELS: dict[str, list[dict[str, str]]] = {
    "anthropic": [
        {"id": "claude-opus-5-5", "label": "Opus 5.5 — most capable"},
        {"id": "claude-sonnet-5-5", "label": "Sonnet 5.5 — balanced"},
        {"id": "claude-haiku-4-5", "label": "Haiku 4.5 — fast"},
    ],
    "deepseek": [
        {"id": "deepseek-v4-pro", "label": "DeepSeek V4 Pro — most capable"},
        {"id": "deepseek-flash", "label": "DeepSeek Flash (V4.1) — fast"},
    ],
    "openai": [
        {"id": "gpt-6-astra", "label": "GPT-6 Astra — most capable"},
        {"id": "gpt-6.1-sol", "label": "GPT-6.1 Sol — balanced"},
        {"id": "gpt-6-luna", "label": "GPT-6 Luna — fast"},
    ],
    "google": [
        {"id": "gemini-3.8-flash", "label": "Gemini 3.8 Flash — most capable"},
        {"id": "gemini-3.5-flash-lite", "label": "Gemini 3.5 Flash Lite — balanced"},
        {"id": "gemini-3.1-flash-lite", "label": "Gemini 3.1 Flash Lite — fast"},
    ],
    "openrouter": [
        {"id": "openrouter/free", "label": "Auto-select free model"},
        {
            "id": "nvidia/nemotron-3.5-lightning:free",
            "label": "Nvidia Nemotron 3.5 Lightning (free)",
        },
        {
            "id": "nvidia/nemotron-3-ultra-550b-a55b:free",
            "label": "Nvidia Nemotron 3 Ultra 550b (free)",
        },
        {
            "id": "nvidia/nemotron-3-super-120b-a12b:free",
            "label": "Nvidia Nemotron 3 Super 120b (free)",
        },
        {"id": "google/gemma-4-31b-it:free", "label": "Gemma 4 31B (free)"},
        {"id": "qwen/qwen3.8-27b:free", "label": "Qwen 3.8 27B (free, vision)"},
    ],
}

# Fallback defaults when no per-provider model is configured in DB settings.
# Intentionally mid-tier (balanced cost/quality).
PROVIDER_DEFAULT_MODELS: dict[str, str] = {
    "anthropic": "claude-sonnet-5-5",
    "openai": "gpt-6.1-sol",
    "google": "gemini-3.5-flash-lite",
    "deepseek": "deepseek-flash",
    "openrouter": "openrouter/free",
}


# ── Image editing (image + prompt → image) ───────────────────────────────────
# (text-in $/MTok, image-in $/MTok, image-out $/MTok) — standard tier, verified 2026-10-02
IMAGE_EDIT_PRICING: dict[str, tuple[float, float, float]] = {
    "gpt-image-2.5-flare": (5.00, 8.00, 30.00),
    "gpt-image-2.5-sunburst": (5.00, 8.00, 30.00),
    "gpt-image-2": (5.00, 8.00, 30.00),
    # Google: same input price for text and image tokens
    "gemini-3.1-flash-lite-image": (0.25, 0.25, 30.00),
    "gemini-3.1-flash-image": (0.50, 0.50, 60.00),
    "gemini-3-pro-image": (2.00, 2.00, 120.00),
}

IMAGE_EDIT_MODELS: list[dict[str, str]] = [
    {"id": "gpt-image-2.5-flare", "provider": "openai", "label": "GPT Image 2.5 Flare — fast"},
    {
        "id": "gpt-image-2.5-sunburst",
        "provider": "openai",
        "label": "GPT Image 2.5 Sunburst — precise edits",
    },
    {"id": "gpt-image-2", "provider": "openai", "label": "GPT Image 2"},
    {
        "id": "gemini-3.1-flash-lite-image",
        "provider": "google",
        "label": "Nano Banana 2 Lite — cheapest (~$0.03)",
    },
    {
        "id": "gemini-3.1-flash-image",
        "provider": "google",
        "label": "Nano Banana 2 — balanced (~$0.07)",
    },
    {"id": "gemini-3-pro-image", "provider": "google", "label": "Nano Banana Pro — best (~$0.13)"},
]

DEFAULT_IMAGE_EDIT_MODEL = "gpt-image-2.5-flare"


def image_edit_provider(model: str) -> str:
    for m in IMAGE_EDIT_MODELS:
        if m["id"] == model:
            return m["provider"]
    raise ValueError(f"Unknown image edit model: {model}")


def calc_image_edit_cost(model: str, text_in: int, image_in: int, image_out: int) -> float:
    p = IMAGE_EDIT_PRICING.get(model)
    if not p:
        return 0.0
    return (text_in * p[0] + image_in * p[1] + image_out * p[2]) / 1_000_000
