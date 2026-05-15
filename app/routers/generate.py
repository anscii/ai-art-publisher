import base64
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AIVariant, Series
from app.routers.series import series_to_detail
from app.routers.settings import get_or_create_settings
from app.schemas import GenerateRequest
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

    provider = get_provider(provider_name, api_key)
    variants_data = provider.generate_variants(images_b64, model, body.hint)

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
        )
        db.add(v)
    db.commit()
    return series_to_detail(s, db).ai_variants


@variants_router.delete("/{variant_id}")
def delete_variant(variant_id: str, db: Session = Depends(get_db)):
    v = db.get(AIVariant, variant_id)
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")
    series = v.series
    if series.chosen_variant_id == variant_id:
        series.chosen_variant_id = None
    db.delete(v)
    db.commit()
    return series_to_detail(series, db)
