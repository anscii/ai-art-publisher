import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Series(Base):
    __tablename__ = "series"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    original_folder_name: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, default="")
    description_en: Mapped[str] = mapped_column(Text, default="")
    description_ru: Mapped[str] = mapped_column(Text, default="")
    tags_instagram: Mapped[str] = mapped_column(Text, default="[]")
    tags_telegram: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String, default="new")
    notes: Mapped[str] = mapped_column(Text, default="")
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    review_reason: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scheduled_targets: Mapped[str] = mapped_column(Text, default="[]")
    posted_to_telegram_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    posted_to_instagram_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    posted_to_facebook_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

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


class Image(Base):
    __tablename__ = "images"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    series_id: Mapped[str] = mapped_column(String, ForeignKey("series.id", ondelete="CASCADE"))
    r2_key: Mapped[str] = mapped_column(String)
    original_filename: Mapped[str] = mapped_column(String)
    original_created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="pending")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    series: Mapped["Series"] = relationship("Series", back_populates="images")


class AIVariant(Base):
    __tablename__ = "ai_variants"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    series_id: Mapped[str] = mapped_column(String, ForeignKey("series.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String, default="")
    description_en: Mapped[str] = mapped_column(Text, default="")
    description_ru: Mapped[str] = mapped_column(Text, default="")
    tags_instagram: Mapped[str] = mapped_column(Text, default="[]")
    tags_telegram: Mapped[str] = mapped_column(Text, default="[]")
    hint: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    telegram_bot_token: Mapped[str] = mapped_column(String, default="")
    telegram_channel_id: Mapped[str] = mapped_column(String, default="")
    instagram_access_token: Mapped[str] = mapped_column(String, default="")
    instagram_user_id: Mapped[str] = mapped_column(String, default="")
    facebook_page_id: Mapped[str] = mapped_column(String, default="")
    facebook_page_access_token: Mapped[str] = mapped_column(String, default="")
    r2_endpoint: Mapped[str] = mapped_column(String, default="")
    r2_access_key: Mapped[str] = mapped_column(String, default="")
    r2_secret_key: Mapped[str] = mapped_column(String, default="")
    r2_bucket: Mapped[str] = mapped_column(String, default="")
    r2_public_base_url: Mapped[str] = mapped_column(String, default="")
