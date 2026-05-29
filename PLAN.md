# Vault — Secure Design Catalog Sharing (Local Prototype) — PLAN

A local-only system that replaces insecure PDF sharing of textile/fabric design photos.
Admin uploads a PDF once → pages are extracted as clean master images → admin mints
many short, device-locked share links per catalog → clients browse a smooth, mobile-first,
per-client-watermarked catalog feed. Goal = **deterrence + traceability**, not perfect prevention.

---

## 1. Tech stack (fixed)

| Layer        | Choice                                                                 |
|--------------|------------------------------------------------------------------------|
| Backend      | Python 3.12, FastAPI, Uvicorn                                          |
| ORM / mig.   | SQLAlchemy 2.x + Alembic, driver `psycopg` (v3)                        |
| Database     | **Local** PostgreSQL on `localhost:5432` via `DATABASE_URL`           |
| PDF → image  | PyMuPDF (`fitz`)                                                       |
| Imaging / WM | Pillow (visible tiled watermark) + manual LSB steganography (invisible)|
| Tokens       | 6-char base62 nanoid-style (NOT UUID)                                  |
| Frontend     | React + Vite, react-router, hooks                                     |
| Caching      | IndexedDB via `idb`                                                   |
| Fingerprint  | `@fingerprintjs/fingerprintjs` (OSS) + self-gen device UUID + cookie  |
| HTTP         | `fetch`                                                               |

> Note: dev machine has PostgreSQL **14** (project asked for 15+). 14 is fully compatible
> with everything used here; documented in README. Python 3.12 used (≥ 3.11 ✓).

---

## 2. Folder structure

```
private-sharing/
├── PLAN.md
├── README.md
├── .gitignore
├── data/                      # gitignored (created at runtime)
│   └── images/
│       ├── masters/<catalog_slug>/page-<n>.png        # CLEAN masters
│       └── wm/<token>/page-<n>.webp                    # per-link watermarked cache
├── backend/
│   ├── requirements.txt
│   ├── .env.example
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/0001_initial.py
│   ├── seed.py                # ingest a local PDF end-to-end without the UI
│   ├── setup_db.sql           # privileged role+db creation (run once)
│   └── app/
│       ├── main.py            # FastAPI app, CORS, routers, static
│       ├── config.py          # Settings from env
│       ├── db.py              # engine + SessionLocal + get_db
│       ├── models.py          # SQLAlchemy models
│       ├── schemas.py         # Pydantic request/response models
│       ├── deps.py            # admin auth dependency, db dep
│       ├── services/
│       │   ├── tokens.py      # 6-char base62 generator
│       │   ├── pdf.py         # PDF → master PNGs
│       │   ├── watermark.py   # visible tiling + LSB embed/decode + cache
│       │   ├── devices.py     # device-lock decision logic (the critical part)
│       │   ├── useragent.py   # UA → friendly name
│       │   └── geo.py         # pluggable approx-location (stub default)
│       └── routers/
│           ├── admin.py       # all /admin/* endpoints
│           └── public.py      # /v/.. resolve, manifest, image serving
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── main.jsx, App.jsx, api.js
        ├── lib/{device.js, idbCache.js, deterrents.js}
        ├── admin/{Login, CatalogList, UploadCatalog, CatalogDetail, LinkAnalytics}.jsx
        └── client/{CatalogViewer, ImageTile, BlockedScreen, ExpiredScreen}.jsx
```

---

## 3. Data model (PostgreSQL)

```
catalog
  id PK, slug UNIQUE, title, source_pdf_name, page_count,
  wm_opacity, wm_font_scale, wm_text_suffix (base WM settings), created_at

catalog_image
  id PK, catalog_id FK→catalog, page_index, file_path (clean master),
  width, height        UNIQUE(catalog_id, page_index)

share_link
  token PK (6-char), catalog_id FK→catalog, slug (denormalized),
  max_devices INT, client_label TEXT, expires_at TIMESTAMPTZ NULL (default NULL = never),
  revoked BOOL default false, created_at        INDEX(catalog_id)

registered_device   (one row per browser that registers)
  id PK, token FK→share_link, device_id (per-browser id), fingerprint_hash,
  friendly_name, approx_location, first_seen, last_seen
  UNIQUE(token, device_id)   INDEX(token)

access_event
  id PK, token FK→share_link, device_id, event_type (open|blocked|revoked_attempt),
  friendly_name, approx_location, ip, user_agent, created_at
  INDEX(token), INDEX(token, created_at)
```

---

## 4. Link / URL system

- Public URL: `/v/{slug}-{token}` → `/v/silk-aura-vol-6-Ab3xK9`.
- Resolve by **token** (last 6 chars after the final `-`); slug is cosmetic, validated for nicer 404s.
- Frontend route `/v/:linkId` parses `linkId` → splits trailing token.

---

## 5. Device-locking logic (critical) — per-browser

Locking is **per browser**: a link allows up to `max_devices` distinct browsers. Opening it
from a different browser (even on the same physical device) consumes another slot.

Identity:
- **Per-browser id** (`device_id`) = stable hash of FingerprintJS `visitorId` + a UUID in
  IndexedDB + an httpOnly cookie the backend sets. Clearing any single source does not
  trivially reset it.

On `POST /api/v/{token}/access`:
1. If `revoked` → log `revoked_attempt`, return `revoked`.
2. If `expires_at` set and `< now` → log `blocked`, return `expired`.
3. **Known device** — a `registered_device` with this browser id already exists → allow, zero
   friction (update last_seen). Checked BEFORE the limit, so a known device is never re-blocked.
4. **New device** — if `count(registered_device) < max_devices` → create the device, log `open`,
   allow.
