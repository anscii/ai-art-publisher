from app.services.ai.base import AIProvider, AIVariantData


class FakeAIProvider(AIProvider):
    def generate_variants(
        self,
        images_b64: list[str],
        model: str,
        hint: str | None = None,
        num_variants: int = 3,
        language: str = "en",
    ) -> list[AIVariantData]:
        if language == "ru":
            return [
                AIVariantData(
                    title="",
                    title_ru="",
                    description_en="",
                    description_ru=f"Фейковое предложение один {i + 1}.\n\nФейковое предложение два {i + 1}.",
                    tags_instagram=[],
                    tags_telegram=[],
                    cost_usd=0.0,
                )
                for i in range(num_variants)
            ]
        return [
            AIVariantData(
                title="",
                title_ru="",
                description_en=f"Fake English sentence one {i + 1}.\n\nFake English sentence two {i + 1}.",
                description_ru="",
                tags_instagram=[],
                tags_telegram=[],
                cost_usd=0.0,
            )
            for i in range(num_variants)
        ]

    def expand_variant(
        self,
        description: str,
        language: str,
        model: str,
        hint: str | None = None,
    ) -> AIVariantData:
        if language == "ru":
            return AIVariantData(
                title="Fake Expanded Title",
                title_ru="Фейковый расширенный заголовок",
                description_en="Fake expanded English sentence one.\n\nFake expanded English sentence two.",
                description_ru=description,
                tags_instagram=["#fake", "#test"],
                tags_telegram=["#фейк"],
                instagram_seo="fake archaeology • expanded ruins",
                pinterest_title="Fake Expanded Pinterest Title",
                pinterest_description="Fake expanded Pinterest description.",
                pinterest_board="Fake Board",
                archive_metadata={
                    "world_keywords": ["fake", "expanded"],
                    "visual_keywords": ["hollow"],
                    "mood_keywords": ["distant"],
                },
                cost_usd=0.0,
            )
        return AIVariantData(
            title="Fake Expanded Title",
            title_ru="Фейковый расширенный заголовок",
            description_en=description,
            description_ru="Фейковое расширенное предложение один.\n\nФейковое расширенное предложение два.",
            tags_instagram=["#fake", "#test"],
            tags_telegram=["#фейк"],
            instagram_seo="fake archaeology • expanded ruins",
            pinterest_title="Fake Expanded Pinterest Title",
            pinterest_description="Fake expanded Pinterest description.",
            pinterest_board="Fake Board",
            archive_metadata={
                "world_keywords": ["fake", "expanded"],
                "visual_keywords": ["hollow"],
                "mood_keywords": ["distant"],
            },
            cost_usd=0.0,
        )
