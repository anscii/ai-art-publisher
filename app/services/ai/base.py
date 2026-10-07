import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

MAX_OUTPUT_TOKENS = 8192

DEFAULT_STYLE_GUIDE = """You write short captions for artwork posted on social media. Each caption is a small fragment of the world inside the image — a moment, a voice, a story the picture belongs to — not a description of the picture itself.

WHAT MAKES A GOOD CAPTION:
- Implies more than it states. One specific, concrete detail — a name, an object, a rule of this world — does more than a paragraph of atmosphere.
- Has a point of view. Someone is speaking or noticing, and they have a relationship to what they see.
- Finds an angle beyond the first, most obvious reading of the image.
- Leaves a question open; the reader should want to look at the image again.
- Matches the register of the artwork: playful, tender, eerie, funny or serious — whatever the image earns. Humor is welcome.
- Social-media safe: no explicit gore, no graphic sexual content, nothing that reads as targeted hate.

WHAT TO AVOID:
- Describing what the image shows (the reader can see it).
- Filler adjectives: "mystical", "ethereal", "enchanted", "timeless", "otherworldly", "stunning", "breathtaking".
- Moral lessons, clichés, and generic inspirational endings.
- Prose that sounds deep without saying anything."""

_DISCOVERY_SECTION = """

DISCOVERY / ARCHIVE LAYER:

Additionally generate a semantic metadata layer intended for:
- Instagram discoverability
- Pinterest SEO
- archive-like world classification

This layer should NOT sound like marketing copy, influencer language,
or generic SEO spam.

Instead, it should feel like:
- archivist taxonomy
- aesthetic classification
- genre indexing
- future library metadata
- forbidden catalog systems
- research tags from an impossible institution

Good examples:
- dream archaeology
- fungal megastructures
- posthuman pilgrimage routes
- unstable cartography
- cosmic bureaucracy
- bioluminescent ruins
- ritual astronomy
- abandoned orbital gardens

Avoid generic phrases like:
- amazing fantasy art
- beautiful sci-fi world
- stunning digital artwork
- epic AI art"""

_STEP1_KEY = {"en": "description_en", "ru": "description_ru"}
_STEP1_PLATFORM = {"en": "Instagram", "ru": "Telegram"}
_STEP2_PRIMARY_LABEL = {"en": "English", "ru": "Russian"}
_STEP2_SECONDARY_KEY = {"en": "description_ru", "ru": "description_en"}
_STEP2_SECONDARY_LABEL = {"en": "Russian", "ru": "English"}
_STEP2_SECONDARY_PLATFORM = {"en": "Telegram", "ru": "Instagram"}


def build_step1_system_prompt(
    num_variants: int = 3, language: str = "en", style_guide: str = ""
) -> str:
    key = _STEP1_KEY.get(language, "description_en")
    platform = _STEP1_PLATFORM.get(language, "Instagram")
    return (
        (style_guide.strip() or DEFAULT_STYLE_GUIDE)
        + f"""

Generate {num_variants} variants differing radically in approach, tone, and implied genre — not just topic. Vary tone and angle between variants.
Each variant must be a JSON object with exactly one key:

- {key}: 2-4 sentences for {platform}. A fragment of a world. Use \\n\\n between paragraphs — break on meaning and rhythm, not mechanically after every sentence.

Respond ONLY with valid JSON array of {num_variants} objects. No markdown, no preamble."""
    )


def build_step2_system_prompt(language: str = "en", style_guide: str = "") -> str:
    primary_label = _STEP2_PRIMARY_LABEL.get(language, "English")
    secondary_key = _STEP2_SECONDARY_KEY.get(language, "description_ru")
    secondary_label = _STEP2_SECONDARY_LABEL.get(language, "Russian")
    secondary_platform = _STEP2_SECONDARY_PLATFORM.get(language, "Telegram")
    return (
        (style_guide.strip() or DEFAULT_STYLE_GUIDE)
        + _DISCOVERY_SECTION
        + f"""

The user provides a finalized {primary_label} description. Do NOT alter it. Generate everything else for the content package.

PARALLEL COMPOSITION RULE (critical):
Do NOT translate anything. The {secondary_label} title and description must be written fresh, as if a {secondary_label}-speaking author with the same sensibility encountered the same image independently — working from the {secondary_label}-language literary tradition. Similar atmosphere, similar core strangeness. But a different entry point, different detail foregrounded, different rhythm. The {secondary_label} reader should feel this was written for them, not translated at them. Variation is not a flaw — it is the goal.

Generate a single JSON object with these exact keys:

- title: 3-6 words, specific, not generic (English). Drawn from the atmosphere of the provided description.
- title_ru: 3-6 words in Russian — NOT a translation of title. A parallel name: same mood, different angle. Could lean on a different detail or metaphor entirely.
- {secondary_key}: Written natively in {secondary_label} for {secondary_platform}. Slightly similar world as the provided description — slightly similar atmosphere, mood, themes — but composed fresh. Allow a shifted emphasis, a different image foregrounded, different angle. 2-4 sentences. Use \\n\\n between paragraphs — break on meaning and rhythm, not mechanically.
- instagram:
    seo: short atmospheric semantic phrase layer, 3-8 fragments separated by •
    tags: up to 5 English hashtags (array of strings with #) mixing discoverability + in-world taxonomy
- pinterest:
    title: concrete searchable visual title, 5-12 words
    description: 1-2 sentences optimized for Pinterest search while preserving atmosphere
    board: board name — prefer an existing board name if provided in the user message; suggest a creative new name only if none of the existing ones fit
- archive_classification:
    world_keywords: 3-8 worldbuilding concepts (array of strings)
    visual_keywords: 3-8 visual/aesthetic descriptors (array of strings)
    mood_keywords: 3-8 emotional or atmospheric descriptors (array of strings)
- tags_telegram: up to 3 Russian hashtags (array of strings with #)

Respond ONLY with a valid JSON object. No markdown, no preamble."""
    )


