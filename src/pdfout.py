"""Print-friendly PDF for Manual Remake (reportlab). Pure: takes a normalized rewrite + prepared figure PNGs."""
from __future__ import annotations

import io
import os
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (CondPageBreak, Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

SOURCE_NOTE = ('This document is a rewrite of the file you uploaded, made by Manual Remake (Panda Federation). '
               'It is not an official or certified replacement for the manufacturer\'s manual and makes no safety, '
               'standards or compliance claim. If anything here disagrees with the original, follow the original '
               'or ask the manufacturer.')
FOOTER = 'Rewrite of your uploaded manual, not a certified replacement. Check against the original.'
ACCENT = colors.HexColor('#1F4E79')
WARN = colors.HexColor('#B71C1C')
GAP = colors.HexColor('#8D6E00')

_FONT, _BOLD, _BOX = 'Helvetica', 'Helvetica-Bold', '[  ]'
for reg, bold in (('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
                  ('/usr/share/fonts/dejavu/DejaVuSans.ttf', '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf')):
    if os.path.exists(reg) and os.path.exists(bold):
        try:
            pdfmetrics.registerFont(TTFont('DejaVu', reg))
            pdfmetrics.registerFont(TTFont('DejaVu-Bold', bold))
            _FONT, _BOLD, _BOX = 'DejaVu', 'DejaVu-Bold', '\u2610'
        except Exception:  # noqa: BLE001
            pass
        break


def _styles():
    ss = getSampleStyleSheet()
    base = ParagraphStyle('base', parent=ss['Normal'], fontName=_FONT, fontSize=11, leading=15, alignment=TA_LEFT)
    return {
        'base': base,
        'small': ParagraphStyle('small', parent=base, fontSize=8.5, leading=11, textColor=colors.HexColor('#555555')),
        'title': ParagraphStyle('title', parent=base, fontName=_BOLD, fontSize=22, leading=27, textColor=ACCENT, spaceAfter=4),
        'sub': ParagraphStyle('sub', parent=base, fontSize=10, textColor=colors.HexColor('#555555'), spaceAfter=10),
        'h2': ParagraphStyle('h2', parent=base, fontName=_BOLD, fontSize=15, leading=19, textColor=ACCENT, spaceBefore=12, spaceAfter=6),
        'step': ParagraphStyle('step', parent=base, fontName=_BOLD, fontSize=13.5, leading=17, spaceBefore=10, spaceAfter=3),
        'li': ParagraphStyle('li', parent=base, leftIndent=22, firstLineIndent=-14, spaceAfter=2),
        'warn': ParagraphStyle('warn', parent=base, textColor=WARN, leftIndent=12, firstLineIndent=-12, spaceAfter=3),
        'gap': ParagraphStyle('gap', parent=base, fontSize=10.5, leading=14),
        'cap': ParagraphStyle('cap', parent=base, fontSize=9.5, leading=12, textColor=colors.HexColor('#333333'), spaceAfter=8),
        'cell': ParagraphStyle('cell', parent=base, fontSize=10, leading=13),
        'cellb': ParagraphStyle('cellb', parent=base, fontName=_BOLD, fontSize=10, leading=13),
    }


def _p(text, style):
    return Paragraph(escape(str(text or '')), style)


def _boxed(flow, border, bg):
    t = Table([[flow]], colWidths=['100%'])
    t.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), 1.2, border), ('BACKGROUND', (0, 0), (-1, -1), bg),
                           ('LEFTPADDING', (0, 0), (-1, -1), 9), ('RIGHTPADDING', (0, 0), (-1, -1), 9),
                           ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 7)]))
    return t


def _image(png: bytes, max_w: float, max_h: float):
    from PIL import Image as PImage
    w, h = PImage.open(io.BytesIO(png)).size
    s = min(max_w / w, max_h / h)
    return Image(io.BytesIO(png), width=w * s, height=h * s)


