"""Admin endpoints: upload catalogs, mint/manage links, analytics, decode watermark.

NOTE: admin auth is currently DISABLED (open console) per request. The password
gate logic is kept in app.deps.require_admin — re-enable by adding
`dependencies=[Depends(require_admin)]` back to the router below. PRODUCTION must
use real authentication.
"""
import io
import shutil

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import (
    AccessEvent,
    Catalog,
    CatalogImage,
    RegisteredDevice,
    ShareLink,
)
from app.schemas import (
    CatalogDetail,
    CatalogImageOut,
    CatalogSummary,
    DecodeResult,
    DeviceAnalytics,
    LinkAnalytics,
    LinkCreate,
    LinkOut,
    LinkUpdate,
)
from app.services import pdf, tokens, watermark

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _public_url(link: ShareLink) -> str:
    return f"/v/{link.slug}-{link.token}"


def _registered_count(db: Session, token: str) -> int:
    return db.scalar(
        select(func.count()).select_from(RegisteredDevice).where(RegisteredDevice.token == token)
    ) or 0


def _link_out(db: Session, link: ShareLink) -> LinkOut:
    out = LinkOut.model_validate(link)
    out.registered_count = _registered_count(db, link.token)
    out.public_url = _public_url(link)
    return out


# --------------------------------------------------------------------------- #
# Catalogs
# --------------------------------------------------------------------------- #
@router.post("/catalogs", response_model=CatalogDetail)
async def create_catalog(
    title: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> CatalogDetail:
    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    base_slug = pdf.slugify(title)
    slug = pdf.unique_slug(
        base_slug,
        exists=lambda s: db.scalar(select(Catalog).where(Catalog.slug == s)) is not None,
    )

    try:
        pages = pdf.extract_pdf(pdf_bytes, slug)
    except Exception as exc:  # noqa: BLE001 - surface a clean 400 to the caller
        raise HTTPException(status_code=400, detail=f"Could not read PDF: {exc}") from exc

    if not pages:
        raise HTTPException(status_code=400, detail="PDF has no pages")

    catalog = Catalog(
        slug=slug,
        title=title,
        source_pdf_name=file.filename or "upload.pdf",
        page_count=len(pages),
    )
    db.add(catalog)
    db.flush()  # assign catalog.id

    for p in pages:
        db.add(CatalogImage(
            catalog_id=catalog.id,
            page_index=p.page_index,
            file_path=p.file_path,
            width=p.width,
            height=p.height,
        ))
    db.commit()
    db.refresh(catalog)
    return _catalog_detail(db, catalog)


@router.get("/catalogs", response_model=list[CatalogSummary])
def list_catalogs(db: Session = Depends(get_db)) -> list[CatalogSummary]:
    catalogs = db.scalars(select(Catalog).order_by(Catalog.created_at.desc())).all()
    result: list[CatalogSummary] = []
    for c in catalogs:
        summary = CatalogSummary.model_validate(c)
        summary.link_count = db.scalar(
            select(func.count()).select_from(ShareLink).where(ShareLink.catalog_id == c.id)
        ) or 0
        result.append(summary)
    return result


def _catalog_detail(db: Session, catalog: Catalog) -> CatalogDetail:
    detail = CatalogDetail.model_validate(catalog)
    detail.link_count = len(catalog.links)
    detail.images = [CatalogImageOut.model_validate(i) for i in catalog.images]
    detail.links = [_link_out(db, link) for link in
                    sorted(catalog.links, key=lambda x: x.created_at, reverse=True)]
    return detail


@router.get("/catalogs/{catalog_id}", response_model=CatalogDetail)
def get_catalog(catalog_id: int, db: Session = Depends(get_db)) -> CatalogDetail:
    catalog = db.get(Catalog, catalog_id)
    if catalog is None:
        raise HTTPException(status_code=404, detail="Catalog not found")
    return _catalog_detail(db, catalog)


@router.delete("/catalogs/{catalog_id}")
def delete_catalog(catalog_id: int, db: Session = Depends(get_db)) -> dict:
    """Delete a catalog: its links, devices and events cascade in the DB; the
    on-disk master images and per-link watermark caches are removed too."""
    catalog = db.get(Catalog, catalog_id)
    if catalog is None:
        raise HTTPException(status_code=404, detail="Catalog not found")

    slug = catalog.slug
    link_tokens = [link.token for link in catalog.links]

    db.delete(catalog)  # ORM + FK cascade removes images, links, devices, events
    db.commit()

    # Remove on-disk artifacts.
    shutil.rmtree(settings.masters_dir / slug, ignore_errors=True)
    for tok in link_tokens:
        shutil.rmtree(settings.watermark_dir / tok, ignore_errors=True)

    return {"deleted": catalog_id, "slug": slug, "links_removed": len(link_tokens)}


# --------------------------------------------------------------------------- #
# Links
# --------------------------------------------------------------------------- #
@router.post("/catalogs/{catalog_id}/links", response_model=LinkOut)
def create_link(catalog_id: int, body: LinkCreate, db: Session = Depends(get_db)) -> LinkOut:
    catalog = db.get(Catalog, catalog_id)
    if catalog is None:
        raise HTTPException(status_code=404, detail="Catalog not found")

    # Generate a unique 6-char token.
    token = tokens.generate_token()
    while db.get(ShareLink, token) is not None:
        token = tokens.generate_token()

    link = ShareLink(
        token=token,
        catalog_id=catalog.id,
        slug=catalog.slug,
        max_devices=body.max_devices,
        client_label=body.client_label,
        expires_at=body.expires_at,
        revoked=False,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return _link_out(db, link)


@router.patch("/links/{token}", response_model=LinkOut)
def update_link(token: str, body: LinkUpdate, db: Session = Depends(get_db)) -> LinkOut:
    link = db.get(ShareLink, token)
    if link is None:
        raise HTTPException(status_code=404, detail="Link not found")

    if body.max_devices is not None:
        current = _registered_count(db, token)
        # Never silently decrease below the number of devices already registered.
        if body.max_devices < current:
            raise HTTPException(
                status_code=409,
                detail=(f"Cannot set max_devices to {body.max_devices}: "
                        f"{current} device(s) already registered. "
                        f"Revoke the link or keep it >= {current}."),
            )
        link.max_devices = body.max_devices

    if body.clear_expiry:
        link.expires_at = None
    elif body.expires_at is not None:
        link.expires_at = body.expires_at

    if body.revoked is not None:
        link.revoked = body.revoked

    db.commit()
    db.refresh(link)
    return _link_out(db, link)


@router.delete("/links/{token}")
def delete_link(token: str, db: Session = Depends(get_db)) -> dict:
    """Delete a share link. An active link is revoked first (cutting off access)
    and then removed in the same transaction — no separate admin step needed. Its
    registered devices and access events cascade; the on-disk watermark cache for
    the token is removed too."""
    link = db.get(ShareLink, token)
    if link is None:
        raise HTTPException(status_code=404, detail="Link not found")

    was_active = not link.revoked
    if was_active:
        link.revoked = True  # revoke-then-delete, internally
        db.flush()

    db.delete(link)  # FK cascade removes registered_devices + access_events
    db.commit()

    shutil.rmtree(settings.watermark_dir / token, ignore_errors=True)
    return {"deleted": token, "was_active": was_active}


@router.get("/links/{token}/analytics", response_model=LinkAnalytics)
def link_analytics(token: str, db: Session = Depends(get_db)) -> LinkAnalytics:
    link = db.get(ShareLink, token)
    if link is None:
        raise HTTPException(status_code=404, detail="Link not found")

    devices = db.scalars(
        select(RegisteredDevice).where(RegisteredDevice.token == token)
        .order_by(RegisteredDevice.first_seen)
    ).all()

    # Build sanitized per-device analytics (NO raw fingerprint / UA / IP exposed).
    device_stats: list[DeviceAnalytics] = []
    for d in devices:
        cnt = db.scalar(
            select(func.count()).select_from(AccessEvent).where(
                AccessEvent.token == token,
                AccessEvent.event_type == "open",
                AccessEvent.device_id == d.device_id,
            )
        ) or 0
        device_stats.append(DeviceAnalytics(
            friendly_name=d.friendly_name,
            approx_location=d.approx_location,
            open_count=cnt,
            first_seen=d.first_seen,
            last_seen=d.last_seen,
        ))

    total_opens = db.scalar(
        select(func.count()).select_from(AccessEvent).where(
            AccessEvent.token == token, AccessEvent.event_type == "open")
    ) or 0
    blocked = db.scalar(
        select(func.count()).select_from(AccessEvent).where(
            AccessEvent.token == token, AccessEvent.event_type == "blocked")
    ) or 0
    revoked_attempts = db.scalar(
        select(func.count()).select_from(AccessEvent).where(
            AccessEvent.token == token, AccessEvent.event_type == "revoked_attempt")
    ) or 0

    return LinkAnalytics(
        token=link.token,
        client_label=link.client_label,
        max_devices=link.max_devices,
        registered_count=len(devices),
        revoked=link.revoked,
        expires_at=link.expires_at,
        total_opens=total_opens,
        blocked_attempts=blocked,
        revoked_attempts=revoked_attempts,
        devices=device_stats,
    )


# --------------------------------------------------------------------------- #
# Forensic watermark decode
# --------------------------------------------------------------------------- #
@router.post("/decode-watermark", response_model=DecodeResult)
async def decode_watermark(file: UploadFile = File(...)) -> DecodeResult:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Not an image: {exc}") from exc

    payload = watermark.decode_lsb(img)
    if not payload:
        return DecodeResult(found=False)

    parts = payload.split("|")
    token = parts[0] if len(parts) > 0 else None
    label = parts[1] if len(parts) > 1 else None
    ts = None
    if len(parts) > 2:
        try:
            ts = int(parts[2])
        except ValueError:
            ts = None
    return DecodeResult(found=True, payload=payload, token=token, client_label=label, timestamp=ts)