_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```")
_logger = logging.getLogger(__name__)


def build_step2_user_text(description: str, language: str, hint: str | None) -> str:
    key = _STEP1_KEY.get(language, "description_en")
    lines = [f"{key}: {description}"]
    if hint:
        lines.append(f"\nArtwork context: {hint}")
    return "\n".join(lines)


def build_user_text(images_b64: list[str], hint: str | None) -> str:
    if images_b64:
        text = "Describe this artwork series."
        if hint:
            text += f" Additional context: {hint}"
    else:
        text = f"Generate narrative fragments and archive metadata for this artwork series.\n\nArtwork description: {hint}"
    return text


def fix_llm_text(text: str) -> str:
    text = re.sub(r"(\w)—", r"\1 —", text)
    text = re.sub(r"—(\w)", r"— \1", text)
    return text


def _ensure_newlines(text: str) -> str:
    if "\n" in text:
        return text
    sentences = re.split(r"(?<=[.!?…])\s+", text.strip())
    if len(sentences) > 1:
        _logger.warning("description missing newlines, force-inserting: %r", text[:80])
        return "\n\n".join(sentences)
    return text


def fix_llm_tag(tag: str) -> str:
    return tag.replace("-", "_").replace(" ", "_")


def extract_json(text: str) -> str:
    """Strip markdown code fences that models sometimes add despite instructions."""
    text = text.strip()
    m = _FENCE_RE.search(text)
    text = m.group(1).strip() if m else text
    # DeepSeek sometimes emits unquoted hashtags: , #Tag" → , "#Tag"
    if "#" in text:
        text = re.sub(
            r'([,\[]\s*)#([^",\[\]\n]+)"',
            lambda match: match.group(1) + '"#' + match.group(2) + '"',
            text,
        )
    return text


class AIResponseError(RuntimeError):
    """Model answered, but the answer is unusable. Message is safe to show in the UI."""


def _parse_json(text: str, provider: str, model: str) -> Any:
    try:
        return json.loads(extract_json(text))
    except Exception as exc:
        _logger.warning(
            "json parse failed | provider=%s | model=%s | error=%s | text=%s",
            provider,
            model,
            exc,
            text,
        )
        raise AIResponseError(
            f"{provider} {model} returned a response that is not valid JSON: {exc}"
        ) from exc


def parse_ai_response(text: str, provider: str, model: str) -> list[Any]:
    return _parse_json(text, provider, model)  # type: ignore[no-any-return]


def parse_ai_object(text: str, provider: str, model: str) -> dict[str, Any]:
    result = _parse_json(text, provider, model)
    if isinstance(result, list) and len(result) == 1:
        return result[0]  # type: ignore[no-any-return]
    return result  # type: ignore[no-any-return]


@dataclass
class AIVariantData:
    title: str
    title_ru: str
    description_en: str
    description_ru: str
    tags_instagram: list[str] = field(default_factory=list)
    tags_telegram: list[str] = field(default_factory=list)
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    instagram_seo: str = ""
    pinterest_title: str = ""
    pinterest_description: str = ""
    pinterest_board: str = ""
    archive_metadata: dict = field(default_factory=dict)
    actual_model: str | None = None

    def __post_init__(self):
        self.title = fix_llm_text(self.title)
        self.title_ru = fix_llm_text(self.title_ru)
        self.description_en = _ensure_newlines(fix_llm_text(self.description_en))
        self.description_ru = _ensure_newlines(fix_llm_text(self.description_ru))
        self.tags_instagram = [fix_llm_tag(t) for t in self.tags_instagram]
        if "#aiart" not in self.tags_instagram:
            self.tags_instagram.append("#aiart")
        self.tags_telegram = [fix_llm_tag(t) for t in self.tags_telegram]

    @classmethod
    def from_llm_dict(cls, d: dict) -> "AIVariantData":
        ig = d.get("instagram") or {}
        pin = d.get("pinterest") or {}
        arch = d.get("archive_classification") or {}
        return cls(
            title=d.get("title", ""),
            title_ru=d.get("title_ru", ""),
            description_en=d.get("description_en", ""),
            description_ru=d.get("description_ru", ""),
            tags_instagram=ig.get("tags") or [],
            tags_telegram=d.get("tags_telegram") or [],
            instagram_seo=ig.get("seo", ""),
            pinterest_title=pin.get("title", ""),
            pinterest_description=pin.get("description", ""),
            pinterest_board=pin.get("board", ""),
            archive_metadata={
                "world_keywords": arch.get("world_keywords") or [],
                "visual_keywords": arch.get("visual_keywords") or [],
                "mood_keywords": arch.get("mood_keywords") or [],
            },
        )


def attach_usage(
    variants: list[AIVariantData], input_tokens: int, output_tokens: int, cost_usd: float
) -> None:
    for vd in variants:
        vd.cost_usd = cost_usd
        vd.input_tokens = input_tokens
        vd.output_tokens = output_tokens


class AIProvider(ABC):
    style_guide: str = ""

    @abstractmethod
    def generate_variants(
        self,
        images_b64: list[str],
        model: str,
        hint: str | None = None,
        num_variants: int = 3,
        language: str = "en",
    ) -> list[AIVariantData]: ...

    @abstractmethod
    def expand_variant(
        self,
        description: str,
        language: str,
        model: str,
        hint: str | None = None,
    ) -> AIVariantData: ...
