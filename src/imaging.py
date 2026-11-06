"""Basic image reassembly for Manual Remake: crop, straighten (deskew), clean, and numbered callouts.

Everything here works on the user's own uploaded pictures. Nothing is drawn from scratch except the
numbered markers that point at the matching rewritten step.
"""
from __future__ import annotations

import io
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

MIN_SIDE = 120          # smaller than this is an icon, bullet or logo, not a usable figure
MIN_STD = 6.0           # near-uniform images (blank boxes, solid fills) are not usable
MAX_SIDE = 1800         # downscale very large photos before work
FONT_PATHS = ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
              '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf')


def _font(size: int):
    for p in FONT_PATHS:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # very old Pillow
        return ImageFont.load_default()


def load(data: bytes) -> Image.Image:
    im = Image.open(io.BytesIO(data))
    im = ImageOps.exif_transpose(im)          # phone photos: honour the camera's rotation flag
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA')
        bg = Image.new('RGB', im.size, 'white')
        bg.paste(im, mask=im.split()[-1])
        im = bg
    return im.convert('RGB')


def usability(im: Image.Image) -> tuple[bool, str]:
    """Is this picture worth reassembling? Returns (usable, reason)."""
    w, h = im.size
    if min(w, h) < MIN_SIDE:
        return False, f'too small ({w}x{h}px)'
    g = np.asarray(im.convert('L').resize((min(w, 256), min(h, 256))), dtype=np.float32)
    if float(g.std()) < MIN_STD:
        return False, 'blank or a single solid colour'
    return True, 'ok'


def _gray_small(im: Image.Image, side: int = 600) -> tuple[np.ndarray, float]:
    scale = min(1.0, side / max(im.size))
    sm = im.convert('L').resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))))
    return np.asarray(sm, dtype=np.float32), scale


def background_level(im: Image.Image) -> float:
    """Estimate the paper colour from the image border (median of the outer ring)."""
    g, _ = _gray_small(im, 300)
    ring = np.concatenate([g[0], g[-1], g[:, 0], g[:, -1]])
    return float(np.median(ring))


def ink_mask(g: np.ndarray, bg: float) -> np.ndarray:
    return np.abs(g - bg) > 40


def estimate_skew(im: Image.Image, max_angle: float = 15.0, step: float = 0.5) -> float:
    """Return the rotation (degrees, counter-clockwise positive as in PIL) that makes lines horizontal/vertical.

    Projection-profile method: rotate the ink mask over candidate angles and pick the one whose row and
    column sums are the most peaked (sharpest lines). Works for line drawings and printed pages.
    """
    g, _ = _gray_small(im, 500)
    mask = ink_mask(g, background_level(im))
    if mask.sum() < 50:
        return 0.0
    mim = Image.fromarray((mask * 255).astype(np.uint8))

    def score(a: float) -> float:
        r = np.asarray(mim.rotate(a, resample=Image.NEAREST, expand=True), dtype=np.float32) / 255.0
        return float(np.var(r.sum(axis=1)) + np.var(r.sum(axis=0)))

    angles = np.arange(-max_angle, max_angle + 1e-9, step)
    best = max(angles, key=score)
    # refine around the best coarse angle
    fine = np.arange(best - step, best + step + 1e-9, step / 5)
    best = max(fine, key=score)
    # photos without straight lines give flat scores: only rotate when the best angle is clearly sharper than none
    if abs(best) < 0.3 or score(best) < score(0.0) * 1.08:
        return 0.0
    return float(round(best, 2))


def deskew(im: Image.Image, angle: float | None = None) -> tuple[Image.Image, float]:
    a = estimate_skew(im) if angle is None else angle
    if not a:
        return im, 0.0
    bg = int(round(background_level(im)))
    return im.rotate(a, resample=Image.BICUBIC, expand=True, fillcolor=(bg, bg, bg)), a