def build_pdf(rw: dict, figures: dict[str, dict] | None = None, *, mode: str = 'text', mode_note: str = '',
              checklist: bool = True, paper: str = 'letter', source_names: list[str] | None = None) -> bytes:
    """rw: output of rewrite.normalize(). figures: id -> {'png': bytes, 'source': str, 'page': int|None}.

    mode 'standard' places the cleaned, numbered pictures; mode 'text' never places pictures.
    """
    st = _styles()
    figures = figures or {}
    size = A4 if str(paper).lower() == 'a4' else LETTER
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=size, leftMargin=0.8 * inch, rightMargin=0.8 * inch, topMargin=0.75 * inch,
                            bottomMargin=0.85 * inch, title=rw['title'], author='Manual Remake (Panda Federation)',
                            subject='Rewrite of an uploaded manual (not a certified replacement)')
    W = size[0] - 1.6 * inch
    story = []

    story.append(_p(rw['title'], st['title']))
    srcs = ', '.join(source_names or [])
    story.append(_p(f"Remade from your upload{(': ' + srcs) if srcs else ''} by Manual Remake (Panda Federation)", st['sub']))
    if rw.get('productSummary'):
        story.append(_p(rw['productSummary'], st['base']))
        story.append(Spacer(1, 8))

    glance = [
        [_p('Difficulty', st['cellb']), _p(f"{rw['difficulty']}" + (f" - {rw['difficultyReason']}" if rw.get('difficultyReason') else ''), st['cell'])],
        [_p('Time (estimate)', st['cellb']), _p(rw['timeEstimate'], st['cell'])],
        [_p('Steps', st['cellb']), _p(str(len(rw['steps'])), st['cell'])],
    ]
    if rw.get('people'):
        glance.append([_p('People', st['cellb']), _p(rw['people'], st['cell'])])
    if rw.get('toolsNeeded'):
        glance.append([_p('Tools', st['cellb']), _p(', '.join(rw['toolsNeeded']), st['cell'])])
    glance.append([_p('Edition', st['cellb']), _p('Standard: text plus your cleaned pictures with numbered callouts' if mode == 'standard'
                                                  else 'Text-only', st['cell'])])
    t = Table(glance, colWidths=[1.45 * inch, W - 1.45 * inch])
    t.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BBBBBB')), ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#EEF3F8')),
                           ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    story.append(t)
    if mode_note:
        story.append(Spacer(1, 6))
        story.append(_boxed(_p(mode_note, st['gap']), colors.HexColor('#999999'), colors.HexColor('#F5F5F5')))

    if rw['warnings']:
        story.append(_p('Warnings from the original manual', st['h2']))
        wl = [_p('\u26a0 ' + w['text'] if _FONT == 'DejaVu' else '! ' + w['text'], st['warn']) for w in rw['warnings']]
        story.append(_boxed(wl, WARN, colors.HexColor('#FFF3F3')))
    else:
        story.append(_p('Warnings', st['h2']))
        story.append(_p('The source did not include any warnings. That does not mean there are no risks; check the original packaging and product labels.', st['base']))

    if rw['parts']:
        story.append(_p('Parts list', st['h2']))
        rows = [[_p(h, st['cellb']) for h in (_BOX, 'Part', 'Name', 'Qty', 'Notes')]]
        for p in rw['parts']:
            rows.append([_p(_BOX, st['cell']), _p(p['id'], st['cellb']), _p(p['name'], st['cell']), _p(p['quantity'] or '?', st['cell']), _p(p['notes'], st['cell'])])
        t = Table(rows, colWidths=[0.4 * inch, 0.6 * inch, 2.6 * inch, 0.6 * inch, W - 4.2 * inch], repeatRows=1)
        t.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BBBBBB')), ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EEF3F8')),
                               ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
        story.append(t)
        story.append(_p('A "?" quantity means the source does not say how many.', st['small']))

    gaps_by = {}
    for g in rw['gaps']:
        gaps_by.setdefault(g['afterStep'], []).append(g)

    def gap_box(gs):
        fl = [_p('Missing or unclear in the source', ParagraphStyle('gh', parent=st['gap'], fontName=_BOLD, textColor=GAP))]
        for g in gs:
            fl.append(_p('- ' + g['issue'] + (f" ({g['suggestion']})" if g.get('suggestion') else ''), st['gap']))
        return _boxed(fl, GAP, colors.HexColor('#FFF8E1'))

    placed = set()
    usable = {f['id']: f for f in rw['figures'] if f['use'] and f['id'] in figures} if mode == 'standard' else {}
    fig_no = {}

    def fig_flow(fid):
        f = usable[fid]
        fig_no[fid] = len(fig_no) + 1
        meta = figures[fid]
        where = meta.get('source', '') + (f", page {meta['page']}" if meta.get('page') else '')
        steps = ', '.join(str(s) for s in f['steps'])
        cap = f"Figure {fig_no[fid]}" + (f": {f['caption']}" if f['caption'] else '') + (f". Red numbers match step {steps}." if steps else '.') + f" From your upload ({where})."
        return KeepTogether([_image(meta['png'], W, 4.2 * inch), Spacer(1, 3), _p(cap, st['cap'])])

    linked = {fid for s_ in rw['steps'] for fid in s_['figures']}
    rest = [fid for fid in usable if fid not in linked]
    if rest:  # pictures not tied to a step (often the parts overview) go right after the parts list
        for i, fid in enumerate(rest):
            placed.add(fid)
            story.append(KeepTogether([_p('Pictures from your upload', st['h2']), fig_flow(fid)]) if i == 0 else fig_flow(fid))

    story.append(PageBreak())
    story.append(_p('Steps', st['h2']))
    if 0 in gaps_by:
        story.append(gap_box(gaps_by[0]))
    for s in rw['steps']:
        block = [_p(f"{_BOX}  Step {s['number']}: {s['title']}", st['step'])]
        meta = []
        if s['parts']:
            meta.append('Parts: ' + ', '.join(s['parts']))
        if s['tools']:
            meta.append('Tools: ' + ', '.join(s['tools']))
        if meta:
            block.append(_p(' | '.join(meta), st['small']))
        for i, line in enumerate(s['instructions'], 1):
            block.append(_p(f'{i}. {line}', st['li']))
        if s['caution']:
            block.append(_p('Caution: ' + s['caution'], st['warn']))
        if s.get('sourceRef'):
            block.append(_p(f"Source: {s['sourceRef']}", st['small']))
        story.append(CondPageBreak(1.6 * inch))
        story.append(KeepTogether(block))
        for fid in s['figures']:
            if fid in usable and fid not in placed:
                placed.add(fid)
                story.append(fig_flow(fid))
        if s['number'] in gaps_by:
            story.append(Spacer(1, 4))
            story.append(gap_box(gaps_by[s['number']]))
    if not rw['steps']:
        story.append(_p('No step-by-step instructions could be found in the source.', st['base']))

    if rw['notes']:
        story.append(_p('Other notes from the source', st['h2']))
        for n in rw['notes']:
            story.append(_p('- ' + n, st['li']))

    if checklist and rw['steps']:
        story.append(PageBreak())
        story.append(_p('Checklist', st['h2']))
        story.append(_p('Tick each box as you go. Print this page on its own if you like.', st['small']))
        rows = []
        if rw['parts']:
            rows.append([_p(_BOX, st['cell']), _p('All parts from the parts list are here and undamaged', st['cell'])])
        if rw['warnings']:
            rows.append([_p(_BOX, st['cell']), _p('I have read the warnings', st['cell'])])
        for s in rw['steps']:
            rows.append([_p(_BOX, st['cell']), _p(f"Step {s['number']}: {s['title']}", st['cell'])])
        if rw['gaps']:
            rows.append([_p(_BOX, st['cell']), _p(f"I checked the {len(rw['gaps'])} missing/unclear point(s) against the original", st['cell'])])
        t = Table(rows, colWidths=[0.45 * inch, W - 0.45 * inch])
        t.setStyle(TableStyle([('LINEBELOW', (0, 0), (-1, -1), 0.4, colors.HexColor('#CCCCCC')), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                               ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5)]))
        story.append(t)

    story.append(Spacer(1, 14))
    story.append(_p('About this document', st['h2']))
    story.append(_p(SOURCE_NOTE, st['small']))

    def on_page(c, d):
        c.saveState()
        c.setFont(_FONT, 7.5)
        c.setFillColor(colors.HexColor('#666666'))
        c.drawString(0.8 * inch, 0.5 * inch, FOOTER)
        c.drawRightString(size[0] - 0.8 * inch, 0.5 * inch, f'Page {d.page}')
        c.restoreState()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()


