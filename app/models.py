import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, default="")
    name_ru: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    series: Mapped[list["Series"]] = relationship("Series", back_populates="collection")


class Series(Base):
    __tablename__ = "series"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    original_folder_name: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String, default="")
    title: Mapped[str] = mapped_column(String, default="")
    title_ru: Mapped[str] = mapped_column(String, default="")
    description_en: Mapped[str] = mapped_column(Text, default="")
    description_ru: Mapped[str] = mapped_column(Text, default="")
    tags_instagram: Mapped[str] = mapped_column(Text, default="[]")
    tags_telegram: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String, default="new", index=True)
    collection_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("collections.id"), nullable=True, index=True
    )
    collection_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    collection_number: Mapped[str | None] = mapped_column(String, nullable=True)
    chosen_variant_id: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    generation_status: Mapped[str] = mapped_column(String, default="idle")
    generation_error: Mapped[str | None] = mapped_column(String, nullable=True)

    collection: Mapped["Collection | None"] = relationship("Collection", back_populates="series")
    images: Mapped[list["Image"]] = relationship(
        "Image",
        back_populates="series",
        cascade="all, delete-orphan",
        order_by="Image.order_index",
    )
    ai_variants: Mapped[list["AIVariant"]] = relationship(
        "AIVariant",
        back_populates="series",
        cascade="all, delete-orphan",
    )
    posts: Mapped[list["Post"]] = relationship(
        "Post",
        back_populates="series",
        cascade="all, delete-orphan",
        order_by="Post.created_at",
    )


class Image(Base):
    __tablename__ = "images"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    series_id: Mapped[str] = mapped_column(
        String, ForeignKey("series.id", ondelete="CASCADE"), index=True
    )
    r2_key: Mapped[str] = mapped_column(String)
    original_filename: Mapped[str] = mapped_column(String)
    original_created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="pending", index=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)

    series: Mapped["Series"] = relationship("Series", back_populates="images")
    post_images: Mapped[list["PostImage"]] = relationship("PostImage", back_populates="image")


class PostImage(Base):
    __tablename__ = "post_images"

    post_id: Mapped[str] = mapped_column(
        String, ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True
    )
    image_id: Mapped[str] = mapped_column(
        String, ForeignKey("images.id", ondelete="CASCADE"), primary_key=True
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    post: Mapped["Post"] = relationship("Post", back_populates="post_images")
    image: Mapped["Image"] = relationship("Image", back_populates="post_images")


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    series_id: Mapped[str] = mapped_column(
        String, ForeignKey("series.id", ondelete="CASCADE"), index=True
    )
    platform: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String, default="draft", index=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    external_post_id: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    collection_line: Mapped[str | None] = mapped_column(String, nullable=True)
    collection_line_ru: Mapped[str | None] = mapped_column(String, nullable=True)
    title_ru: Mapped[str | None] = mapped_column(String, nullable=True)
    seo: Mapped[str | None] = mapped_column(Text, nullable=True)
    variant_id: Mapped[str | None] = mapped_column(String, nullable=True)
    post_url: Mapped[str | None] = mapped_column(String, nullable=True)

    series: Mapped["Series"] = relationship("Series", back_populates="posts")
    post_images: Mapped[list["PostImage"]] = relationship(
        "PostImage",
        back_populates="post",
        cascade="all, delete-orphan",
        order_by="PostImage.order_index",
    )
    story: Mapped["Story | None"] = relationship(
        "Story", back_populates="post", uselist=False, cascade="all, delete-orphan", lazy="joined"
    )


class Story(Base):
    __tablename__ = "stories"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    post_id: Mapped[str] = mapped_column(
        String, ForeignKey("posts.id", ondelete="CASCADE"), unique=True, index=True
    )
    status: Mapped[str] = mapped_column(String, default="draft")
    # draft | rendered | posted | failed

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    rendered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    platform_result_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    post: Mapped["Post"] = relationship("Post", back_populates="story")
    frames: Mapped[list["StoryFrame"]] = relationship(
        "StoryFrame",
        back_populates="story",
        cascade="all, delete-orphan",
        order_by="StoryFrame.position",
    )


class StoryFrame(Base):
    __tablename__ = "story_frames"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    story_id: Mapped[str] = mapped_column(
        String, ForeignKey("stories.id", ondelete="CASCADE"), index=True
    )

    position: Mapped[int] = mapped_column(Integer)
    frame_type: Mapped[str] = mapped_column(String)
    # image | text

    source_image_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("images.id", ondelete="SET NULL"), nullable=True
    )

    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    background_mode: Mapped[str] = mapped_column(String, default="image_blur_dim")
    # image_clean | image_blur_dim | solid_dark | solid_light | solid_accent

    text_color: Mapped[str] = mapped_column(String, default="#ffffff")
    # #ffffff | #0e0e10 | #f5e6d3 | #b8501f | #9ab2c7

    font_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # None = use renderer default (64); range 32-120

    text_align: Mapped[str] = mapped_column(String, default="middle")
    # top | middle | bottom

    title_position: Mapped[str] = mapped_column(String, default="bottom")
    # top | bottom

    text_halign: Mapped[str] = mapped_column(String, default="center")
    # left | center | right

    rendered_url: Mapped[str | None] = mapped_column(String, nullable=True)
    rendered_storage_key: Mapped[str | None] = mapped_column(String, nullable=True)

    platform_frame_id: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    story: Mapped["Story"] = relationship("Story", back_populates="frames")


