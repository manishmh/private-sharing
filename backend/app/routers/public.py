"""Public (client) endpoints: resolve link, device-lock access, manifest, images.

No admin auth. The device-lock decision lives in app.services.devices.
"""
import secrets
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Catalog, CatalogImage, RegisteredDevice, ShareLink
from app.schemas import (
    AccessRequest,
    AccessResponse,
    LinkMeta,
    Manifest,
    ManifestPage,
)
from app.services import devices, watermark

router = APIRouter(prefix="/api/v", tags=["public"])

# httpOnly cookie name — third identity source so clearing IndexedDB alone
# doesn't reset a device. Combined client-side into the device_id.
_COOKIE = "vault_dev"


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else ""


def _link_status(link: ShareLink) -> str:
    if link.revoked:
        return "revoked"
    if link.expires_at is not None and link.expires_at < datetime.now(timezone.utc):
        return "expired"
    return "active"


def _full_device_id(base_device_id: str, request: Request) -> str:
    """Combine the client device_id with the httpOnly cookie as an extra factor."""
    cookie_val = request.cookies.get(_COOKIE, "")
    if not cookie_val:
        return base_device_id
    return f"{base_device_id}.{cookie_val[:8]}"


def _set_cookie(response: Response, request: Request) -> None:
    if not request.cookies.get(_COOKIE):
        response.set_cookie(
            _COOKIE,
            secrets.token_hex(16),
            httponly=True,
            samesite="lax",
            secure=settings.cookie_secure,  # HTTPS-only in production
            max_age=60 * 60 * 24 * 365 * 5,  # 5 years
        )


@router.get("/{token}", response_model=LinkMeta)
def resolve_link(token: str, request: Request, response: Response,
                 db: Session = Depends(get_db)) -> LinkMeta:
    """Resolve link metadata and set the identity cookie. No access decision here."""
    _set_cookie(response, request)
    link = db.get(ShareLink, token)
    if link is None:
        return LinkMeta(token=token, slug="", title="", page_count=0, status="not_found")
    catalog = db.get(Catalog, link.catalog_id)
    return LinkMeta(
        token=token,
        slug=link.slug,
        title=catalog.title if catalog else "",
        page_count=catalog.page_count if catalog else 0,
        status=_link_status(link),
    )


@router.post("/{token}/access", response_model=AccessResponse)
def access_link(token: str, body: AccessRequest, request: Request, response: Response,
                db: Session = Depends(get_db)) -> AccessResponse:
    """Run the device-lock decision; register the device when appropriate."""
    _set_cookie(response, request)
    link = db.get(ShareLink, token)
    if link is None:
        return AccessResponse(status="blocked", reason="Link not found")

    device_id = _full_device_id(body.device_id, request)
    ua = request.headers.get("user-agent", "")

    ctx = devices.AccessContext(
        device_id=device_id,
        fingerprint_hash=body.fingerprint_hash,
        user_agent=ua,
        ip=_client_ip(request),
    )
    decision = devices.decide_access(db, link, ctx)

    catalog = db.get(Catalog, link.catalog_id)
    return AccessResponse(
        status=decision.status,
        reason=decision.reason,
        title=catalog.title if catalog else None,
        page_count=catalog.page_count if catalog else None,
    )


def _require_active_registered(db: Session, token: str, request: Request):
    """Return the link if it's active AND the calling device is registered, else None.

    The client passes its base device id in the X-Device-Id header; we reconstruct
    the same server-side identity (base + cookie) used at registration time.
    """
    link = db.get(ShareLink, token)
    if link is None or _link_status(link) != "active":
        return None
    base = request.headers.get("x-device-id", "")
    if not base:
        return None
    device_id = _full_device_id(base, request)
    # The calling browser must be a registered device for this link.
    device = db.scalar(
        select(RegisteredDevice).where(
            RegisteredDevice.token == token,
            RegisteredDevice.device_id == device_id,
        )
    )
    if device is None:
        return None
    return link


@router.get("/{token}/manifest", response_model=Manifest)
def manifest(token: str, request: Request, db: Session = Depends(get_db)):
    link = _require_active_registered(db, token, request)
    if link is None:
        return JSONResponse(status_code=403, content={"detail": "Link not active"})
    catalog = db.get(Catalog, link.catalog_id)
    images = db.scalars(
        select(CatalogImage).where(CatalogImage.catalog_id == catalog.id)
        .order_by(CatalogImage.page_index)
    ).all()
    return Manifest(
        token=token,
        title=catalog.title,
        page_count=catalog.page_count,
        pages=[ManifestPage(page_index=i.page_index, width=i.width, height=i.height) for i in images],
    )


@router.get("/{token}/page/{page_index}.webp")
def page_image(token: str, page_index: int, request: Request, db: Session = Depends(get_db)):
    """Serve the per-client watermarked page image (cached on disk per token)."""
    link = _require_active_registered(db, token, request)
    if link is None:
        return JSONResponse(status_code=403, content={"detail": "Link not active"})

    catalog = db.get(Catalog, link.catalog_id)
    image = db.scalar(
        select(CatalogImage).where(
            CatalogImage.catalog_id == catalog.id,
            CatalogImage.page_index == page_index,
        )
    )
    if image is None:
        return JSONResponse(status_code=404, content={"detail": "Page not found"})

    out = watermark.generate_watermarked(
        master_path=image.file_path,
        token=token,
        page_index=page_index,
        client_label=link.client_label,
        timestamp=int(time.time()),
        opacity=catalog.wm_opacity,
        font_scale=catalog.wm_font_scale,
        suffix=catalog.wm_text_suffix,
    )
    # Private, no shared caching: each client's image is unique & access-controlled.
    return FileResponse(
        str(out),
        media_type="image/webp",
        headers={"Cache-Control": "private, max-age=0, no-store"},
    )
