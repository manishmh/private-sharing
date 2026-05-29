"""Pydantic request/response models."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---- Admin: catalogs ----
class CatalogSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    slug: str
    title: str
    source_pdf_name: str
    page_count: int
    created_at: datetime
    link_count: int = 0


class CatalogImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    page_index: int
    width: int
    height: int


# ---- Admin: links ----
class LinkCreate(BaseModel):
    client_label: str = Field(min_length=1, max_length=120)
    max_devices: int = Field(default=1, ge=1, le=999)
    expires_at: datetime | None = None  # None == never


class LinkUpdate(BaseModel):
    max_devices: int | None = Field(default=None, ge=1, le=999)
    expires_at: datetime | None = None
    clear_expiry: bool = False  # set expires_at back to NULL (never)
    revoked: bool | None = None


class LinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    token: str
    catalog_id: int
    slug: str
    client_label: str
    max_devices: int
    expires_at: datetime | None
    revoked: bool
    created_at: datetime
    registered_count: int = 0
    public_url: str = ""


class CatalogDetail(CatalogSummary):
    images: list[CatalogImageOut] = []
    links: list[LinkOut] = []


# ---- Admin: analytics (sanitized for client-facing UI) ----
class DeviceAnalytics(BaseModel):
    friendly_name: str
    approx_location: str
    open_count: int
    first_seen: datetime
    last_seen: datetime


class LinkAnalytics(BaseModel):
    token: str
    client_label: str
    max_devices: int
    registered_count: int
    revoked: bool
    expires_at: datetime | None
    total_opens: int
    blocked_attempts: int
    revoked_attempts: int
    devices: list[DeviceAnalytics]


class DecodeResult(BaseModel):
    found: bool
    payload: str | None = None
    token: str | None = None
    client_label: str | None = None
    timestamp: int | None = None


# ---- Public ----
class LinkMeta(BaseModel):
    token: str
    slug: str
    title: str
    page_count: int
    status: str  # active | revoked | expired | not_found


class AccessRequest(BaseModel):
    device_id: str = Field(min_length=4, max_length=128)
    fingerprint_hash: str = Field(default="", max_length=128)


class AccessResponse(BaseModel):
    status: str        # allowed | blocked | expired | revoked
    reason: str
    title: str | None = None
    page_count: int | None = None


class ManifestPage(BaseModel):
    page_index: int
    width: int
    height: int


class Manifest(BaseModel):
    token: str
    title: str
    page_count: int
    pages: list[ManifestPage]
