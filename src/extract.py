"""Source ingest for Manual Remake: classify uploads, enforce the page cap, pull text and pictures out of PDFs.

Hidden AI-directed text (invisible, white, microscopic or off-page text, zero-width characters and lines that
address an AI) is removed here and counted, so it never reaches the rewrite or the output PDF.
"""
from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass, field

from . import imaging

PAGE_CAP = 15
IMAGE_EXT = ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tif', '.tiff')
ZERO_WIDTH = re.compile('[\u200b-\u200f\u2028-\u202e\u2060-\u2064\ufeff\U000e0000-\U000e007f]')
# Lines that address an AI system. Kept narrow on purpose so real manual text ("use a mild cleaning agent; you must
# rinse", "ignore the previous hole") is never dropped: the phrase has to be about instructions/prompts or speak to an AI.
_AI = r'(?:ai|a\.i\.|llm|large language model|language model|chatbot|chat ?gpt|gpt-?\d*|claude|gemini|copilot|ai (?:assistant|agent|model|system))'
AI_DIRECTED = re.compile(
    r'\b(?:ignore|disregard|forget|override)\s+(?:all\s+|any\s+)?(?:of\s+)?(?:the\s+|your\s+)?(?:previous|prior|above|earlier|system|original)\s+'
    r'(?:instructions?|prompts?|rules|directions|guidelines)'
    r'|\b(?:system prompt|developer message|jailbreak|prompt injection)\b'
    r'|\b(?:note|message|instructions?)\s+(?:to|for)\s+(?:the\s+|any\s+)?(?:ai|llm|assistant|model|agent|chatbot|language model)s?\b'
    r'|\byou are (?:an?|the) (?:ai|language model|llm|assistant|chatbot)\b'
    r'|(?:^|[\s(\[])(?:dear\s+)?' + _AI + r's?\s*[:,]\s'
    r'|\b' + _AI + r's?\s+(?:reading|parsing|processing|summari[sz]ing|rewriting) (?:this|these)\b',
    re.I)


class InputError(ValueError):
    """A problem with the user's input. The message is shown to the user as-is."""


@dataclass
class Source:
    name: str
    kind: str            # 'pdf' or 'image'
    data: bytes
    pages: int = 1       # PDF pages, or 1 for a standalone image


@dataclass
class Figure:
    id: str
    source: str
    page: int | None
    image: object        # PIL.Image (raw)
    fullPage: bool = False


@dataclass
class Extracted:
    pages: list[dict] = field(default_factory=list)      # {'source','page','text','hasTextLayer'}
    figures: list[Figure] = field(default_factory=list)
    scanPages: list[Figure] = field(default_factory=list)  # pages/photos the rewrite must read visually
    skippedImages: list[dict] = field(default_factory=list)
    hiddenRemoved: list[dict] = field(default_factory=list)


def sniff(name: str, data: bytes) -> str:
    head = data[:1024]
    if b'%PDF' in head:
        return 'pdf'
    if head.startswith(b'\xff\xd8') or head.startswith(b'\x89PNG') or head[:4] == b'RIFF' and head[8:12] == b'WEBP' \
            or head[:6] in (b'GIF87a', b'GIF89a') or head[:2] == b'BM' or head[:4] in (b'II*\x00', b'MM\x00*'):
        return 'image'
    if head[4:12] in (b'ftypheic', b'ftypheix', b'ftypmif1', b'ftyphevc'):
        raise InputError(f'"{name}" is a HEIC photo. Export it as JPEG or PNG (on iPhone: Settings > Camera > Formats > Most Compatible) and upload again.')
    if b'<html' in head.lower() or b'<!doctype' in head.lower():
        raise InputError(f'"{name}" is a web page, not a PDF or image. Use a direct link to the file.')
    raise InputError(f'"{name}" is not a PDF or a supported image (JPEG, PNG, WebP, GIF, BMP, TIFF).')


def pdf_reader(data: bytes, name: str, password: str | None = None):
    from pypdf import PdfReader
    try:
        r = PdfReader(io.BytesIO(data))
        if r.is_encrypted and not r.decrypt(password or ''):
            raise InputError(f'"{name}" is password-protected. Add the password in "PDF password" or upload an unlocked copy.')
        _ = len(r.pages)
        return r
    except InputError:
        raise
    except Exception as e:  # noqa: BLE001
        raise InputError(f'"{name}" could not be opened as a PDF ({type(e).__name__}).') from e


