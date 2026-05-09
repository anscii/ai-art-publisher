import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

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

Generate 3 variants differing radically in approach, tone, and implied genre — not just topic:
- title: 3-6 words, specific and strange, not generic
- description_en: 2-4 sentences for Instagram. A fragment of a world, not a caption for an image.
- description_ru: for Telegram, friends who also read a lot. Conversational but sharp. Different angle from the English if possible — not a translation, a parallel take.
- tags_instagram: up to 5 English hashtags (array of strings with #)
- tags_telegram: up to 3 Russian hashtags (array of strings with #)

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
    return m.group(1).strip() if m else text


@dataclass
class AIVariantData:
    title: str
    description_en: str
    description_ru: str
    tags_instagram: list[str]
    tags_telegram: list[str]

    def __post_init__(self):
        self.title = fix_llm_text(self.title)
        self.description_en = fix_llm_text(self.description_en)
        self.description_ru = fix_llm_text(self.description_ru)
        self.tags_instagram = [fix_llm_tag(t) for t in self.tags_instagram]
        self.tags_telegram = [fix_llm_tag(t) for t in self.tags_telegram]


class AIProvider(ABC):
    @abstractmethod
    def generate_variants(
        self,
        images_b64: list[str],
        model: str,
        hint: str | None = None,
    ) -> list[AIVariantData]: ...
