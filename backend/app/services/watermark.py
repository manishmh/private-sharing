"""Per-client watermarking: visible tiled text + invisible LSB steganography.

Watermarked images are generated on demand from the clean master and cached on
local disk at data/images/wm/<token>/page-<i>.webp (lossless WebP, so the LSB
payload survives). The visible tile is the always-present, screenshot-survivable
traceable layer; the LSB payload lets a leaked *file* be decoded to the exact
client. Heavy recompression / photo-of-screen will destroy the LSB bits but not
the visible tile — this is an honest limitation, documented in the README.
"""
import math
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.config import settings

# ---- LSB steganography format ----
# layout: MAGIC(4) | payload_length uint32 BE(4) | payload(N) , one bit per channel byte.
_MAGIC = b"VWM1"
_HEADER_LEN = len(_MAGIC) + 4

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    # Pillow >= 10 supports a sized default font.
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


# --------------------------------------------------------------------------- #
# Invisible LSB watermark
# --------------------------------------------------------------------------- #
def _bytes_to_bits(data: bytes):
    for byte in data:
        for shift in range(7, -1, -1):
            yield (byte >> shift) & 1


def embed_lsb(img: Image.Image, payload: str) -> Image.Image:
    """Return a copy of `img` (RGB) with `payload` embedded in channel LSBs."""
    rgb = img.convert("RGB")
    body = payload.encode("utf-8")
    framed = _MAGIC + struct.pack(">I", len(body)) + body
    bits = list(_bytes_to_bits(framed))

    raw = bytearray(rgb.tobytes())  # R,G,B,R,G,B,... row-major
    if len(bits) > len(raw):
        raise ValueError("Image too small to hold watermark payload")

    for i, bit in enumerate(bits):
        raw[i] = (raw[i] & 0xFE) | bit

    return Image.frombytes("RGB", rgb.size, bytes(raw))


def decode_lsb(img: Image.Image) -> str | None:
    """Extract an embedded payload, or None if no valid marker is present."""
    raw = img.convert("RGB").tobytes()

    def read_bytes(offset_bits: int, n: int) -> bytes:
        out = bytearray()
        pos = offset_bits
        for _ in range(n):
            byte = 0
            for _ in range(8):
                byte = (byte << 1) | (raw[pos] & 1)
                pos += 1
            out.append(byte)
        return bytes(out)

    if len(raw) < _HEADER_LEN * 8:
        return None
    header = read_bytes(0, _HEADER_LEN)
    if header[:4] != _MAGIC:
        return None
    length = struct.unpack(">I", header[4:8])[0]
    if length <= 0 or length > 4096 or (_HEADER_LEN + length) * 8 > len(raw):
        return None
    body = read_bytes(_HEADER_LEN * 8, length)
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        return None


# --------------------------------------------------------------------------- #
# Visible tiled diagonal watermark
# --------------------------------------------------------------------------- #
def apply_visible(img: Image.Image, text: str, opacity: int, font_scale: int) -> Image.Image:
    """Tile `text` diagonally across the image, semi-transparent."""
    base = img.convert("RGBA")
    w, h = base.size

    # Scale font to image width so it reads well on both small and large pages.
    font_size = max(14, int(w * font_scale / 1000))
    font = _load_font(font_size)
    stroke = max(1, font_size // 18)

    # Measure one instance of the text.
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = probe.textbbox((0, 0), text, font=font, stroke_width=stroke)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    # Build an oversized layer (square of the diagonal) so rotation fully covers base.
    diag = int(math.hypot(w, h)) + max(tw, th)
    layer = Image.new("RGBA", (diag, diag), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    # Dense tiling so any crop / partial screenshot still captures the mark.
    gap_x = tw + int(tw * 0.35)
    gap_y = int(th * 1.9)
    fill = (255, 255, 255, opacity)
    stroke_fill = (0, 0, 0, min(255, opacity + 40))

    row = 0
    y = 0
    while y < diag:
        # Stagger every other row for a denser, harder-to-mask tile.
        x = -(row % 2) * (gap_x // 2)
        while x < diag:
            draw.text((x, y), text, font=font, fill=fill,
                      stroke_width=stroke, stroke_fill=stroke_fill)
            x += gap_x
        y += gap_y
        row += 1

    layer = layer.rotate(30, expand=False, resample=Image.BICUBIC)

    # Crop the center (w x h) out of the rotated square and composite.
    left = (diag - w) // 2
    top = (diag - h) // 2
    layer = layer.crop((left, top, left + w, top + h))

    return Image.alpha_composite(base, layer)


# --------------------------------------------------------------------------- #
# Orchestration + disk cache
# --------------------------------------------------------------------------- #
def watermarked_path(token: str, page_index: int) -> Path:
    return settings.watermark_dir / token / f"page-{page_index}.webp"


def generate_watermarked(
    *,
    master_path: str,
    token: str,
    page_index: int,
    client_label: str,
    timestamp: int,
    opacity: int,
    font_scale: int,
    suffix: str,
    regenerate: bool = False,
) -> Path:
    """Return the cached watermarked image path, creating it if missing.

    Visible text: "<client_label> · <token> · <suffix>"
    Invisible payload: "<token>|<client_label>|<timestamp>"
    """
    out = watermarked_path(token, page_index)
    if out.exists() and not regenerate:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(master_path) as master:
        master.load()
        # Visible tile is toggleable (currently disabled via settings); the
        # invisible LSB forensic watermark below is always applied.
        if settings.watermark_visible:
            visible_text = f"{client_label} · {token} · {suffix}"
            marked = apply_visible(master, visible_text, opacity, font_scale)
            flat = marked.convert("RGB")
        else:
            flat = master.convert("RGB")
        payload = f"{token}|{client_label}|{timestamp}"
        final = embed_lsb(flat, payload)
        # Lossless WebP preserves the LSB payload while staying compact.
        final.save(str(out), format="WEBP", lossless=True, quality=100, method=4)

    return out


def clear_token_cache(token: str) -> None:
    """Delete the cached watermarked images for a token (forces regeneration)."""
    d = settings.watermark_dir / token
    if d.exists():
        for f in d.glob("*.webp"):
            f.unlink(missing_ok=True)
