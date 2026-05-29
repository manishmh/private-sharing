"""Device-locking decision logic (per-browser).

Locking is per browser: each browser produces a stable per-browser id
(FingerprintJS visitorId + IndexedDB UUID + an httpOnly cookie the backend sets).
A link allows up to `max_devices` distinct browsers; opening it from a new browser
on the same physical device consumes another slot.

Rule order (do NOT reorder): revoked -> expired -> known device -> free slot ->
blocked. A known device is checked BEFORE the limit so it is never re-blocked.
"""
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AccessEvent, RegisteredDevice, ShareLink
from app.services import geo, useragent


@dataclass
class AccessContext:
    device_id: str               # per-browser id (base + cookie)
    fingerprint_hash: str
    user_agent: str
    ip: str


@dataclass
class AccessDecision:
    status: str           # "allowed" | "blocked" | "expired" | "revoked"
    reason: str
    friendly_name: str
    approx_location: str
    registered: bool


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _log(db: Session, token: str, event_type: str, ctx: AccessContext,
         friendly: str, location: str) -> None:
    db.add(AccessEvent(
        token=token,
        device_id=ctx.device_id,
        event_type=event_type,
        friendly_name=friendly,
        approx_location=location,
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    ))


def decide_access(db: Session, link: ShareLink, ctx: AccessContext) -> AccessDecision:
    friendly = useragent.friendly_name(ctx.user_agent)
    location = geo.lookup(ctx.ip)

    # 1) Revoked.
    if link.revoked:
        _log(db, link.token, "revoked_attempt", ctx, friendly, location)
        db.commit()
        return AccessDecision("revoked", "Link revoked", friendly, location, False)

    # 2) Expired (NULL == never).
    if link.expires_at is not None and link.expires_at < _now():
        _log(db, link.token, "blocked", ctx, friendly, location)
        db.commit()
        return AccessDecision("expired", "Link expired", friendly, location, False)

    # 3) Known device → always allow, zero friction. Checked BEFORE the limit so a
    #    registered browser is never re-blocked when the limit changes.
    device = db.scalar(
        select(RegisteredDevice).where(
            RegisteredDevice.token == link.token,
            RegisteredDevice.device_id == ctx.device_id,
        )
    )
    if device is not None:
        device.last_seen = _now()
        device.friendly_name = friendly
        device.approx_location = location
        _log(db, link.token, "open", ctx, friendly, location)
        db.commit()
        return AccessDecision("allowed", "Known device", friendly, location, True)

    # 4) New device — register if a slot is free.
    count = db.scalar(
        select(func.count()).select_from(RegisteredDevice).where(
            RegisteredDevice.token == link.token
        )
    ) or 0
    if count < link.max_devices:
        device = RegisteredDevice(
            token=link.token,
            device_id=ctx.device_id,
            fingerprint_hash=ctx.fingerprint_hash,
            friendly_name=friendly,
            approx_location=location,
        )
        db.add(device)
        _log(db, link.token, "open", ctx, friendly, location)
        db.commit()
        return AccessDecision("allowed", "Newly registered device", friendly, location, True)

    # 5) Limit reached, unrecognized device → blocked.
    _log(db, link.token, "blocked", ctx, friendly, location)
    db.commit()
    return AccessDecision("blocked", "Device limit reached", friendly, location, False)