def to_markdown(rw: dict, mode: str, mode_note: str = '') -> str:
    L = [f"# {rw['title']}", '', rw.get('productSummary', ''), '',
         f"- Difficulty: {rw['difficulty']}" + (f" ({rw['difficultyReason']})" if rw.get('difficultyReason') else ''),
         f"- Time (estimate): {rw['timeEstimate']}", f"- Edition: {'Standard' if mode == 'standard' else 'Text-only'}"]
    if mode_note:
        L += ['', f'> {mode_note}']
    if rw['warnings']:
        L += ['', '## Warnings'] + [f"- {w['text']}" for w in rw['warnings']]
    if rw['parts']:
        L += ['', '## Parts', '| Part | Name | Qty | Notes |', '|---|---|---|---|'] + [f"| {p['id']} | {p['name']} | {p['quantity'] or '?'} | {p['notes']} |" for p in rw['parts']]
    L += ['', '## Steps']
    for s in rw['steps']:
        L += ['', f"### - [ ] Step {s['number']}: {s['title']}"] + [f'{i}. {x}' for i, x in enumerate(s['instructions'], 1)]
        if s['caution']:
            L.append(f"**Caution:** {s['caution']}")
    if rw['gaps']:
        L += ['', '## Missing or unclear in the source'] + [f"- After step {g['afterStep']}: {g['issue']}" for g in rw['gaps']]
    L += ['', '---', SOURCE_NOTE]
    return '\n'.join(L) + '\n'
