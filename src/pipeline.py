"""Manual Remake pipeline without any Apify I/O: sources -> extract -> clean pictures -> rewrite -> PDF.

`rewrite_fn` is injected so tests can pass a fixture rewrite instead of calling a model.
"""
from __future__ import annotations

from typing import Awaitable, Callable

from . import imaging
from .extract import Extracted, InputError, Source, check_cap, count_units, extract
from .pdfout import build_pdf, to_markdown
from .rewrite import build_messages, normalize

NOTE_OPT_OUT = 'Text-only edition: picture work was turned off for this run, so no pictures were reused.'
NOTE_NO_IMAGES = ('Text-only edition: no usable pictures were found in your upload (pictures were missing, too small, '
                  'blank, or could not be decoded), so this remake is text only.')
NOTE_NO_STEP_IMAGES = ('Text-only edition: the pictures in your upload did not show the assembly steps (for example a cover '
                       'or logo), so this remake is text only.')


def plan_mode(include_images: bool, n_figures: int) -> tuple[str, str]:
    if not include_images:
        return 'text', NOTE_OPT_OUT
    if n_figures == 0:
        return 'text', NOTE_NO_IMAGES
    return 'standard', ''


def prepare_figures(ex: Extracted) -> dict[str, dict]:
    out = {}
    for f in ex.figures:
        try:
            im, info = imaging.prepare(f.image)
        except Exception as e:  # noqa: BLE001
            ex.skippedImages.append({'source': f.source, 'page': f.page, 'reason': f'cleanup failed ({type(e).__name__})'})
            continue
        out[f.id] = {'image': im, 'info': info, 'source': f.source, 'page': f.page, 'raw': f.image}
    return out


def llm_images(ex: Extracted, prepared: dict[str, dict]) -> list[tuple[str, str, bytes]]:
    imgs, fig_raw = [], {id(v['raw']) for v in prepared.values()}
    for fid, v in prepared.items():
        where = v['source'] + (f", page {v['page']}" if v['page'] else '')
        imgs.append((fid, f'cleaned picture from {where}', imaging.to_jpeg(v['image'], 1024)))
    for s in ex.scanPages:
        where = s.source + (f', page {s.page}' if s.page else '')
        note = ' (the same photo is also attached as a fig picture)' if id(s.image) in fig_raw else ''
        imgs.append((s.id, f'photo/scan of {where} to read{note}', imaging.to_jpeg(s.image, 1600, 85)))
    return imgs


async def run_pipeline(sources: list[Source], *, include_images: bool = True, title: str | None = None,
                       checklist: bool = True, paper: str = 'letter', password: str | None = None,
                       rewrite_fn: Callable[[list[dict]], Awaitable[dict]], log=print,
                       before_rewrite: Callable[[str], Awaitable[None]] | None = None, banner: str = '',
                       footer: str | None = None, origin: str = 'your upload', source_note: str | None = None,
                       sample: bool = False) -> dict:
    """before_rewrite(planned_mode) runs after extraction and before the model call (e.g. a max-charge check).
    banner: shown at the top of the PDF and Markdown (used for the free sample). footer: overrides the page footer."""
    check_cap(sources)
    units = count_units(sources)
    ex = extract(sources, want_images=include_images, password=password)
    text_pages = [p for p in ex.pages if p['hasTextLayer']]
    if not text_pages and not ex.scanPages:
        raise InputError('No readable text or page pictures were found in the upload. If it is a scan, upload it as a PDF or as JPEG/PNG photos.')
    prepared = prepare_figures(ex) if include_images else {}
    mode, note = plan_mode(include_images, len(prepared))
    log(f'{units} page(s)/image(s); {len(text_pages)} with a text layer, {len(ex.scanPages)} to read from pictures; '
        f'{len(prepared)} usable picture(s); {len(ex.hiddenRemoved)} hidden/AI-directed text item(s) removed; mode={mode}')

    if before_rewrite is not None:
        await before_rewrite(mode)
    messages = build_messages(ex.pages, llm_images(ex, prepared))
    raw = await rewrite_fn(messages)
    rw = normalize(raw, list(prepared.keys()), title)
    if not rw['steps']:
        raise InputError('No step-by-step instructions could be found in the upload, so no remake was made. '
                         'Check that the file is the manual itself (not only a cover, warranty card or parts sheet).')

    figures_out, fig_records = {}, []
    if mode == 'standard':
        for f in rw['figures']:
            v = prepared.get(f['id'])
            if not v or not f['use']:
                continue
            im = imaging.overlay_callouts(v['image'], f['callouts'])
            figures_out[f['id']] = {'png': imaging.to_png(im), 'source': v['source'], 'page': v['page']}
            fig_records.append({'id': f['id'], 'source': v['source'], 'page': v['page'], 'caption': f['caption'], 'steps': f['steps'],
                                'callouts': len(f['callouts']), 'deskewDegrees': v['info']['deskewDegrees'],
                                'originalSize': v['info']['originalSize'], 'finalSize': v['info']['finalSize']})
        if not figures_out:
            mode, note = 'text', NOTE_NO_STEP_IMAGES

    names = [s.name for s in sources]
    pdf = build_pdf(rw, figures_out, mode=mode, mode_note=note, checklist=checklist, paper=paper, source_names=names,
                    banner=banner, footer=footer, origin=origin, source_note=source_note, sample=sample)
    return {
        'mode': mode, 'modeNote': note, 'rewrite': rw, 'pdf': pdf,
        'markdown': to_markdown(rw, mode, note, banner, sample=sample, source_note=source_note),
        'figures': figures_out, 'figureRecords': fig_records, 'units': units, 'sources': names,
        'textPages': len(text_pages), 'scanPages': len(ex.scanPages), 'usablePictures': len(prepared),
        'skippedImages': ex.skippedImages, 'hiddenRemoved': ex.hiddenRemoved,
    }
