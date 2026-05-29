#!/usr/bin/env python
"""Seed / demo helper — ingest a local PDF into Vault without using the UI.

Examples
--------
# Ingest your own PDF and mint a demo link:
    python seed.py --pdf /path/to/catalog.pdf --title "Silk Aura Vol 6" \
        --label "Rajesh Textiles" --max-devices 1

# No PDF handy? Generate a synthetic demo catalog + link:
    python seed.py --make-demo

It prints the catalog id, slug, page count and the public link URL so you can test
the whole flow end-to-end.
"""
import argparse
import sys
from pathlib import Path

# Allow running as `python seed.py` from the backend/ dir.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import Catalog, CatalogImage, ShareLink  # noqa: E402
from app.services import pdf, tokens  # noqa: E402


def _make_demo_pdf() -> bytes:
    """Render a few colorful pages to an in-memory PDF for testing."""
    import fitz

    palette = [(214, 188, 160), (160, 196, 214), (196, 160, 214), (160, 214, 176), (214, 160, 160)]
    doc = fitz.open()
    for i, (r, g, b) in enumerate(palette):
        page = doc.new_page(width=595, height=842)  # A4 points
        page.draw_rect(page.rect, color=None, fill=(r / 255, g / 255, b / 255))
        page.insert_text((60, 120), f"DEMO DESIGN  #{i + 1}", fontsize=40, color=(0.1, 0.1, 0.1))
        page.insert_text((60, 180), "Vault sample catalog page", fontsize=18, color=(0.2, 0.2, 0.2))
        # A little geometry so the watermark has texture to sit on.
        for k in range(6):
            page.draw_circle((150 + k * 60, 420), 26, color=(0.2, 0.2, 0.2), width=2)
    data = doc.tobytes()
    doc.close()
    return data


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest a PDF into Vault.")
    ap.add_argument("--pdf", help="Path to a local PDF file")
    ap.add_argument("--title", default="Demo Catalog", help="Catalog title")
    ap.add_argument("--make-demo", action="store_true", help="Generate a synthetic demo PDF")
    ap.add_argument("--label", default="Demo Client", help="Client label for the minted link")
    ap.add_argument("--max-devices", type=int, default=1, help="Max devices for the link")
    ap.add_argument("--no-link", action="store_true", help="Only create the catalog, skip the link")
    args = ap.parse_args()

    if args.pdf:
        pdf_bytes = Path(args.pdf).read_bytes()
        source_name = Path(args.pdf).name
    elif args.make_demo:
        pdf_bytes = _make_demo_pdf()
        source_name = "demo.pdf"
        if args.title == "Demo Catalog":
            args.title = "Silk Aura Vol 6 (Demo)"
    else:
        ap.error("Provide --pdf <path> or --make-demo")

    db = SessionLocal()
    try:
        base_slug = pdf.slugify(args.title)
        slug = pdf.unique_slug(
            base_slug,
            exists=lambda s: db.scalar(select(Catalog).where(Catalog.slug == s)) is not None,
        )
        pages = pdf.extract_pdf(pdf_bytes, slug)
        if not pages:
            print("ERROR: PDF produced no pages", file=sys.stderr)
            sys.exit(1)

        catalog = Catalog(
            slug=slug, title=args.title, source_pdf_name=source_name, page_count=len(pages)
        )
        db.add(catalog)
        db.flush()
        for p in pages:
            db.add(CatalogImage(
                catalog_id=catalog.id, page_index=p.page_index,
                file_path=p.file_path, width=p.width, height=p.height,
            ))
        db.commit()
        db.refresh(catalog)

        print(f"Catalog created: id={catalog.id}  slug={catalog.slug}  pages={catalog.page_count}")

        if not args.no_link:
            token = tokens.generate_token()
            while db.get(ShareLink, token) is not None:
                token = tokens.generate_token()
            link = ShareLink(
                token=token, catalog_id=catalog.id, slug=catalog.slug,
                max_devices=args.max_devices, client_label=args.label, revoked=False,
            )
            db.add(link)
            db.commit()
            print(f"Link minted:   token={token}  label='{args.label}'  max_devices={args.max_devices}")
            print(f"Public URL:    /v/{catalog.slug}-{token}")
            print(f"Open in dev:   http://localhost:5173/v/{catalog.slug}-{token}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
