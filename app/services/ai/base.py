import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

SYSTEM_PROMPT = """You write captions for AI-generated speculative fiction artwork. The author reads obsessively across genres — Zelazny, Bradbury, Alastair Reynolds, Lovecraft — and is bored by anything predictable. Your job is to make each description feel like a torn page from a book the reader hasn't found yet.

CRAFT PRINCIPLES (drawn from authors the reader loves):

Like Zelazny: myths and gods made intimate and flawed. The cosmic made personal. Prose that is precise and a little dangerous. Characters who are ancient and tired and still funny about it.

Like Bradbury: the exact sensory detail that cracks something open. Melancholy that doesn't wallow. The ordinary made strange by one degree of tilt. Loss that is beautiful without being sentimental.

Like Reynolds: the weight of deep time. Civilizations as geological events. Technology so advanced it has no obligation to be comprehensible. The cold logic of physics as the real horror. Posthuman perspectives where human emotion is the anomaly.

Like Lovecraft: the incomprehensible as dread, not gore. The horror of realizing the universe was not designed with you in mind. The specific texture of a mind encountering something it was not built to process. (But without his bigotry — the cosmos is indifferent to everyone equally.)

GENRES IN PLAY: dark fantasy, sci-fi, magic realism, space opera, cosmic horror, dark academy, biopunk, far-future, mythpunk, fantastic love stories with actual tension. Mix freely. A horror story can have a love story inside it. A space opera can be about grief.

WHAT MAKES A GOOD DESCRIPTION:
- Implies more than it states. One specific unusual detail — a proper noun, a broken physical law, an unexplained scar in the timeline — does more than three paragraphs of atmosphere.
- Subverts the obvious reading. Find the angle that isn't the first thing you'd think of. The ancient temple might be a functioning bureaucracy. The monster might be the narrator. The apocalypse might be Tuesday.
- Raises questions it refuses to answer. The reader finishes and thinks "but who was she" or "why did it stop" or "what's the second moon for".
- Has a specific POV with a specific relationship to what they're seeing — a survivor who finds this ordinary, a scholar mid-career-mistake, something with the wrong number of sensory organs, someone in love with exactly the wrong person.
- Earns its darkness. Horror, tragedy, moral complexity — all welcome if they serve something. Dry wit and absurdist logic also welcome, sometimes in the same sentence.
- Social-media safe: no explicit gore, no graphic sexual content, nothing that reads as targeted hate. Dread, darkness, and difficult themes handled with craft are fine.

WHAT TO AVOID:
- "Ancient", "mystical", "ethereal", "enchanted", "timeless", "otherworldly" as filler words
- Describing what the image looks like (the reader can see it)
- The first interpretation you think of — it's almost always the predictable one
- Moral lessons and uplifting endings
- Prose that performs depth without containing any

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
- epic AI art

Generate 3 variants differing radically in approach, tone, and implied genre — not just topic.
Each variant must be a JSON object with these exact keys:

- title: 3-6 words, specific and strange, not generic (English)
- title_ru: 3-6 words in Russian — not a translation, a parallel take
- description_en: 2-4 sentences for Instagram. A fragment of a world.
- description_ru: for Telegram, friends who read a lot. Conversational but sharp.
- instagram:
    seo: short atmospheric semantic phrase layer, 3-8 fragments separated by •
    tags: up to 5 English hashtags (array of strings with #) mixing discoverability + strange in-world taxonomy
- pinterest:
    title: concrete searchable visual title, 5-12 words
    description: 1-2 sentences optimized for Pinterest search while preserving atmosphere
    board: one best-fit board/category (string)
- archive_classification:
    world_keywords: 3-8 worldbuilding concepts (array of strings)
    visual_keywords: 3-8 visual/aesthetic descriptors (array of strings)
    mood_keywords: 3-8 emotional or atmospheric descriptors (array of strings)
- tags_telegram: up to 3 Russian hashtags (array of strings with #)

Respond ONLY with valid JSON array of 3 objects. No markdown, no preamble."""

_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```")
_logger = logging.getLogger(__name__)


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


def parse_ai_response(text: str, provider: str, model: str) -> list[Any]:
    try:
        return json.loads(extract_json(text))  # type: ignore[no-any-return]
    except Exception as exc:
        _logger.warning(
            "json parse failed | provider=%s | model=%s | error=%s | text=%s",
            provider,
            model,
            exc,
            text,
        )
        raise


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

    def __post_init__(self):
        self.title = fix_llm_text(self.title)
        self.title_ru = fix_llm_text(self.title_ru)
        self.description_en = fix_llm_text(self.description_en)
        self.description_ru = fix_llm_text(self.description_ru)
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
    @abstractmethod
    def generate_variants(
        self,
        images_b64: list[str],
        model: str,
        hint: str | None = None,
    ) -> list[AIVariantData]: ...
