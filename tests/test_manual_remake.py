"""Local tests for Manual Remake. No model calls: the rewrite comes from tests/fixtures/rewrite_fixture.json."""
import asyncio
import io
import json
import os
import subprocess
import sys

import pytest
from PIL import Image
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from src import imaging
from src.extract import PAGE_CAP, InputError, check_cap, count_units, extract, make_source
from src.pdfout import FOOTER, build_pdf
from src.pipeline import NOTE_NO_IMAGES, NOTE_OPT_OUT, run_pipeline
from src.rewrite import build_messages, normalize
from tests.make_fixtures import leg_diagram, parts_diagram

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, 'tests', 'fixtures')
SAMPLE = open(os.path.join(FIX, 'sample_manual.pdf'), 'rb').read()
PHOTO = open(os.path.join(FIX, 'sample_photo.jpg'), 'rb').read()
REWRITE = json.load(open(os.path.join(FIX, 'rewrite_fixture.json')))


def text_pdf(pages: int, text='Step 1. Put the panel on the floor and fix the legs with the screws provided.') -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for i in range(pages):
        c.drawString(72, 720, f'Page {i + 1}. {text}')
        c.showPage()
    c.save()
    return buf.getvalue()


def pdf_text(b: bytes) -> str:
    return '\n'.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(b)).pages)


async def fixture_rewrite(messages):
    fixture_rewrite.seen = messages
    return REWRITE


# 1. page/image cap -------------------------------------------------------------------------------------------

def test_cap_refuses_over_15_pdf_pages():
    s = make_source('big.pdf', text_pdf(16))
    assert s.pages == 16
    with pytest.raises(InputError) as e:
        check_cap([s])
    assert '16 pages/images' in str(e.value) and f'limit is {PAGE_CAP}' in str(e.value) and 'Nothing was processed or charged' in str(e.value)


def test_cap_counts_pdf_pages_plus_standalone_images_without_double_counting():
    pdf = make_source('sample_manual.pdf', SAMPLE)          # 3 pages, 2 embedded pictures
    imgs = [make_source(f'p{i}.jpg', PHOTO) for i in range(12)]
    assert count_units([pdf] + imgs) == 15                   # embedded pictures are not counted again
    check_cap([pdf] + imgs)                                  # exactly at the cap: allowed
    with pytest.raises(InputError):
        check_cap([pdf] + imgs + [make_source('extra.jpg', PHOTO)])


def test_cap_refusal_does_not_truncate_or_call_the_model():
    called = []

    async def rw(m):
        called.append(1)
        return REWRITE
    with pytest.raises(InputError):
        asyncio.run(run_pipeline([make_source('big.pdf', text_pdf(20))], rewrite_fn=rw, log=lambda *_: None))
    assert not called


# 2. text extraction ------------------------------------------------------------------------------------------

def test_text_extraction_from_sample_pdf():
    ex = extract([make_source('sample_manual.pdf', SAMPLE)])
    assert len(ex.pages) == 3 and all(p['hasTextLayer'] for p in ex.pages)
    assert 'choking hazard' in ex.pages[0]['text']
    assert 'corner hole of A' in ex.pages[1]['text']
    assert 'tighten all screw D' in ex.pages[2]['text']
    assert [f.page for f in ex.figures] == [1, 2]


def test_hidden_ai_text_is_removed_and_never_sent_to_the_model():
    ex = extract([make_source('sample_manual.pdf', SAMPLE)])
    reasons = {h['reason'] for h in ex.hiddenRemoved}
    assert {'white text', 'microscopic text'} <= reasons
    sent = json.dumps(build_messages(ex.pages, [])[1])                   # the source part (system prompt quotes examples)
    assert 'ignore previous instructions' not in sent and 'example.com/deal' not in sent


def test_normalize_drops_ai_directed_text_from_the_rewrite():
    rw = normalize(REWRITE, ['fig-1', 'fig-2'])
    assert all('coupon' not in n for n in rw['notes'])
    assert [s['number'] for s in rw['steps']] == [1, 2, 3, 4, 5]          # renumbered, gap kept as a flag
    assert rw['gaps'][0]['afterStep'] == 3 and rw['gaps'][1]['afterStep'] == 4
    fig2 = next(f for f in rw['figures'] if f['id'] == 'fig-2')
    assert [c['step'] for c in fig2['callouts']] == [2, 3]


# 3. image crop / deskew / clean / callouts --------------------------------------------------------------------

@pytest.mark.parametrize('angle', [-6, -3, 0, 4])
def test_deskew_recovers_rotation(angle):
    est = imaging.estimate_skew(leg_diagram(angle))
    assert abs(est + angle) <= 0.6


