# Vault — Secure Design Catalog Sharing (Local Prototype)

Replaces insecure PDF sharing of textile/fabric design photos. An admin uploads a PDF once;
the system extracts pages as clean master images and lets the admin mint many short,
device-locked share links per catalog. Clients open a link on their phone; it binds to their
device(s) and shows a smooth, mobile-first, **per-client-watermarked** catalog feed.

> Goal = **deterrence + traceability**, not perfect prevention. See "Security honesty" below.

Everything runs **locally**: no cloud, no hosted services, no Docker required.

---

## 1. Prerequisites

- **Python 3.11+** (tested on 3.12)
- **Node 18+** (tested on Node 20)
- **PostgreSQL 14+** running locally on `localhost:5432` (15+ recommended; 14 works fine)

Check PostgreSQL is up:
```bash
pg_isready          # expect: accepting connections
```

---

## 2. One-time database setup (privileged)

Vault uses a dedicated `vault` role + `vault` database. Creating them needs PostgreSQL
superuser rights, so run this **once** as the `postgres` user:

```bash
sudo -u postgres psql -f backend/setup_db.sql
```

This creates role `vault` (password `vault`) and database `vault` it owns. It is idempotent.

> Prefer no password / Unix-socket peer auth as your own OS user instead? Create the DB your
> own way and set `DATABASE_URL=postgresql+psycopg:///vault` in `backend/.env`.

---

## 3. Backend setup & run

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Config: copy the example and adjust if needed (defaults already match step 2).
cp .env.example .env       # DATABASE_URL, ADMIN_PASSWORD (unused), DATA_DIR, CORS_ORIGINS, WATERMARK_VISIBLE

# Create all tables via Alembic migrations:
alembic upgrade head

# Run the API (http://localhost:8000, docs at /docs):
uvicorn app.main:app --reload --port 8000
```

`backend/.env` defaults:
- `DATABASE_URL=postgresql+psycopg://vault:vault@localhost:5432/vault`
- `ADMIN_PASSWORD=vault-admin`  ← admin password gate is **currently disabled** (open console);
  the value is unused unless you re-enable the gate in `app/deps.py`
- `DATA_DIR=../data`            ← images live under `data/images/`
- `WATERMARK_VISIBLE=false`     ← visible tile **off** by default; invisible LSB always applied

> Re-running migrations: `alembic upgrade head` applies `0001_initial`, then `0002_fuzzy_device`
> (an experimental cross-browser device-match schema) and `0003_rollback_per_browser` (which
> reverts it). The end state is the **per-browser** schema. If your DB was already at `0002`,
> just re-run `alembic upgrade head` to drop the extra table/column.

---

## 4. Frontend setup & run

In a second terminal:
```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

The Vite dev server proxies `/api` and `/admin` to the backend on `:8000`, so cookies and
device-locking work without CORS friction.

- Admin console: **http://localhost:5173/admin**  (no password — open console for this prototype)
- Client viewer: **http://localhost:5173/v/{slug}-{token}**

---

## 5. Create a catalog from a PDF

**Option A — admin UI:** open `/admin`, click **Upload PDF**, give it a title and file.

**Option B — seed script (no UI clicking):**
```bash
cd backend && source .venv/bin/activate

# Use your own PDF:
python seed.py --pdf /path/to/catalog.pdf --title "Silk Aura Vol 6" \
    --label "Rajesh Textiles" --max-devices 1

# OR generate a synthetic demo catalog + link to test instantly:
python seed.py --make-demo
```
The script prints the catalog id, slug, page count, and a ready-to-open link URL.

**Option C — curl** (admin auth is disabled, so no header needed):
```bash
curl -s -X POST http://localhost:8000/api/admin/catalogs \
  -F "title=Silk Aura Vol 6" \
  -F "file=@/path/to/catalog.pdf"
```

---

## 6. Mint & manage links

In the catalog detail screen you can **Create a share link** with a client label, max devices,
and optional expiry (blank = never). For each link you can, **without reissuing it**:
- **Set limit** — type an exact `max_devices` value (never drops below already-registered count; it warns instead)
- **set / clear expiry**
- **Revoke / Un-revoke** instantly
- **Copy link** (one tap, shows "Link copied!")
- **Delete** the link (on confirmation) — a still-active link is revoked and deleted in one step,
  so you never have to revoke it manually first; its devices, analytics and watermark cache go too
- open **Analytics**

You can also **Delete catalog** from the catalog detail screen (removes its links, devices,
events and on-disk images).

Or via curl (no auth header needed):
```bash
# mint a link
curl -s -X POST http://localhost:8000/api/admin/catalogs/1/links \
  -H "Content-Type: application/json" \
  -d '{"client_label":"Rajesh Textiles","max_devices":1}'