class AIVariant(Base):
    __tablename__ = "ai_variants"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    series_id: Mapped[str] = mapped_column(
        String, ForeignKey("series.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String, default="")
    title_ru: Mapped[str] = mapped_column(String, default="")
    description_en: Mapped[str] = mapped_column(Text, default="")
    description_ru: Mapped[str] = mapped_column(Text, default="")
    tags_instagram: Mapped[str] = mapped_column(Text, default="[]")
    tags_telegram: Mapped[str] = mapped_column(Text, default="[]")
    hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("ai_variants.id", ondelete="CASCADE"), nullable=True
    )
    instagram_seo: Mapped[str | None] = mapped_column(Text, nullable=True)
    pinterest_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    pinterest_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    pinterest_board: Mapped[str | None] = mapped_column(Text, nullable=True)
    archive_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    series: Mapped["Series"] = relationship("Series", back_populates="ai_variants")


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    anthropic_api_key: Mapped[str] = mapped_column(String, default="")
    openai_api_key: Mapped[str] = mapped_column(String, default="")
    google_api_key: Mapped[str] = mapped_column(String, default="")
    default_provider: Mapped[str] = mapped_column(String, default="anthropic")
    anthropic_default_model: Mapped[str] = mapped_column(String, default="")
    openai_default_model: Mapped[str] = mapped_column(String, default="")
    google_default_model: Mapped[str] = mapped_column(String, default="")
    deepseek_api_key: Mapped[str] = mapped_column(String, default="")
    deepseek_default_model: Mapped[str] = mapped_column(String, default="")
    openrouter_api_key: Mapped[str] = mapped_column(String, default="")
    openrouter_default_model: Mapped[str] = mapped_column(String, default="")
    telegram_bot_token: Mapped[str] = mapped_column(String, default="")
    telegram_channel_id: Mapped[str] = mapped_column(String, default="")
    telegram_api_id: Mapped[str] = mapped_column(String, default="")
    telegram_api_hash: Mapped[str] = mapped_column(String, default="")
    telegram_session_string: Mapped[str] = mapped_column(Text, default="")
    instagram_access_token: Mapped[str] = mapped_column(String, default="")
    instagram_user_id: Mapped[str] = mapped_column(String, default="")
    facebook_page_id: Mapped[str] = mapped_column(String, default="")
    facebook_page_access_token: Mapped[str] = mapped_column(String, default="")
    pinterest_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    pinterest_default_board_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    pinterest_board_map: Mapped[str | None] = mapped_column(Text, nullable=True)
    r2_endpoint: Mapped[str] = mapped_column(String, default="")
    r2_access_key: Mapped[str] = mapped_column(String, default="")
    r2_secret_key: Mapped[str] = mapped_column(String, default="")
    r2_bucket: Mapped[str] = mapped_column(String, default="")
    r2_public_base_url: Mapped[str] = mapped_column(String, default="")
