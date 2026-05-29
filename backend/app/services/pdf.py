"""PDF → clean master images using PyMuPDF (fitz).

Each page is rendered at high resolution and saved as a lossless PNG master under
data/images/masters/<slug>/page-<n>.png. Masters are never watermarked; per-link
watermarking reads from them on demand.
"""
import re
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF

from app.config import settings

# Render zoom: 2.0 ≈ 144 DPI, good quality for design photos without huge files.
RENDER_ZOOM = 2.0


@dataclass
class ExtractedPage:
    page_index: int
    file_path: str
    width: int
    height: int


def slugify(value: str) -> str:
    """Turn a title into a URL-safe slug, e.g. 'Silk Aura Vol 6' -> 'silk-aura-vol-6'."""
    value = value.strip().lower()
    value = re.sub(r"[^\w\s-]", "", value)
    value = re.sub(r"[\s_-]+", "-", value)
    return value.strip("-") or "catalog"


def extract_pdf(pdf_bytes: bytes, slug: str) -> list[ExtractedPage]:
    """Render every page of the PDF to a PNG master. Returns page metadata."""
    out_dir = settings.masters_dir / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    pages: list[ExtractedPage] = []
    matrix = fitz.Matrix(RENDER_ZOOM, RENDER_ZOOM)

    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            file_path = out_dir / f"page-{i}.png"
            pix.save(str(file_path))
            pages.append(
                ExtractedPage(
                    page_index=i,
                    file_path=str(file_path),
                    width=pix.width,
                    height=pix.height,
                )
            )
    return pages


def unique_slug(base_slug: str, exists: callable) -> str:
    """Append -2, -3, ... until `exists(slug)` is False."""
    if not exists(base_slug):
        return base_slug
    n = 2
    while exists(f"{base_slug}-{n}"):
        n += 1
    return f"{base_slug}-{n}"
