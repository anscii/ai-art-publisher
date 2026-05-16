from app.services.ai.base import AIProvider, AIVariantData


class FakeAIProvider(AIProvider):
    def generate_variants(
        self, images_b64: list[str], model: str, hint: str | None = None
    ) -> list[AIVariantData]:
        return [
            AIVariantData(
                title=f"Fake Title {i + 1}",
                title_ru=f"Фейковый заголовок {i + 1}",
                description_en=f"Fake English description {i + 1}.",
                description_ru=f"Фейковое описание {i + 1}.",
                tags_instagram=["#fake", "#test"],
                tags_telegram=["#фейк"],
                instagram_seo=f"fake archaeology • test ruins {i + 1}",
                pinterest_title=f"Fake Pinterest Title {i + 1}",
                pinterest_description=f"Fake Pinterest description {i + 1}.",
                pinterest_board="Fake Board",
                archive_metadata={
                    "world_keywords": ["fake", "test"],
                    "visual_keywords": ["hollow"],
                    "mood_keywords": ["distant"],
                },
                cost_usd=0.0,
            )
            for i in range(3)
        ]