# set the device limit to an exact value
curl -s -X PATCH http://localhost:8000/api/admin/links/Ab3xK9 \
  -H "Content-Type: application/json" -d '{"max_devices":2}'

# revoke instantly
curl -s -X PATCH http://localhost:8000/api/admin/links/Ab3xK9 \
  -H "Content-Type: application/json" -d '{"revoked":true}'

# delete a link (auto-revokes first if it's still active)
curl -s -X DELETE http://localhost:8000/api/admin/links/Ab3xK9

# delete a catalog
curl -s -X DELETE http://localhost:8000/api/admin/catalogs/1
```

---

## 7. Testing the device-lock (per-browser)

The public URL is `/v/{slug}-{token}`, e.g. `/v/silk-aura-vol-6-Ab3xK9`.

Locking is **per browser**: a link allows up to `max_devices` distinct browsers. Opening it in a
different browser — even on the same physical machine — counts as another device and is blocked
once the limit is reached.

1. **First open:** open the link in your normal browser → it loads; the device is registered.
2. **Same browser reopens with zero friction:** refresh / reopen any time → always allowed
   (the known device is checked before the limit, so it is never re-blocked).
3. **Different browser = different slot:** with `max_devices=1`, open the link in a **second
   browser** (e.g. Chrome then Firefox, or a private window) → friendly **"Device limit reached"**
   screen and a `blocked` event. Raise the limit with **Set limit**, reopen → it loads.
4. **Expiry / revoke:** set an expiry in the past, or click **Revoke** → friendly **"no longer
   active"** screen, and that link's cached images are purged from the browser's IndexedDB.
   Un-revoke to restore.
5. **Default never-expires:** links created without an expiry never expire.

**Simulating two devices via curl** (distinct `device_id`s → two slots):
```bash
# device A (allowed, registers)
curl -s -c /tmp/a.txt http://localhost:8000/api/v/Ab3xK9 >/dev/null
curl -s -b /tmp/a.txt -X POST http://localhost:8000/api/v/Ab3xK9/access \
  -H "Content-Type: application/json" \
  -d '{"device_id":"devA0000"}'

# device B (different id → blocked at limit 1)
curl -s -c /tmp/b.txt http://localhost:8000/api/v/Ab3xK9 >/dev/null
curl -s -b /tmp/b.txt -X POST http://localhost:8000/api/v/Ab3xK9/access \
  -H "Content-Type: application/json" \
  -d '{"device_id":"devB1111"}'