def test_crop_removes_empty_margin_and_clean_whitens_paper():
    im = parts_diagram(0)
    out, info = imaging.prepare(im)
    assert out.width < im.width * 0.75 and out.height < im.height * 0.75
    assert imaging.background_level(out) > 245                          # yellowed paper pushed to white
    assert imaging.usability(out)[0]


def test_unusable_images_are_rejected():
    assert not imaging.usability(Image.new('RGB', (60, 60), 'white'))[0]
    assert not imaging.usability(Image.new('RGB', (800, 800), (200, 200, 200)))[0]


def test_numbered_callouts_drawn_at_positions():
    base = Image.new('RGB', (600, 400), 'white')
    out = imaging.overlay_callouts(base, [{'step': 2, 'x': 0.25, 'y': 0.5}, {'step': 7}])
    assert out.size == base.size
    ring = out.crop((150 - 17, 200 - 17, 150 + 17, 200 + 17))
    assert any(p[0] > 180 and p[1] < 90 for p in ring.getdata())        # red marker at (0.25, 0.5)
    left = out.crop((0, 0, 80, 400))
    assert any(p[0] > 180 and p[1] < 90 for p in left.getdata())        # positionless callout on the left edge
    assert imaging.overlay_callouts(base, []).tobytes() == base.tobytes()


# 4. print PDF from fixture rewrite (no LLM) -----------------------------------------------------------------

def test_print_pdf_from_fixture_rewrite_standard():
    rw = normalize(REWRITE, ['fig-1', 'fig-2'])
    im, _ = imaging.prepare(leg_diagram(-3))
    figs = {'fig-2': {'png': imaging.to_png(imaging.overlay_callouts(im, rw['figures'][1]['callouts'])), 'source': 'sample_manual.pdf', 'page': 2}}
    pdf = build_pdf(rw, figs, mode='standard', checklist=True, source_names=['sample_manual.pdf'])
    assert pdf.startswith(b'%PDF')
    txt = pdf_text(pdf)
    for needle in ('Birchline ST-2', 'Parts list', 'Warnings from the original manual', 'choking hazard', 'Step 5: Stand the table up',
                   'Missing or unclear in the source', 'Checklist', 'not a certified replacement', 'Easy', '20-30 minutes', 'Figure 1'):
        assert needle in txt, needle
    assert 'coupon' not in txt
    assert 'ANSI' not in txt and 'OSHA' not in txt
    assert any(len(p.images) for p in PdfReader(io.BytesIO(pdf)).pages)


def test_full_pipeline_standard_with_fixture_rewrite():
    res = asyncio.run(run_pipeline([make_source('sample_manual.pdf', SAMPLE)], rewrite_fn=fixture_rewrite, log=lambda *_: None))
    assert res['mode'] == 'standard' and set(res['figures']) == {'fig-1', 'fig-2'}
    assert res['usablePictures'] == 2 and len(res['hiddenRemoved']) >= 2
    assert FOOTER.split('.')[0] in pdf_text(res['pdf'])
    open(os.path.join(ROOT, 'tests', 'output_standard.pdf'), 'wb').write(res['pdf'])


# 5. empty / missing input ------------------------------------------------------------------------------------

def test_empty_input_rejected():
    with pytest.raises(InputError) as e:
        check_cap([])
    assert 'No manual to remake' in str(e.value)
    with pytest.raises(InputError, match='empty'):
        make_source('x.pdf', b'')
    with pytest.raises(InputError, match='not a PDF or a supported image'):
        make_source('notes.txt', b'hello there')
    with pytest.raises(InputError, match='web page'):
        make_source('page', b'<!DOCTYPE html><html></html>')


def _summary(kv):
    for name in ('SUMMARY.json', 'SUMMARY'):
        if (kv / name).exists():
            return json.loads((kv / name).read_text())
    return None


def _out_pdf(kv):
    for name in ('OUTPUT.pdf', 'OUTPUT.pdf.pdf'):
        if (kv / name).exists():
            return (kv / name).read_bytes()
    return None


def _run_actor(tmp_path, inp):
    store = tmp_path / 'storage'
    kv = store / 'key_value_stores' / 'default'
    kv.mkdir(parents=True)
    (kv / 'INPUT.json').write_text(json.dumps(inp))
    env = {**os.environ, 'APIFY_LOCAL_STORAGE_DIR': str(store), 'CRAWLEE_STORAGE_DIR': str(store), 'APIFY_PURGE_ON_START': '0',
           'CRAWLEE_PURGE_ON_START': '0'}
    p = subprocess.run([sys.executable, '-m', 'src'], cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)
    return p, _summary(kv)