def content_bbox(im: Image.Image, pad_frac: float = 0.03) -> tuple[int, int, int, int]:
    """Bounding box of the drawing/photo content, ignoring the empty paper or table around it."""
    g, scale = _gray_small(im, 800)
    mask = ink_mask(g, background_level(im))
    # ignore isolated specks (scanner dust): require a few ink pixels per row/column
    rows = np.where(mask.sum(axis=1) >= 2)[0]
    cols = np.where(mask.sum(axis=0) >= 2)[0]
    if rows.size == 0 or cols.size == 0:
        return (0, 0, im.width, im.height)
    x0, x1, y0, y1 = cols[0] / scale, (cols[-1] + 1) / scale, rows[0] / scale, (rows[-1] + 1) / scale
    pad = pad_frac * max(x1 - x0, y1 - y0)
    return (max(0, int(x0 - pad)), max(0, int(y0 - pad)), min(im.width, int(math.ceil(x1 + pad))), min(im.height, int(math.ceil(y1 + pad))))


def crop(im: Image.Image) -> Image.Image:
    box = content_bbox(im)
    # do not crop to a sliver: keep at least 25% of each side
    if (box[2] - box[0]) < im.width * 0.25 or (box[3] - box[1]) < im.height * 0.25:
        return im
    return im.crop(box)


def clean(im: Image.Image) -> Image.Image:
    """Even out the paper colour, lift contrast, remove speckle and sharpen a little."""
    g = np.asarray(im, dtype=np.float32)
    bg = background_level(im)
    if 120 < bg < 250:                                   # off-white or yellowed paper: push it to white
        g = np.clip(g * (255.0 / bg), 0, 255)
    out = Image.fromarray(g.astype(np.uint8))
    out = out.filter(ImageFilter.MedianFilter(3))
    out = ImageOps.autocontrast(out, cutoff=1)
    out = out.filter(ImageFilter.UnsharpMask(radius=1.5, percent=60, threshold=3))
    return out


def prepare(im: Image.Image) -> tuple[Image.Image, dict]:
    """Full cleanup pass: downscale, deskew, crop, clean. Returns (image, info)."""
    info = {'originalSize': list(im.size)}
    if max(im.size) > MAX_SIDE:
        s = MAX_SIDE / max(im.size)
        im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    im, angle = deskew(im)
    im = crop(im)
    im = clean(im)
    info.update({'deskewDegrees': angle, 'finalSize': list(im.size)})
    return im, info


def default_positions(n: int) -> list[tuple[float, float]]:
    """Where to put markers when the rewrite gave no positions: down the left edge, evenly spaced."""
    if n <= 0:
        return []
    return [(0.06, (i + 1) / (n + 1)) for i in range(n)]


def overlay_callouts(im: Image.Image, callouts: list[dict]) -> Image.Image:
    """Draw numbered circular markers. Each callout: {"step": int, "x": 0..1, "y": 0..1} (x/y optional).

    The number shown is the rewritten step number so the picture and the step list match.
    """
    im = im.copy().convert('RGB')
    if not callouts:
        return im
    missing = [c for c in callouts if not _has_pos(c)]
    fallback = iter(default_positions(len(missing)))
    d = ImageDraw.Draw(im)
    r = max(14, int(min(im.size) * 0.045))
    font = _font(int(r * 1.15))
    for c in callouts:
        x, y = (float(c['x']), float(c['y'])) if _has_pos(c) else next(fallback)
        cx = min(max(x * im.width, r + 2), im.width - r - 2)
        cy = min(max(y * im.height, r + 2), im.height - r - 2)
        d.ellipse([cx - r - 3, cy - r - 3, cx + r + 3, cy + r + 3], fill='white')
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill='#D32F2F', outline='white', width=max(2, r // 7))
        d.text((cx, cy), str(int(c['step'])), font=font, fill='white', anchor='mm')
    return im


def _has_pos(c: dict) -> bool:
    try:
        x, y = float(c.get('x')), float(c.get('y'))
    except (TypeError, ValueError):
        return False
    return 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0


def to_png(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.save(buf, 'PNG', optimize=True)
    return buf.getvalue()


def to_jpeg(im: Image.Image, side: int = 1024, quality: int = 80) -> bytes:
    if max(im.size) > side:
        s = side / max(im.size)
        im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    buf = io.BytesIO()
    im.convert('RGB').save(buf, 'JPEG', quality=quality)
    return buf.getvalue()
