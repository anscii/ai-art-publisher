from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

# ── Settings ──────────────────────────────────────────────────────────────────


class SettingsResponse(BaseModel):
    anthropic_api_key: str
    openai_api_key: str
    google_api_key: str
    default_provider: str
    default_model: str
    telegram_bot_token: str
    telegram_channel_id: str
    instagram_access_token: str
    instagram_user_id: str
    facebook_page_id: str
    r2_endpoint: str
    r2_access_key: str
    r2_secret_key: str
    r2_bucket: str
    r2_public_base_url: str


class SettingsUpdate(BaseModel):
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    google_api_key: str | None = None
    default_provider: str | None = None
    default_model: str | None = None
    telegram_bot_token: str | None = None
    telegram_channel_id: str | None = None
    instagram_access_token: str | None = None
    instagram_user_id: str | None = None
    facebook_page_id: str | None = None
    r2_endpoint: str | None = None
    r2_access_key: str | None = None
    r2_secret_key: str | None = None
    r2_bucket: str | None = None
    r2_public_base_url: str | None = None


# ── Images ────────────────────────────────────────────────────────────────────


class ImageResponse(BaseModel):
    id: str
    series_id: str
    r2_key: str
    original_filename: str
    original_created_at: datetime | None
    order_index: int
    status: str
    uploaded_at: datetime
    deleted_at: datetime | None
    public_url: str


class ImageStatusUpdate(BaseModel):
    status: str


class RegisterImageBody(BaseModel):
    r2_key: str
    original_filename: str
    original_created_at: datetime | None = None


class MoveImageBody(BaseModel):
    target_series_id: str


class ReorderImagesBody(BaseModel):
    image_ids: list[str]


# ── AI Variants ───────────────────────────────────────────────────────────────


class AIVariantResponse(BaseModel):
    id: str
    series_id: str
    provider: str
    model: str
    title: str
    description_en: str
    description_ru: str
    tags_instagram: list[str]
    tags_telegram: list[str]
    generated_at: datetime


# ── Series ────────────────────────────────────────────────────────────────────


class SeriesCreate(BaseModel):
    original_folder_name: str | None = None
    title: str = ""
    status: str = "new"
    created_at: datetime | None = None


class SeriesUpdate(BaseModel):
    title: str | None = None
    description_en: str | None = None
    description_ru: str | None = None
    tags_instagram: list[str] | None = None
    tags_telegram: list[str] | None = None
    status: str | None = None
    notes: str | None = None
    needs_review: bool | None = None
    review_reason: str | None = None


class SeriesListItem(BaseModel):
    id: str
    original_folder_name: str | None
    title: str
    status: str
    needs_review: bool
    created_at: datetime
    scheduled_at: datetime | None
    posted_to_telegram_at: datetime | None
    posted_to_instagram_at: datetime | None
    posted_to_facebook_at: datetime | None
    image_count: int
    cover_url: str | None


class SeriesListResponse(BaseModel):
    items: list[SeriesListItem]
    total: int
    page: int
    limit: int


class SeriesDetail(BaseModel):
    id: str
    original_folder_name: str | None
    title: str
    description_en: str
    description_ru: str
    tags_instagram: list[str]
    tags_telegram: list[str]
    status: str
    notes: str
    needs_review: bool
    review_reason: str
    created_at: datetime
    scheduled_at: datetime | None
    scheduled_targets: list[str]
    posted_to_telegram_at: datetime | None
    posted_to_instagram_at: datetime | None
    posted_to_facebook_at: datetime | None
    images: list[ImageResponse]
    ai_variants: list[AIVariantResponse]


# ── Generation ────────────────────────────────────────────────────────────────


class GenerateRequest(BaseModel):
    provider: str | None = None
    model: str | None = None
    hint: str | None = None
    include_images: bool = False


# ── Scheduling ────────────────────────────────────────────────────────────────


class ScheduleRequest(BaseModel):
    datetime_utc: datetime
    targets: list[str]


class QueueItem(BaseModel):
    series_id: str
    title: str
    original_folder_name: str | None
    scheduled_at: datetime
    targets: list[str]


# ── Posting ───────────────────────────────────────────────────────────────────


class PostResult(BaseModel):
    success: bool
    message: str


# ── Trash ─────────────────────────────────────────────────────────────────────


class TrashSeries(BaseModel):
    id: str
    title: str
    original_folder_name: str | None
    deleted_at: datetime
    image_count: int
    cover_url: str | None


class TrashImage(BaseModel):
    id: str
    series_id: str
    series_title: str
    original_filename: str
    public_url: str
    deleted_at: datetime


class TrashResponse(BaseModel):
    series: list[TrashSeries]
    images: list[TrashImage]
