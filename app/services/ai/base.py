from abc import ABC, abstractmethod
from dataclasses import dataclass

SYSTEM_PROMPT = """You are a creative writer helping describe AI-generated artwork series for social media.

Given images from a series, generate 3 distinct variants of:
- title: short evocative name (3-6 words)
- description_en: 2-4 sentences for Instagram. Creative, engaging. May invent a story, fictional creature description, or world-building snippet that fits the images.
- description_ru: equivalent in Russian, more personal/conversational tone (for Telegram audience). Not a direct translation — rewrite for the tone.
- tags_instagram: 15-20 relevant English hashtags (array of strings with #)
- tags_telegram: 3-5 Russian hashtags (array of strings with #)

Variants should differ significantly — one story-focused, one creature/world-building, one poetic/atmospheric.

Respond ONLY with valid JSON array of 3 objects. No markdown, no preamble."""


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
