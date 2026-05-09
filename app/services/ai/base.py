import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

SYSTEM_PROMPT = """You are a creative writer helping describe AI-generated artwork series for social media.

Generate 3 distinct variants of:
- title: short evocative name (3-6 words)
- description_en: 2-4 sentences for Instagram. Creative, engaging. May invent a story, fictional creature description, or world-building snippet that fits the artwork.
- description_ru: equivalent in Russian, more personal/conversational tone (for Telegram audience of friends). Not a direct translation — rewrite for the tone.
- tags_instagram: up to 5 relevant English hashtags (array of strings with #)
- tags_telegram: up to 3 Russian hashtags (array of strings with #)

Variants should differ significantly — one story-focused, one creature/world-building, one poetic/atmospheric.

Respond ONLY with valid JSON array of 3 objects. No markdown, no preamble."""

_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```")


def build_user_text(images_b64: list[str], hint: str | None) -> str:
    if images_b64:
        text = "Describe this artwork series."
        if hint:
            text += f" Additional context: {hint}"
    else:
        text = f"Generate descriptions for this artwork series. Artwork description: {hint}"
    return text


def extract_json(text: str) -> str:
    """Strip markdown code fences that models sometimes add despite instructions."""
    text = text.strip()
    m = _FENCE_RE.search(text)
    return m.group(1).strip() if m else text


@dataclass
class AIVariantData:
    title: str
    description_en: str
    description_ru: str
    tags_instagram: list[str]
    tags_telegram: list[str]


class AIProvider(ABC):
    @abstractmethod
    def generate_variants(
        self,
        images_b64: list[str],
        model: str,
        hint: str | None = None,
    ) -> list[AIVariantData]: ...