def test_actor_rejects_empty_input(tmp_path):
    p, summ = _run_actor(tmp_path, {})
    assert p.returncode != 0
    assert summ and summ['status'] == 'failed' and summ['charged'] == 0 and 'No manual to remake' in summ['takeaway']


def test_actor_rejects_missing_api_key(tmp_path):
    (tmp_path / 'm.pdf').write_bytes(text_pdf(2))
    p, summ = _run_actor(tmp_path, {'fileUrls': ['https://example.invalid/m.pdf']})
    assert p.returncode != 0 and 'Missing "LLM API key"' in summ['takeaway'] and summ['charged'] == 0


def test_actor_refuses_over_cap_before_model(tmp_path):
    store_dir = tmp_path / 'storage' / 'key_value_stores' / 'default'
    store_dir.mkdir(parents=True)
    (store_dir / 'big.pdf').write_bytes(text_pdf(16))
    (store_dir / 'big.pdf.__metadata__.json').write_text(json.dumps({'key': 'big.pdf', 'contentType': 'application/pdf'}))
    inp = {'files': ['big.pdf'], 'llmApiKey': 'sk-test-not-a-real-key', 'llmBaseUrl': 'http://127.0.0.1:9/v1'}
    (store_dir / 'INPUT.json').write_text(json.dumps(inp))
    env = {**os.environ, 'APIFY_LOCAL_STORAGE_DIR': str(tmp_path / 'storage'), 'CRAWLEE_STORAGE_DIR': str(tmp_path / 'storage'),
           'APIFY_PURGE_ON_START': '0', 'CRAWLEE_PURGE_ON_START': '0'}
    p = subprocess.run([sys.executable, '-m', 'src'], cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)
    summ = _summary(store_dir)
    assert p.returncode != 0 and '16 pages/images' in summ['takeaway'] and summ['charged'] == 0
    assert 'sk-test' not in p.stdout + p.stderr                         # the key is never logged
    assert _out_pdf(store_dir) is None


# 6. text-only path -------------------------------------------------------------------------------------------

def test_text_only_when_images_turned_off():
    res = asyncio.run(run_pipeline([make_source('sample_manual.pdf', SAMPLE)], include_images=False, rewrite_fn=fixture_rewrite, log=lambda *_: None))
    assert res['mode'] == 'text' and res['modeNote'] == NOTE_OPT_OUT and not res['figures']
    txt = pdf_text(res['pdf'])
    assert 'Text-only edition' in txt and 'Figure' not in txt
    assert not any(len(p.images) for p in PdfReader(io.BytesIO(res['pdf'])).pages)
    assert not any(c.get('type') == 'image_url' for c in fixture_rewrite.seen[1]['content'])


def test_text_only_when_no_usable_images():
    res = asyncio.run(run_pipeline([make_source('plain.pdf', text_pdf(3))], include_images=True, rewrite_fn=fixture_rewrite, log=lambda *_: None))
    assert res['mode'] == 'text' and res['modeNote'] == NOTE_NO_IMAGES
    assert 'no usable pictures were found' in pdf_text(res['pdf'])


def test_actor_summary_says_text_only(tmp_path, monkeypatch):
    """Runs main() end to end with the model call replaced by the fixture, and checks the SUMMARY record."""
    store = tmp_path / 'storage'
    kv = store / 'key_value_stores' / 'default'
    kv.mkdir(parents=True)
    (kv / 'plain.pdf').write_bytes(text_pdf(3))
    (kv / 'plain.pdf.__metadata__.json').write_text(json.dumps({'key': 'plain.pdf', 'contentType': 'application/pdf'}))
    (kv / 'INPUT.json').write_text(json.dumps({'files': ['plain.pdf'], 'llmApiKey': 'sk-test-not-a-real-key'}))
    code = ("import asyncio, json, src.main as m\n"
            "async def fake(messages, key, model, base):\n    return json.load(open('tests/fixtures/rewrite_fixture.json')), {}\n"
            "m.call_llm = fake\nasyncio.run(m.main())\n")
    env = {**os.environ, 'APIFY_LOCAL_STORAGE_DIR': str(store), 'CRAWLEE_STORAGE_DIR': str(store), 'APIFY_PURGE_ON_START': '0', 'CRAWLEE_PURGE_ON_START': '0'}
    p = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)
    assert p.returncode == 0, p.stderr[-2000:]
    summ = _summary(kv)
    assert summ['status'] == 'succeeded' and summ['edition'] == 'text'
    assert 'Text-only' in summ['takeaway'] and 'no usable pictures' in summ['takeaway']
    assert _out_pdf(kv).startswith(b'%PDF')
