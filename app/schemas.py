from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

# ── Settings ──────────────────────────────────────────────────────────────────


class SettingsResponse(BaseModel):
    anthropic_api_key: str
    openai_api_key: str
    google_api_key: str
    default_provider: str
    anthropic_default_model: str
    openai_default_model: str
    google_default_model: str
    telegram_bot_token: str
    telegram_channel_id: str
    instagram_access_token: str
    instagram_user_id: str
    facebook_page_id: str
    facebook_page_access_token: str
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
    anthropic_default_model: str | None = None
    openai_default_model: str | None = None
    google_default_model: str | None = None
    telegram_bot_token: str | None = None
    telegram_channel_id: str | None = None
    instagram_access_token: str | None = None
    instagram_user_id: str | None = None
    facebook_page_id: str | None = None
    facebook_page_access_token: str | None = None
    r2_endpoint: str | None = None
    r2_access_key: str | None = None
    r2_secret_key: str | None = None
    r2_bucket: str | None = None
    r2_public_base_url: str | None = None


# ── Collections ───────────────────────────────────────────────────────────────


class CollectionResponse(BaseModel):
    id: str
    name: str
    name_ru: str | None = None
    created_at: datetime
    series_total: int = 0
    series_by_status: dict[str, int] = {}


class CollectionCreate(BaseModel):
    name: str
    name_ru: str | None = None


class CollectionUpdate(BaseModel):
    name: str
    name_ru: str | None = None


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
    status: str  # allowed: "pending", "skip"


class RegisterImageBody(BaseModel):
    r2_key: str
    original_filename: str
    original_created_at: datetime | None = None


class MoveImageBody(BaseModel):
    target_series_id: str


class ReorderImagesBody(BaseModel):
    image_ids: list[str]


class SaveQueueBody(BaseModel):
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
    hint: str | None = None
    cost_usd: float = 0.0
    generated_at: datetime


# ── Posts ─────────────────────────────────────────────────────────────────────


class PostResponse(BaseModel):
    id: str
    series_id: str
    platform: str
    title: str
    title_ru: str
    description: str
    tags: list[str]
    collection_line: str | None
    collection_line_ru: str | None
    status: str
    scheduled_at: datetime | None
    posted_at: datetime | None
    external_post_id: str | None
    error_message: str
    created_at: datetime
    image_ids: list[str]


class PostCreate(BaseModel):
    platform: str
    title: str
    title_ru: str = ""
    description: str
    tags: list[str] = []
    image_ids: list[str]
    scheduled_at: datetime | None = None


class PostBatchCreate(BaseModel):
    platforms: list[str]
    title: str
    title_ru: str = ""
    description_telegram: str
    description_other: str
    tags_telegram: list[str] = []
    tags_other: list[str] = []
    collection_line: str | None = None
    collection_line_ru: str | None = None
    image_ids: list[str]
    scheduled_at: datetime | None = None


class PostUpdate(BaseModel):
    title: str | None = None
    title_ru: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    image_ids: list[str] | None = None
    collection_line: str | None = None
    collection_line_ru: str | None = None


class PostScheduleRequest(BaseModel):
    datetime_utc: datetime


# ── Series ────────────────────────────────────────────────────────────────────


class SeriesCreate(BaseModel):
    original_folder_name: str | None = None
    name: str = ""
    title: str = ""
    status: str = "new"
    created_at: datetime | None = None


class SeriesUpdate(BaseModel):
    name: str | None = None
    title: str | None = None
    description_en: str | None = None
    description_ru: str | None = None
    tags_instagram: list[str] | None = None
    tags_telegram: list[str] | None = None
    status: str | None = None
    collection_id: str | None = None
    collection_number: str | None = None


class CollectionRef(BaseModel):
    id: str
    name: str
    collection_index: int | None = None
    collection_number: str | None = None


class SeriesListItem(BaseModel):
    id: str
    original_folder_name: str | None
    name: str
    title: str
    status: str
    collection_name: str | None
    collection_name_ru: str | None
    collection_number: str | None
    created_at: datetime
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
    name: str
    title: str
    description_en: str
    description_ru: str
    tags_instagram: list[str]
    tags_telegram: list[str]
    status: str
    collection: CollectionRef | None
    collection_index: int | None
    collection_number: str | None
    created_at: datetime
    images: list[ImageResponse]
    ai_variants: list[AIVariantResponse]
    posts: list[PostResponse]


# ── Generation ────────────────────────────────────────────────────────────────


class GenerateRequest(BaseModel):
    provider: str | None = None
    model: str | None = None
    hint: str | None = None
    include_images: bool = False
    selected_image_ids: list[str] | None = None


# ── Scheduling (legacy queue view) ────────────────────────────────────────────


class QueueItem(BaseModel):
    post_id: str
    series_id: str
    series_name: str
    platform: str
    title: str
    scheduled_at: datetime


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