5. Else (limit reached, unrecognized) → log `blocked`, return `blocked`.

Content GETs (manifest/images) are gated on the calling browser being a registered device for
the link.

> NOTE: this is the original per-browser model. The cross-browser fuzzy device-matching
> experiment (signals + a `device_browser` map table) was rolled back — see §11.

---

## 6. Endpoints

### Admin (auth currently DISABLED — open console; gate kept in `app/deps.py`)
> UI routes live at `/admin/*`; the admin **API** is namespaced under `/api/admin/*`
> (mirrors public `/api/v` vs UI `/v`) so a hard browser refresh on an admin route
> isn't proxied to the backend and falls through to the SPA.

| Method | Path                                  | Purpose                                            |
|--------|---------------------------------------|----------------------------------------------------|
| POST   | `/api/admin/catalogs`                 | multipart PDF upload → extract pages → catalog      |
| GET    | `/api/admin/catalogs`                 | list catalogs (+ page_count, link_count)            |
| GET    | `/api/admin/catalogs/{id}`            | catalog detail + its links                          |
| DELETE | `/api/admin/catalogs/{id}`            | delete catalog + cascade links/devices + disk files |
| POST   | `/api/admin/catalogs/{id}/links`      | mint link (max_devices, client_label, expires_at)   |
| PATCH  | `/api/admin/links/{token}`            | update max_devices / expires_at / revoked           |
| DELETE | `/api/admin/links/{token}`            | delete link (auto-revokes if active) + cascade + cache |
| GET    | `/api/admin/links/{token}/analytics`  | per-link analytics (sanitized + raw split)          |
| POST   | `/api/admin/decode-watermark`         | upload image → return decoded LSB payload           |

### Public (no admin auth)
| Method | Path                              | Purpose                                                       |
|--------|-----------------------------------|---------------------------------------------------------------|
| GET    | `/api/v/{token}`                  | resolve link meta (title, page_count, status) + set cookie    |
| POST   | `/api/v/{token}/access`           | device-lock decision (body: device_id, fingerprint, UA hints) |
| GET    | `/api/v/{token}/manifest`         | ordered page list (index, w, h) — gated by access             |
| GET    | `/api/v/{token}/page/{i}.webp`    | per-client watermarked image (visible + LSB), disk-cached     |

---

## 7. Watermarking

Per-link, generated on demand from the clean master, cached at `data/images/wm/<token>/page-<i>.webp`.
- **Visible**: tiled diagonal repeated text `"{client_label} · {token} · CONFIDENTIAL"`,
  semi-transparent, sized for mobile readability vs. intrusion (tunable via catalog settings).
- **Invisible (LSB)**: embed `"{token}|{client_label}|{unix_ts}"` into low bits of RGB channels
  with a length header + magic marker; decode reverses it. Applied to the *final* served image.
- Cache invalidation: delete `wm/<token>/` to force regen; served handler regenerates if missing.

> LSB survives PNG/WEBP-lossless re-encode but NOT heavy recompression/screenshots-of-screenshots.
> Honest limitation; the visible tile is the always-present traceable layer.

---

## 8. Screenshot deterrents (best-effort, documented)

Client viewer: `user-select:none`, `-webkit-touch-callout:none`, `draggable=false`,
contextmenu/dragstart/copy guards, images as CSS `background-image` on `<div>` (not `<img src>`),
blur+black overlay on `visibilitychange`/`blur`/`pagehide`, desktop PrintScreen keyup → overwrite
clipboard + flash overlay. Every view carries the per-client watermark so any capture is traceable.
Clear comment block states these are deterrents, not guarantees.

---

## 9. Frontend screens

**Admin** (open, no login): Catalog list → Upload PDF → Catalog detail (create link + links
table + delete catalog) → Per-link analytics (friendly name, approx location, opens,
first/last seen, registered vs blocked).

**Client**: `/v/:linkId` viewer — vertical scrolling feed, progressive skeletons, eager in-order
IndexedDB caching (all pages, page 0 first; serve cached first), Blocked screen, Expired/Revoked
screen (which also purges that link's cached images).

---

## 10. Build order

1. PLAN.md ✓ 2. Backend scaffold 3. Models + Alembic 4. Services (tokens/pdf/watermark)
5. API (admin + public + device lock) 6. Frontend 7. seed + README + DB setup + verify.

---

## 11. Changes since v1

- **Cross-browser fuzzy device matching — ROLLED BACK.** It was added in `0002_fuzzy_device`
  (a `device_browser` map table + a `signals` column + weighted similarity scoring) and then
  reverted in `0003_rollback_per_browser`. Locking is back to **per browser** (see §5): a new
  browser, even on the same physical device, uses another slot. Migrations `0002`/`0003` stay in
  history; running `alembic upgrade head` ends at the per-browser schema.
- **Admin password disabled** — console opens directly; the `require_admin` gate is kept in
  `app/deps.py` (re-enable by re-adding the router dependency).
- **Visible watermark disabled by default** — `WATERMARK_VISIBLE=false` env flag; the invisible
  LSB watermark is always applied. Visible-tile rendering stays in `app/services/watermark.py`.
- **Delete catalog** — `DELETE /admin/catalogs/{id}` (cascades links/devices/events + removes
  on-disk masters and watermark caches) + a button on the catalog detail screen.
- **Eager in-order image loading** — the viewer loads every page sequentially (page 0 first),
  cache-first via IndexedDB, instead of waiting for scroll.
- **Expiry/revoke cache purge** — visiting an expired/revoked link clears that link's cached
  images from IndexedDB (`clearTokenImages`).
- **Admin UX** — bigger copy-link button with icon + "Link copied!" toast; set an exact device
  limit (not just +1); analytics shows a per-device browser count.