```

> A known device is checked **before** the limit, so it is never blocked as "new" regardless of
> limit changes. The visible + invisible watermark remains the real traceability guarantee.

---

## 8. Watermarks (the real protection)

Every served image is generated per-link from the clean master and cached at
`data/images/wm/<token>/page-<i>.webp`:
- **Visible:** tiled diagonal semi-transparent text `"<client_label> · <token> · CONFIDENTIAL"`.
  **Disabled by default** (`WATERMARK_VISIBLE=false`) — set it to `true` and clear the cache
  (`rm -rf data/images/wm/*`) to re-enable. The rendering logic stays in `app/services/watermark.py`.
- **Invisible (LSB):** `"<token>|<client_label>|<unix_ts>"` embedded in pixel low-bits — **always
  applied**, regardless of the visible toggle.

**Decode a captured image** back to the client:
- Admin UI: **Decode watermark** (top right) → upload the image.
- curl (no auth header needed):
```bash
curl -s -X POST http://localhost:8000/api/admin/decode-watermark \
  -F "file=@/path/to/leaked.webp"
```

---

## 9. Client caching (IndexedDB)

The viewer fetches the manifest, then loads **every** page sequentially (page 0 first), even
without scrolling — cache-first from IndexedDB, fetching only what's missing and storing each
blob. Reopening the link serves cached pages instantly (offline-ish). Sized skeletons keep the
layout stable and a small "loading X/N" shows progress. Visiting an **expired or revoked** link
purges that link's cached images from IndexedDB so confidential pages don't linger locally.

---

## 10. Analytics

The admin per-link analytics view shows only: friendly device name, approx location, open count,
first/last seen, and registered vs blocked/revoked attempts. Raw fingerprint, full user-agent,
and IP are recorded on the backend (`access_event`) but intentionally **not** shown in the UI.

`approx_location` (`backend/app/services/geo.py`) does a real IP-geolocation lookup via the free,
no-key **ip-api.com** service and shows a "City, Region, Country" label. Because everything runs
locally the client IP is loopback/private, so it geolocates the **server's own public IP** — your
actual approximate location. Results are cached; if the lookup is offline or rate-limited it falls
back to "Localhost"/"Local network". This is the **only** part of Vault that makes an outbound
call — swap `_geo_api` for an offline MaxMind/GeoIP2 reader to stay fully local.

---

## 11. Security honesty (screenshot deterrents)

You **cannot** truly block screenshots or screen recording in a mobile web browser. Vault
implements best-effort deterrents (disabled context menu / long-press / drag / selection,
images as CSS backgrounds, a privacy overlay when the page is hidden or loses focus, desktop
PrintScreen clipboard overwrite + flash). These only raise friction. The **watermark is the
real defense**: any capture remains traceable to the exact client. The invisible LSB payload
survives lossless re-encoding but not heavy recompression / photo-of-screen; the visible tile
always survives. See `frontend/src/lib/deterrents.js` and `backend/app/services/watermark.py`.

> Admin auth is **disabled** for this prototype — the console is open to anyone who can reach it.
> The password gate is kept in `app/deps.py` (re-enable by re-adding the router dependency), but
> you must add real authentication before any production use.

---

## 12. Project layout

```
backend/   FastAPI app, SQLAlchemy models, Alembic migrations, services, seed.py, setup_db.sql
frontend/  React + Vite (admin console + client viewer)
data/      local image store (gitignored): images/masters/<slug>/, images/wm/<token>/
PLAN.md    architecture, data model, endpoints, screens
```

## 13. Run commands (quick reference)

```bash
# one-time
sudo -u postgres psql -f backend/setup_db.sql
cd backend && python3.12 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && cp .env.example .env && alembic upgrade head

# run backend (terminal 1)
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000

# run frontend (terminal 2)
cd frontend && npm install && npm run dev
```

---

## 14. Deploy to Render (free tier)

Vault deploys as **one** Docker service: FastAPI serves the API under `/api/*` and
the built React SPA on every other path, so it's same-origin (the device cookie just
works, no CORS). Files: [`Dockerfile`](Dockerfile) (multi-stage Node→Python build) and
[`render.yaml`](render.yaml) (a Blueprint defining the web service + a free Postgres).

**Steps:**
1. Push this repo to GitHub:
   ```bash
   git init && git add -A && git commit -m "Vault" && git branch -M main
   git remote add origin git@github.com:<you>/<repo>.git && git push -u origin main
   ```
2. In Render: **New → Blueprint**, pick the repo. It reads `render.yaml` and provisions
   the `vault` web service + `vault-db` Postgres. `DATABASE_URL` is injected and
   normalized to `postgresql+psycopg://` in `app/config.py`; migrations run on boot.
3. Set the one secret it asks for: **`ADMIN_PASSWORD`** (a strong value). The admin
   console is then gated by HTTP Basic auth (user **`admin`**, that password).
4. Open `https://<service>.onrender.com/admin`, enter the credentials, upload a PDF,
   mint a link, and open `/v/<slug>-<token>` on your phone over HTTPS.

**Free-tier caveats (important):**
- **No persistent disk** and the service **sleeps after ~15 min idle**. On every
  restart/redeploy the container filesystem (`DATA_DIR=/data`) is wiped, so uploaded
  master images vanish while their DB rows remain → existing catalogs show broken
  images. Re-upload after a cold start, or (for durability) move image storage to
  object storage / a paid disk.
- Render's **free Postgres is time-limited** and may expire.

**Prod env vars** (set by `render.yaml`): `STATIC_DIR=/app/static`, `DATA_DIR=/data`,
`COOKIE_SECURE=true`, `ADMIN_AUTH_ENABLED=true`, `WATERMARK_VISIBLE=false`,
`ADMIN_PASSWORD` (you set it). These stay unset locally, so `npm run dev` + Vite is
unchanged.