def make_source(name: str, data: bytes, password: str | None = None) -> Source:
    if not data:
        raise InputError(f'"{name}" is empty (0 bytes).')
    kind = sniff(name, data)
    pages = len(pdf_reader(data, name, password).pages) if kind == 'pdf' else 1
    if kind == 'pdf' and pages == 0:
        raise InputError(f'"{name}" has no pages.')
    return Source(name=name, kind=kind, data=data, pages=pages)


def count_units(sources: list[Source]) -> int:
    """PDF pages plus standalone images. Pictures inside a PDF page are part of that page, not extra units."""
    return sum(s.pages if s.kind == 'pdf' else 1 for s in sources)


def check_cap(sources: list[Source], cap: int = PAGE_CAP) -> None:
    if not sources:
        raise InputError('No manual to remake. Upload a PDF or photos of the manual, or paste a direct link in "Manual files or links".')
    n = count_units(sources)
    if n > cap:
        parts = ', '.join(f'{s.name}: {s.pages} page{"s" if s.pages != 1 else ""}' if s.kind == 'pdf' else f'{s.name}: 1 image' for s in sources[:8])
        raise InputError(
            f'This run has {n} pages/images; the limit is {cap} per run ({parts}{", ..." if len(sources) > 8 else ""}). '
            f'Nothing was processed or charged. Split the manual into runs of {cap} pages or fewer (for example pages 1-{cap}, '
            f'then {cap + 1} onward) and run again.')


# ---------------------------------------------------------------- text

def _mat_mult(m, n):
    return [m[0] * n[0] + m[1] * n[2], m[0] * n[1] + m[1] * n[3], m[2] * n[0] + m[3] * n[2],
            m[2] * n[1] + m[3] * n[3], m[4] * n[0] + m[5] * n[2] + n[4], m[4] * n[1] + m[5] * n[3] + n[5]]


def clean_line(s: str) -> str:
    return re.sub(r'[ \t]+', ' ', ZERO_WIDTH.sub('', s)).strip()


def page_text(page, page_no: int, source: str, hidden: list[dict]) -> str:
    """Visible text of one page. Hidden or AI-directed text is dropped and logged in `hidden`."""
    st = {'tr': 0, 'fill': 0.0, 'stack': [], 'darkFill': False, 'image': False}
    try:
        box = page.mediabox
        W, H = float(box.width), float(box.height)
        X0, Y0 = float(box.left), float(box.bottom)
    except Exception:  # noqa: BLE001
        W, H, X0, Y0 = 612.0, 792.0, 0.0, 0.0
    chunks: list[str] = []

    def op_before(op, args, cm, tm):
        o = op.decode('latin-1') if isinstance(op, bytes) else str(op)
        try:
            if o == 'q':
                st['stack'].append((st['tr'], st['fill']))
            elif o == 'Q' and st['stack']:
                st['tr'], st['fill'] = st['stack'].pop()
            elif o == 'Tr':
                st['tr'] = int(args[0])
            elif o == 'rg':
                st['fill'] = min(float(a) for a in args[:3])          # brightness of darkest channel
            elif o == 'g':
                st['fill'] = float(args[0])
            elif o == 'k':
                st['fill'] = 1.0 - max(float(a) for a in args[:4])
            elif o in ('sc', 'scn') and len(args) in (1, 3):
                st['fill'] = min(float(a) for a in args)
            elif o in ('f', 'F', 'f*', 'B', 'B*', 'b', 'b*') and st['fill'] < 0.85:
                st['darkFill'] = True          # a coloured box was painted: white text may sit on it (warning banners)
            elif o == 'Do':
                st['image'] = True             # an image was drawn: invisible text is likely an OCR layer
        except (TypeError, ValueError, IndexError):
            pass

    def on_text(text, cm, tm, font, size):
        if not text or not text.strip():
            chunks.append(text or '')
            return
        m = _mat_mult(tm, cm)
        eff = abs(size * (m[3] if m[3] else m[0])) if size else 10
        x, y = m[4], m[5]
        why = None
        if st['tr'] == 3 and not st['image']:
            why = 'invisible text'
        elif st['fill'] >= 0.94 and st['tr'] != 3 and not st['darkFill']:
            why = 'white text'
        elif 0 < eff < 2.0:
            why = 'microscopic text'
        elif x < X0 - 5 or x > X0 + W + 5 or y < Y0 - 5 or y > Y0 + H + 5:
            why = 'off-page text'
        if why:
            hidden.append({'source': source, 'page': page_no, 'reason': why, 'chars': len(text.strip())})
            return
        chunks.append(text)

    try:
        page.extract_text(visitor_operand_before=op_before, visitor_text=on_text)
    except Exception:  # noqa: BLE001
        try:
            chunks = [page.extract_text() or '']
        except Exception:  # noqa: BLE001
            chunks = []
    lines = []
    for ln in ''.join(chunks).splitlines():
        raw = ln
        ln = clean_line(ln)
        if ZERO_WIDTH.search(raw) and len(raw) - len(ln) > 3:
            hidden.append({'source': source, 'page': page_no, 'reason': 'zero-width or tag characters', 'chars': len(raw) - len(ln)})
        if ln and AI_DIRECTED.search(ln):
            hidden.append({'source': source, 'page': page_no, 'reason': 'AI-directed instruction', 'chars': len(ln)})
            continue
        lines.append(ln)
    text = '\n'.join(lines)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def _pil_from_pdf_image(img_file):
    try:
        im = img_file.image
        if im is None:
            im = imaging.load(img_file.data)
        return imaging.load(_to_png_bytes(im))
    except Exception:  # noqa: BLE001
        try:
            return imaging.load(img_file.data)
        except Exception:  # noqa: BLE001
            return None


