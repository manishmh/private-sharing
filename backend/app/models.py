"""SQLAlchemy ORM models for the Vault catalog-sharing system."""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Catalog(Base):
    __tablename__ = "catalog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    source_pdf_name: Mapped[str] = mapped_column(String(255))
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    # Base watermark settings (per-link rendering reads these defaults).
    wm_opacity: Mapped[int] = mapped_column(Integer, default=72)       # 0-255 alpha
    wm_font_scale: Mapped[int] = mapped_column(Integer, default=28)    # px-ish tile font
    wm_text_suffix: Mapped[str] = mapped_column(String(60), default="CONFIDENTIAL")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    images: Mapped[list["CatalogImage"]] = relationship(
        back_populates="catalog", cascade="all, delete-orphan", order_by="CatalogImage.page_index"
    )
    links: Mapped[list["ShareLink"]] = relationship(
        back_populates="catalog", cascade="all, delete-orphan"
    )


class CatalogImage(Base):
    __tablename__ = "catalog_image"
    __table_args__ = (UniqueConstraint("catalog_id", "page_index", name="uq_catalog_page"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    catalog_id: Mapped[int] = mapped_column(ForeignKey("catalog.id", ondelete="CASCADE"), index=True)
    page_index: Mapped[int] = mapped_column(Integer)
    file_path: Mapped[str] = mapped_column(Text)  # clean master on local disk
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)

    catalog: Mapped["Catalog"] = relationship(back_populates="images")


class ShareLink(Base):
    __tablename__ = "share_link"

    # 6-char base62 token is the primary key (NOT a UUID).
    token: Mapped[str] = mapped_column(String(6), primary_key=True)
    catalog_id: Mapped[int] = mapped_column(
        ForeignKey("catalog.id", ondelete="CASCADE"), index=True
    )
    slug: Mapped[str] = mapped_column(String(120))  # denormalized for the URL
    max_devices: Mapped[int] = mapped_column(Integer, default=1)
    client_label: Mapped[str] = mapped_column(String(120))
    # NULL == never expires (the default).
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    catalog: Mapped["Catalog"] = relationship(back_populates="links")
    devices: Mapped[list["RegisteredDevice"]] = relationship(
        back_populates="link", cascade="all, delete-orphan"
    )
    events: Mapped[list["AccessEvent"]] = relationship(
        back_populates="link", cascade="all, delete-orphan"
    )


class RegisteredDevice(Base):
    """A device that has registered against a share link. Identity is per-browser:
    device_id = FingerprintJS visitorId + IndexedDB UUID + an httpOnly cookie. Each
    distinct browser consumes one of the link's device slots."""

    __tablename__ = "registered_device"
    __table_args__ = (
        UniqueConstraint("token", "device_id", name="uq_token_device"),
        Index("ix_registered_device_token", "token"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(ForeignKey("share_link.token", ondelete="CASCADE"))
    device_id: Mapped[str] = mapped_column(String(128))  # per-browser id
    fingerprint_hash: Mapped[str] = mapped_column(String(128), default="")
    friendly_name: Mapped[str] = mapped_column(String(120), default="Unknown device")
    approx_location: Mapped[str] = mapped_column(String(120), default="Local/Unknown")
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    link: Mapped["ShareLink"] = relationship(back_populates="devices")


class AccessEvent(Base):
    __tablename__ = "access_event"
    __table_args__ = (
        Index("ix_access_event_token", "token"),
        Index("ix_access_event_token_created", "token", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(ForeignKey("share_link.token", ondelete="CASCADE"))
    device_id: Mapped[str] = mapped_column(String(128), default="")
    # open | blocked | revoked_attempt
    event_type: Mapped[str] = mapped_column(String(20))
    friendly_name: Mapped[str] = mapped_column(String(120), default="")
    approx_location: Mapped[str] = mapped_column(String(120), default="")
    ip: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    link: Mapped["ShareLink"] = relationship(back_populates="events")
