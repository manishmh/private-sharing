"""Vault FastAPI application entrypoint.

In production this single service serves BOTH the JSON API (under /api/*) and the
built React SPA (every other path), so the browser treats them as same-origin and
the httpOnly device cookie works without CORS. Locally you instead run Vite on
:5173 (which proxies /api here) and STATIC_DIR is unset, so the SPA mount is off.
"""
import base64
import secrets

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import admin, public

app = FastAPI(title="Vault — Secure Design Catalog Sharing", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,  # needed so the httpOnly identity cookie round-trips
    allow_methods=["*"],
    allow_headers=["*"],
)


def _check_basic_auth(header: str) -> bool:
    if not header.startswith("Basic "):
        return False
    try:
        user, _, pw = base64.b64decode(header[6:]).decode("utf-8").partition(":")
    except Exception:  # noqa: BLE001 - malformed header == not authorized
        return False
    return (secrets.compare_digest(user, "admin")
            and secrets.compare_digest(pw, settings.admin_password))


@app.middleware("http")
async def admin_basic_auth(request: Request, call_next):
    """Optional HTTP Basic gate for the admin console (UI + API). Enabled via
    ADMIN_AUTH_ENABLED=true for the public deploy; the client viewer is never
    gated. The browser prompts once on the /admin document load, then reuses the
    credentials for same-origin /api/admin fetches."""
    if settings.admin_auth_enabled:
        path = request.url.path
        if path == "/admin" or path.startswith("/admin/") or path.startswith("/api/admin"):
            if not _check_basic_auth(request.headers.get("authorization", "")):
                return Response(status_code=401,
                                headers={"WWW-Authenticate": 'Basic realm="Vault admin"'})
    return await call_next(request)


app.include_router(admin.router)
app.include_router(public.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# --- Serve the built React SPA (production single-service deploy) ---------- #
_static = settings.static_path
if _static is not None and _static.is_dir():
    _assets = _static / "assets"
    if _assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")

    @app.get("/")
    def _root():
        # A document navigation to /admin so the Basic-auth prompt fires when enabled.
        return RedirectResponse("/admin")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        # /api/* is matched by the routers above; anything here is a UI route.
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        candidate = _static / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(_static / "index.html"))
