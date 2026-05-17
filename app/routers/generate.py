import base64
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AIVariant, Series
from app.routers.series import series_to_detail
from app.routers.settings import get_or_create_settings
from app.schemas import AIVariantSemanticUpdate, GenerateRequest
from app.services.ai.base import AIProvider
from app.services.ai.catalogue import PROVIDER_DEFAULT_MODELS
from app.services.storage import get_storage_from_settings

router = APIRouter(prefix="/api/series", tags=["generate"])
variants_router = APIRouter(prefix="/api/ai_variants", tags=["ai_variants"])


def get_provider(provider_name: str, api_key: str) -> AIProvider:
    from app.config import get_config

    if get_config().fake_ai:
        from app.services.ai.fake import FakeAIProvider

        return FakeAIProvider()
    if provider_name == "anthropic":
        from app.services.ai.anthropic import AnthropicProvider

        return AnthropicProvider(api_key)
    elif provider_name == "openai":
        from app.services.ai.openai import OpenAIProvider

        return OpenAIProvider(api_key)
    elif provider_name == "google":
        from app.services.ai.google import GoogleProvider

        return GoogleProvider(api_key)
    elif provider_name == "deepseek":
        from app.services.ai.deepseek import DeepSeekProvider

        return DeepSeekProvider(api_key)
    raise ValueError(f"Unknown provider: {provider_name}")


def _get_api_key(settings, provider: str) -> str:
    return {
        "anthropic": settings.anthropic_api_key,
        "openai": settings.openai_api_key,
        "google": settings.google_api_key,
        "deepseek": settings.deepseek_api_key,
    }.get(provider, "")


@router.post("/{series_id}/generate")
def generate_descriptions(
    series_id: str,
    body: GenerateRequest,
    db: Session = Depends(get_db),
):
    s = db.get(Series, series_id)
    if not s:
        raise HTTPException(status_code=404, detail="Series not found")
    if not body.include_images and not body.hint:
        raise HTTPException(status_code=400, detail="Hint is required when not including images")
    if body.include_images and not s.images:
        raise HTTPException(status_code=400, detail="Series has no images")

    settings = get_or_create_settings(db)
    provider_name = body.provider or settings.default_provider
    model = (
        body.model
        or getattr(settings, f"{provider_name}_default_model", None)
        or PROVIDER_DEFAULT_MODELS.get(provider_name, "")
    )
    from app.config import get_config

    api_key = _get_api_key(settings, provider_name)
    if not api_key and not get_config().fake_ai:
        raise HTTPException(status_code=400, detail=f"API key for {provider_name} not configured")

    images_b64: list[str] = []
    if body.include_images:
        storage = get_storage_from_settings(settings)
        active = {i.id: i for i in s.images if i.deleted_at is None}
        if body.selected_image_ids:
            ordered = [active[id] for id in body.selected_image_ids if id in active][:3]
        else:
            ordered = sorted(active.values(), key=lambda i: i.order_index)[:3]
        for img in ordered:
            data = storage.download_bytes(img.r2_key)
            images_b64.append(base64.b64encode(data).decode())

    board_context = ""
    if settings.pinterest_board_map:
        try:
            _bm = json.loads(settings.pinterest_board_map)
            if _bm:
                names = ", ".join(_bm.keys())
                board_context = (
                    f"\n\nExisting Pinterest boards: {names}. "
                    "For the pinterest.board field, prefer one of these names; "
                    "suggest a new board name only if none fit this artwork."
                )
        except (json.JSONDecodeError, TypeError):
            pass

    augmented_hint = (body.hint or "") + board_context if board_context else body.hint

    provider = get_provider(provider_name, api_key)
    variants_data = provider.generate_variants(images_b64, model, augmented_hint)

    for vd in variants_data:
        v = AIVariant(
            series_id=series_id,
            provider=provider_name,
            model=model,
            title=vd.title,
            title_ru=vd.title_ru,
            description_en=vd.description_en,
            description_ru=vd.description_ru,
            tags_instagram=json.dumps(vd.tags_instagram),
            tags_telegram=json.dumps(vd.tags_telegram),
            hint=body.hint,
            cost_usd=vd.cost_usd,
            instagram_seo=vd.instagram_seo or None,
            pinterest_title=vd.pinterest_title or None,
            pinterest_description=vd.pinterest_description or None,
            pinterest_board=vd.pinterest_board or None,
            archive_metadata=json.dumps(vd.archive_metadata) if vd.archive_metadata else None,
        )
        db.add(v)
    db.commit()
    return series_to_detail(s, db).ai_variants


@variants_router.delete("/{variant_id}")
def delete_variant(variant_id: str, db: Session = Depends(get_db)):
    from sqlalchemy import select as _select

    from app.models import Post

    v = db.get(AIVariant, variant_id)
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")

    used = (
        db.scalar(
            _select(Post.id)
            .where(
                Post.variant_id == variant_id,
                Post.deleted_at.is_(None),
            )
            .limit(1)
        )
        is not None
    )
    if used:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete a variant that has been used in posts",
        )

    series = v.series
    if series.chosen_variant_id == variant_id:
        series.chosen_variant_id = None
    db.delete(v)
    db.commit()
    return series_to_detail(series, db)


@variants_router.patch("/{variant_id}")
def update_variant_semantic(
    variant_id: str,
    body: AIVariantSemanticUpdate,
    db: Session = Depends(get_db),
):
    v = db.get(AIVariant, variant_id)
    if not v:
        raise HTTPException(status_code=404, detail="AIVariant not found")
    if body.instagram_seo is not None:
        v.instagram_seo = body.instagram_seo or None
    if body.pinterest_title is not None:
        v.pinterest_title = body.pinterest_title or None
    if body.pinterest_description is not None:
        v.pinterest_description = body.pinterest_description or None
    if body.pinterest_board is not None:
        v.pinterest_board = body.pinterest_board or None
    if body.archive_metadata is not None:
        v.archive_metadata = json.dumps(body.archive_metadata) if body.archive_metadata else None
    db.commit()
    return series_to_detail(v.series, db)