def _to_png_bytes(im) -> bytes:
    buf = io.BytesIO()
    im.save(buf, 'PNG')
    return buf.getvalue()


def _fingerprint(im) -> str:
    sm = im.convert('L').resize((24, 24))
    return hashlib.md5(sm.tobytes()).hexdigest()


def render_page(data: bytes, index: int, dpi: int = 150):
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(data)
    try:
        return doc[index].render(scale=dpi / 72).to_pil().convert('RGB')
    finally:
        doc.close()


def extract(sources: list[Source], want_images: bool = True, password: str | None = None) -> Extracted:
    """Pull visible text and candidate pictures from every source.

    Scanned or photographed pages (no text layer) are always kept as page images so the rewrite can read them;
    they also count as usable figures when picture work is on.
    """
    out = Extracted()
    seen: set[str] = set()
    fig_no = 0

    def add_figure(im, src, page, full=False):
        nonlocal fig_no
        ok, why = imaging.usability(im)
        if not ok:
            out.skippedImages.append({'source': src, 'page': page, 'reason': why})
            return None
        fp = _fingerprint(im)
        if fp in seen:
            out.skippedImages.append({'source': src, 'page': page, 'reason': 'repeat of an earlier picture (logo or header)'})
            return None
        seen.add(fp)
        fig_no += 1
        f = Figure(id=f'fig-{fig_no}', source=src, page=page, image=im, fullPage=full)
        out.figures.append(f)
        return f

    for s in sources:
        if s.kind == 'image':
            im = imaging.load(s.data)
            out.pages.append({'source': s.name, 'page': None, 'text': '', 'hasTextLayer': False})
            out.scanPages.append(Figure(id=f'scan-{len(out.scanPages) + 1}', source=s.name, page=None, image=im, fullPage=True))
            if want_images:
                add_figure(im, s.name, None, full=True)
            continue
        reader = pdf_reader(s.data, s.name, password)
        for i, page in enumerate(reader.pages, start=1):
            txt = page_text(page, i, s.name, out.hiddenRemoved)
            has_layer = len(re.sub(r'\s', '', txt)) >= 25
            out.pages.append({'source': s.name, 'page': i, 'text': txt, 'hasTextLayer': has_layer})
            imgs = []
            try:
                imgs = list(page.images)
            except Exception:  # noqa: BLE001
                imgs = []
            if not has_layer:
                try:
                    full = render_page(s.data, i - 1)
                    out.scanPages.append(Figure(id=f'scan-{len(out.scanPages) + 1}', source=s.name, page=i, image=full, fullPage=True))
                    if want_images and not imgs:
                        add_figure(full, s.name, i, full=True)
                except Exception as e:  # noqa: BLE001
                    out.skippedImages.append({'source': s.name, 'page': i, 'reason': f'page could not be rendered ({type(e).__name__})'})
            if want_images:
                for img in imgs:
                    im = _pil_from_pdf_image(img)
                    if im is None:
                        out.skippedImages.append({'source': s.name, 'page': i, 'reason': 'picture format could not be decoded'})
                        continue
                    add_figure(im, s.name, i)
    return out
