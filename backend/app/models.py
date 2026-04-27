from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _id() -> str:
    return uuid.uuid4().hex[:16]


def _now() -> dt.datetime:
    return dt.datetime.utcnow()


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String(255))
    owner_type: Mapped[str] = mapped_column(String(32), default="empresa")
    website: Mapped[str | None] = mapped_column(String(512))
    full_name: Mapped[str | None] = mapped_column(String(255))
    cv_text: Mapped[str | None] = mapped_column(Text)
    research: Mapped[dict | None] = mapped_column(JSON)
    gaps: Mapped[dict | None] = mapped_column(JSON)
    competitors: Mapped[list | None] = mapped_column(JSON)
    products: Mapped[list | None] = mapped_column(JSON)
    icp: Mapped[dict | None] = mapped_column(JSON)
    personas: Mapped[list | None] = mapped_column(JSON)
    brand_kit: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    leads = relationship("Lead", back_populates="project", cascade="all, delete-orphan")
    campaigns = relationship("Campaign", back_populates="project", cascade="all, delete-orphan")
    automations = relationship("Automation", back_populates="project", cascade="all, delete-orphan")


class Lead(Base):
    __tablename__ = "leads"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String(255))
    website: Mapped[str | None] = mapped_column(String(512))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(64))
    address: Mapped[str | None] = mapped_column(String(512))
    city: Mapped[str | None] = mapped_column(String(128))
    country: Mapped[str | None] = mapped_column(String(128))
    sector: Mapped[str | None] = mapped_column(String(128))
    score: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)

    project = relationship("Project", back_populates="leads")


class Campaign(Base):
    __tablename__ = "campaigns"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String(255))
    goal: Mapped[str | None] = mapped_column(String(255))
    channels: Mapped[list | None] = mapped_column(JSON)
    selectors: Mapped[dict | None] = mapped_column(JSON)  # qué piezas se generan
    brief: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="draft")  # draft|approved|scheduled|sent
    prediction: Mapped[dict | None] = mapped_column(JSON)
    roi: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)

    project = relationship("Project", back_populates="campaigns")
    assets = relationship("Asset", back_populates="campaign", cascade="all, delete-orphan")
    sends = relationship("EmailSend", back_populates="campaign", cascade="all, delete-orphan")


class Asset(Base):
    __tablename__ = "assets"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"))
    kind: Mapped[str] = mapped_column(String(32))  # slogan|logo|brochure|newsletter|banner|post|video|infographic|email
    title: Mapped[str | None] = mapped_column(String(255))
    text: Mapped[str | None] = mapped_column(Text)
    image_data: Mapped[str | None] = mapped_column(Text)  # base64 PNG
    meta: Mapped[dict | None] = mapped_column(JSON)  # platform, variant, locale, etc.
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    scheduled_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)

    campaign = relationship("Campaign", back_populates="assets")


class EmailSend(Base):
    __tablename__ = "email_sends"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"))
    lead_id: Mapped[str | None] = mapped_column(ForeignKey("leads.id"))
    to_email: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(512))
    body_html: Mapped[str] = mapped_column(Text)
    variant: Mapped[str] = mapped_column(String(8), default="A")
    sent_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)
    opened_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    open_count: Mapped[int] = mapped_column(Integer, default=0)
    click_count: Mapped[int] = mapped_column(Integer, default=0)
    last_click_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    bounced: Mapped[bool] = mapped_column(Boolean, default=False)
    unsubscribed: Mapped[bool] = mapped_column(Boolean, default=False)

    campaign = relationship("Campaign", back_populates="sends")


class EmailEvent(Base):
    __tablename__ = "email_events"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    send_id: Mapped[str] = mapped_column(ForeignKey("email_sends.id"))
    kind: Mapped[str] = mapped_column(String(16))  # open|click|unsubscribe|bounce
    url: Mapped[str | None] = mapped_column(String(1024))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    ip: Mapped[str | None] = mapped_column(String(64))
    at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


class Automation(Base):
    __tablename__ = "automations"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String(255))
    trigger_kind: Mapped[str] = mapped_column(String(32))  # schedule|comment|like|new_lead
    trigger_config: Mapped[dict | None] = mapped_column(JSON)
    action_kind: Mapped[str] = mapped_column(String(32))  # publish_post|reply_comment|send_email|tag_lead
    action_config: Mapped[dict | None] = mapped_column(JSON)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run: Mapped[dt.datetime | None] = mapped_column(DateTime)
    runs: Mapped[list | None] = mapped_column(JSON, default=list)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)

    project = relationship("Project", back_populates="automations")


class ProviderKey(Base):
    __tablename__ = "provider_keys"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # provider id
    api_key: Mapped[str] = mapped_column(Text)
    base_url: Mapped[str | None] = mapped_column(String(512))
    models: Mapped[dict | None] = mapped_column(JSON)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    extra: Mapped[dict | None] = mapped_column(JSON)  # from_email, smtp_user, etc.
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class TaskPreference(Base):
    __tablename__ = "task_preferences"
    task: Mapped[str] = mapped_column(String(32), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(64))


class AILog(Base):
    __tablename__ = "ai_logs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    project_id: Mapped[str | None] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(64))
    operation: Mapped[str] = mapped_column(String(64))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    images: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


def init_db():
    from . import db as _db
    from sqlalchemy import text, inspect
    Base.metadata.create_all(bind=_db.engine)
    # Migraciones ligeras sobre SQLite: añadir columnas nuevas si faltan
    try:
        with _db.engine.begin() as conn:
            insp = inspect(conn)
            cols = {c["name"] for c in insp.get_columns("provider_keys")}
            if "extra" not in cols:
                conn.execute(text("ALTER TABLE provider_keys ADD COLUMN extra JSON"))
    except Exception:
        pass
