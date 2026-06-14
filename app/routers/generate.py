import base64
import concurrent.futures
import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

import app.database as _db_module
from app.database import get_db
from app.models import AIVariant, Series
from app.routers.series import series_to_detail
from app.routers.settings import get_or_create_settings
from app.schemas import (
    AIVariantSemanticUpdate,
    GenerateFullRequest,
    GenerateRequest,
    SeriesDetail,
)
from app.services.ai.base import AIProvider
from app.services.ai.catalogue import PROVIDER_DEFAULT_MODELS
from app.services.storage import get_storage_from_settings

logger = logging.getLogger("app.generate")

_GENERATION_TIMEOUT = 300  # 5 minutes


def _call_with_timeout(fn, *args, timeout: int = _GENERATION_TIMEOUT, **kwargs):
    """Run fn(*args, **kwargs) in a thread; raise TimeoutError if it exceeds timeout seconds.

    Uses a 2-second grace period after the deadline: if the future completed at the
    boundary (race condition), we return its result instead of raising.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fn, *args, **kwargs)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            # Grace period: thread may have finished at the exact timeout boundary.
            try:
                return future.result(timeout=2)
            except concurrent.futures.TimeoutError:
                raise TimeoutError(f"AI call timed out after {timeout}s")


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
    elif provider_name == "openrouter":
        from app.services.ai.openrouter import OpenRouterProvider

        return OpenRouterProvider(api_key)
    raise ValueError(f"Unknown provider: {provider_name}")


def _get_api_key(settings, provider: str) -> str:
    return {
        "anthropic": settings.anthropic_api_key,
        "openai": settings.openai_api_key,
        "google": settings.google_api_key,
        "deepseek": settings.deepseek_api_key,
        "openrouter": settings.openrouter_api_key,
    }.get(provider, "")


def _resolve_actual_provider_model(
    actual_model: str | None, provider_name: str, model: str
) -> tuple[str, str]:
    """Return (provider, model) to store in AIVariant.

    Provider is always the routing provider (e.g. "openrouter").
    Model is the actual model returned by the API when available
    (e.g. "google/gemma-3-27b-it:free"), otherwise the requested model.
    """
    return provider_name, actual_model or model


def _build_board_context(settings) -> str:
    if not settings.pinterest_board_map:
        return ""
    try:
        _bm = json.loads(settings.pinterest_board_map)
        if _bm:
            names = ", ".join(_bm.keys())
            return (
                f"\n\nExisting Pinterest boards: {names}. "
                "For the pinterest.board field, prefer one of these names; "
                "suggest a new board name only if none fit this artwork."
            )
    except (json.JSONDecodeError, TypeError):
        pass
    return ""


def _run_generate_variants(series_id: str, body_data: dict, db: Session) -> None:
    """Core logic for generating draft variants. Runs in a background task or directly in tests."""
    s = db.get(Series, series_id)
    if not s:
        return

    settings = get_or_create_settings(db)
    provider_name = body_data.get("provider") or settings.default_provider
    model = (
        body_data.get("model")
        or getattr(settings, f"{provider_name}_default_model", None)
        or PROVIDER_DEFAULT_MODELS.get(provider_name, "")
    )

    api_key = _get_api_key(settings, provider_name)

    include_images = body_data.get("include_images", False)
    selected_image_ids = body_data.get("selected_image_ids")
    images_b64: list[str] = []
    if include_images:
        storage = get_storage_from_settings(settings)
        active = {i.id: i for i in s.images if i.deleted_at is None}
        if selected_image_ids:
            ordered = [active[id] for id in selected_image_ids if id in active][:3]
        else:
            ordered = sorted(active.values(), key=lambda i: i.order_index)[:3]
        for img in ordered:
            data = storage.download_bytes(img.r2_key)
            images_b64.append(base64.b64encode(data).decode())

    board_context = _build_board_context(settings)
    hint = body_data.get("hint")
    augmented_hint = (hint or "") + board_context if board_context else hint

    provider = get_provider(provider_name, api_key)
    num_variants = body_data.get("num_variants", 1)
    language = body_data.get("language", "en")
    variants_data = _call_with_timeout(
        provider.generate_variants,
        images_b64,
        model,
        augmented_hint,
        num_variants=num_variants,
        language=language,
    )

    for vd in variants_data:
        used_provider, used_model = _resolve_actual_provider_model(
            vd.actual_model, provider_name, model
        )
        v = AIVariant(
            series_id=series_id,
            provider=used_provider,
            model=used_model,
            title=vd.title,
            title_ru=vd.title_ru,
            description_en=vd.description_en,
            description_ru=vd.description_ru,
            tags_instagram=json.dumps(vd.tags_instagram),
            tags_telegram=json.dumps(vd.tags_telegram),
            hint=hint,
            cost_usd=vd.cost_usd,
            instagram_seo=vd.instagram_seo or None,
            pinterest_title=vd.pinterest_title or None,
            pinterest_description=vd.pinterest_description or None,
            pinterest_board=vd.pinterest_board or None,
            archive_metadata=json.dumps(vd.archive_metadata) if vd.archive_metadata else None,
        )
        db.add(v)

    s.generation_status = "idle"
    s.generation_error = None
    db.commit()


def _run_generate_full(series_id: str, body_data: dict, db: Session) -> None:
    """Core logic for generate-full. Runs in a background task or directly in tests."""
    s = db.get(Series, series_id)
    if not s:
        return

    settings = get_or_create_settings(db)
    provider_name = body_data.get("provider") or settings.default_provider
    model = (
        body_data.get("model")
        or getattr(settings, f"{provider_name}_default_model", None)
        or PROVIDER_DEFAULT_MODELS.get(provider_name, "")
    )

    api_key = _get_api_key(settings, provider_name)
    board_context = _build_board_context(settings)
    hint = body_data.get("hint")
    augmented_hint = (hint or "") + board_context if board_context else hint

    provider = get_provider(provider_name, api_key)
    description = body_data["description"]
    language = body_data.get("language", "en")
    vd = _call_with_timeout(provider.expand_variant, description, language, model, augmented_hint)
    used_provider, used_model = _resolve_actual_provider_model(
        vd.actual_model, provider_name, model
    )
    if language == "en":
        vd.description_en = description
    else:
        vd.description_ru = description

    variant_id = body_data.get("variant_id")
    if variant_id:
        existing = db.get(AIVariant, variant_id)
        if not existing or existing.series_id != series_id:
            s.generation_status = "failed"
            s.generation_error = f"Variant {variant_id} not found"
            db.commit()
            return
        is_draft = existing.title == "" and existing.title_ru == ""
        same_pipeline = existing.provider == used_provider and existing.model == used_model
        if is_draft and same_pipeline:
            v = existing
        else:
            v = AIVariant(series_id=series_id, provider=used_provider, model=used_model, hint=hint)
            if language == "en":
                v.description_en = description
            else:
                v.description_ru = description
            v.draft_id = variant_id
            db.add(v)
    else:
        v = AIVariant(series_id=series_id, provider=used_provider, model=used_model, hint=hint)
        db.add(v)

    v.provider = used_provider
    v.model = used_model
    v.title = vd.title
    v.title_ru = vd.title_ru
    v.description_en = vd.description_en
    v.description_ru = vd.description_ru
    v.tags_instagram = json.dumps(vd.tags_instagram)
    v.tags_telegram = json.dumps(vd.tags_telegram)
    v.hint = hint
    v.cost_usd = vd.cost_usd
    v.instagram_seo = vd.instagram_seo or None
    v.pinterest_title = vd.pinterest_title or None
    v.pinterest_description = vd.pinterest_description or None
    v.pinterest_board = vd.pinterest_board or None
    v.archive_metadata = json.dumps(vd.archive_metadata) if vd.archive_metadata else None

    s.generation_status = "idle"
    s.generation_error = None
    db.commit()


def _generate_variants_background(series_id: str, body_data: dict) -> None:
    db = _db_module.SessionLocal()
    try:
        _run_generate_variants(series_id, body_data, db)
    except Exception as exc:
        logger.exception("Background generation failed for series %s: %s", series_id, exc)
        try:
            _s = db.get(Series, series_id)
            if _s and _s.generation_status.startswith("generating"):
                _s.generation_status = "failed"
                _s.generation_error = str(exc)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def _generate_full_background(series_id: str, body_data: dict) -> None:
    db = _db_module.SessionLocal()
    try:
        _run_generate_full(series_id, body_data, db)
    except Exception as exc:
        logger.exception("Background generate-full failed for series %s: %s", series_id, exc)
        try:
            _s = db.get(Series, series_id)
            if _s and _s.generation_status.startswith("generating"):
                _s.generation_status = "failed"
                _s.generation_error = str(exc)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@router.post("/{series_id}/generate", status_code=202)
def generate_descriptions(
    series_id: str,
    body: GenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> SeriesDetail:
    s = db.get(Series, series_id)
    if not s:
        raise HTTPException(status_code=404, detail="Series not found")
    if not body.include_images and not body.hint:
        raise HTTPException(status_code=400, detail="Hint is required when not including images")
    if body.include_images and not s.images:
        raise HTTPException(status_code=400, detail="Series has no images")
    if s.generation_status in ("generating_draft", "generating_full"):
        raise HTTPException(status_code=409, detail="Generation already in progress")

    settings = get_or_create_settings(db)
    provider_name = body.provider or settings.default_provider
    from app.config import get_config

    api_key = _get_api_key(settings, provider_name)
    if not api_key and not get_config().fake_ai:
        raise HTTPException(status_code=400, detail=f"API key for {provider_name} not configured")

    s.generation_status = "generating_draft"
    s.generation_error = None
    db.commit()

    background_tasks.add_task(_generate_variants_background, series_id, body.model_dump())
    return series_to_detail(s, db)


@router.post("/{series_id}/generate-full", status_code=202)
def generate_full(
    series_id: str,
    body: GenerateFullRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> SeriesDetail:
    s = db.get(Series, series_id)
    if not s:
        raise HTTPException(status_code=404, detail="Series not found")
    if not body.description.strip():
        raise HTTPException(status_code=400, detail="description is required")
    if s.generation_status in ("generating_draft", "generating_full"):
        raise HTTPException(status_code=409, detail="Generation already in progress")

    # Validate variant_id upfront so we can return 404 synchronously.
    if body.variant_id:
        existing = db.get(AIVariant, body.variant_id)
        if not existing or existing.series_id != series_id:
            raise HTTPException(status_code=404, detail="Variant not found")

    settings = get_or_create_settings(db)
    provider_name = body.provider or settings.default_provider
    from app.config import get_config

    api_key = _get_api_key(settings, provider_name)
    if not api_key and not get_config().fake_ai:
        raise HTTPException(status_code=400, detail=f"API key for {provider_name} not configured")

    s.generation_status = "generating_full"
    s.generation_error = None
    db.commit()

    background_tasks.add_task(_generate_full_background, series_id, body.model_dump())
    return series_to_detail(s, db)


@variants_router.delete("/{variant_id}")
def delete_variant(
    variant_id: str,
    cascade: bool = False,
    db: Session = Depends(get_db),
) -> SeriesDetail:
    from sqlalchemy import select as _select

    from app.models import Post

    v = db.get(AIVariant, variant_id)
    if not v or v.deleted_at is not None:
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

    dependents = db.scalars(
        _select(AIVariant).where(
            AIVariant.draft_id == variant_id,
            AIVariant.deleted_at.is_(None),
        )
    ).all()

    if dependents and not cascade:
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    f"This draft has {len(dependents)} dependent full variant"
                    f"{'s' if len(dependents) != 1 else ''} that will also be deleted."
                ),
                "cascade_required": True,
                "dependent_count": len(dependents),
            },
        )

    if dependents and cascade:
        dep_ids = [d.id for d in dependents]
        dep_used = (
            db.scalar(
                _select(Post.id)
                .where(Post.variant_id.in_(dep_ids), Post.deleted_at.is_(None))
                .limit(1)
            )
            is not None
        )
        if dep_used:
            raise HTTPException(
                status_code=409,
                detail="Cannot delete: a dependent full variant is used in posts",
            )
        for dep in dependents:
            dep.deleted_at = datetime.now(UTC)

    series = v.series
    if series.chosen_variant_id == variant_id:
        series.chosen_variant_id = None
    v.deleted_at = datetime.now(UTC)
    db.commit()
    return series_to_detail(series, db)


@variants_router.patch("/{variant_id}")
def update_variant_semantic(
    variant_id: str,
    body: AIVariantSemanticUpdate,
    db: Session = Depends(get_db),
) -> SeriesDetail:
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
