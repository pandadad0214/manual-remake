"""Manual Remake by Panda Federation: turn a PDF or photos of an existing manual into a clearer English manual
(print-friendly PDF) with a clean parts list, warnings, difficulty/time estimate, flagged gaps, a checklist and,
in the Standard edition, the user's own pictures cleaned up with numbered callouts that match the steps."""
from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import unquote, urlparse

import httpx
from apify import Actor

from .extract import PAGE_CAP, InputError, make_source
from .pipeline import run_pipeline
from .rewrite import DEFAULT_MODEL, call_llm

EV_TEXT, EV_STANDARD = 'text-remake', 'standard-remake'
MAX_BYTES = 50 * 1024 * 1024
UA = 'Mozilla/5.0 (compatible; PandaFederation-ManualRemake/0.1; +https://apify.com/pandadad0214)'


def norm_url(u: str) -> str:
    u = u.strip()
    m = re.match(r'https?://drive\.google\.com/(?:file/d/|open\?id=)([\w-]+)', u)
    if m:
        return f'https://drive.google.com/uc?export=download&id={m.group(1)}'
    m = re.match(r'https?://www\.dropbox\.com/(.+?)(\?.*)?$', u)
    if m:
        return f'https://www.dropbox.com/{m.group(1)}?dl=1'
    return u


def collect_refs(inp: dict) -> list[str]:
    refs = []
    for k in ('files', 'fileUrls'):
        for u in inp.get(k) or []:
            u = u.get('url') if isinstance(u, dict) else u
            if isinstance(u, str) and u.strip() and u.strip() not in refs:
                refs.append(u.strip())
    return refs


async def fetch(client: httpx.AsyncClient, ref: str) -> tuple[str, bytes]:
    if not ref.startswith(('http://', 'https://')):
        store_id, _, key = ref.rpartition('/')
        store = await Actor.open_key_value_store(id=store_id) if store_id else await Actor.open_key_value_store()
        data = await store.get_value(key)
        if data is None:
            raise InputError(f'File "{key}" was not found in key-value store "{store_id or "default"}".')
        if isinstance(data, str):
            data = data.encode('latin-1', 'ignore')
        if not isinstance(data, (bytes, bytearray)):
            raise InputError(f'Record "{key}" is not a file.')
        return key, bytes(data)
    url = norm_url(ref)
    headers = {'User-Agent': UA, 'Accept': 'application/pdf,image/*,*/*'}
    host = urlparse(url).hostname or ''
    if (host == 'apify.com' or host.endswith('.apify.com')) and Actor.configuration.token:
        headers['Authorization'] = f'Bearer {Actor.configuration.token}'
    buf = bytearray()
    try:
        async with client.stream('GET', url, headers=headers) as r:
            if r.status_code in (401, 403) and 'Authorization' in headers:
                headers.pop('Authorization')
                raise httpx.HTTPStatusError('retry', request=r.request, response=r)
            if r.status_code >= 400:
                raise InputError(f'Download failed for {url[:120]}: HTTP {r.status_code}.')
            async for chunk in r.aiter_bytes(1 << 16):
                buf += chunk
                if len(buf) > MAX_BYTES:
                    raise InputError(f'{url[:120]} is larger than 50 MB.')
            cd = r.headers.get('content-disposition', '')
            final = str(r.url)
    except httpx.HTTPStatusError:
        return await fetch_plain(client, url, headers)
    except httpx.HTTPError as e:
        raise InputError(f'Could not download {url[:120]} ({type(e).__name__}).') from e
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', cd)
    name = unquote(m.group(1)) if m else unquote(os.path.basename(urlparse(final).path)) or 'upload'
    return name[:120], bytes(buf)


async def fetch_plain(client, url, headers):
    r = await client.get(url, headers=headers)
    if r.status_code >= 400:
        raise InputError(f'Download failed for {url[:120]}: HTTP {r.status_code}.')
    if len(r.content) > MAX_BYTES:
        raise InputError(f'{url[:120]} is larger than 50 MB.')
    return (unquote(os.path.basename(urlparse(str(r.url)).path)) or 'upload')[:120], r.content


def dataset_rows(res: dict) -> list[dict]:
    rw, rows = res['rewrite'], []
    for w in rw['warnings']:
        rows.append({'type': 'warning', 'number': None, 'title': 'Warning', 'text': w['text'], 'sourceRef': w['sourceRef']})
    for p in rw['parts']:
        rows.append({'type': 'part', 'number': None, 'title': f"{p['id']} {p['name']}".strip(), 'text': f"Qty {p['quantity'] or '?'}" + (f"; {p['notes']}" if p['notes'] else ''), 'sourceRef': ''})
    for s in rw['steps']:
        rows.append({'type': 'step', 'number': s['number'], 'title': s['title'], 'text': ' '.join(s['instructions']), 'parts': s['parts'],
                     'tools': s['tools'], 'caution': s['caution'], 'figures': s['figures'] if res['mode'] == 'standard' else [], 'sourceRef': s['sourceRef']})
    for g in rw['gaps']:
        rows.append({'type': 'gap', 'number': g['afterStep'], 'title': f"Missing or unclear (after step {g['afterStep']})", 'text': g['issue'] + (f" ({g['suggestion']})" if g['suggestion'] else ''), 'sourceRef': ''})
    for f in res['figureRecords']:
        rows.append({'type': 'figure', 'number': None, 'title': f['id'], 'text': f['caption'], 'figureKey': f"{f['id']}.png",
                     'figureSteps': f['steps'], 'deskewDegrees': f['deskewDegrees'], 'sourceRef': f['source'] + (f", page {f['page']}" if f['page'] else '')})
    for r in rows:
        r['summary'] = f"{r['type']}{' ' + str(r['number']) if r['number'] is not None else ''}: {r['title']} | {r['text'][:160]}"
    return rows


async def fail(summary: dict, msg: str) -> None:
    summary.update({'status': 'failed', 'charged': 0, 'chargedEvent': None, 'takeaway': msg[:400], 'finishedAt': datetime.now(timezone.utc).isoformat(timespec='seconds')})
    await Actor.set_value('SUMMARY', summary)
    Actor.log.error(msg)
    await Actor.fail(status_message=msg[:900])


async def main() -> None:
    async with Actor:
        inp = await Actor.get_input() or {}
        summary = {'startedAt': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'pageCap': PAGE_CAP}
        refs = collect_refs(inp)
        if not refs:
            return await fail(summary, 'No manual to remake: add a PDF or photos in "Manual files" or a direct link in "Manual links", then run again. Nothing was charged.')
        api_key = (inp.get('llmApiKey') or '').strip()
        if not api_key:
            return await fail(summary, 'Missing "LLM API key": the rewrite runs on your own OpenAI-compatible key (it is stored encrypted and never logged). Nothing was charged.')
        model = (inp.get('llmModel') or DEFAULT_MODEL).strip()
        base = (inp.get('llmBaseUrl') or '').strip() or None
        include_images = inp.get('includeImages', True) is not False
        opts = {'includeImages': include_images, 'checklistMode': inp.get('checklistMode', True) is not False,
                'paperSize': 'a4' if str(inp.get('paperSize', 'letter')).lower() == 'a4' else 'letter', 'llmModel': model,
                'llmBaseUrl': 'custom' if base else 'default (OpenAI)', 'title': (inp.get('title') or '').strip() or None}
        summary['options'] = opts

        await Actor.set_status_message(f'Downloading {len(refs)} file(s)...')
        sources = []
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(120, connect=20)) as client:
                for ref in refs:
                    name, data = await fetch(client, ref)
                    sources.append(await asyncio.to_thread(make_source, name, data, inp.get('pdfPassword') or None))
        except InputError as e:
            return await fail(summary, f'{e} Nothing was charged.')

        cm = Actor.get_charging_manager()
        info = cm.get_pricing_info()
        ppe = bool(getattr(info, 'is_pay_per_event', False))

        async def rewrite_fn(messages):
            # the edition is known before the model call: make sure the run's max charge covers it first
            await Actor.set_status_message('Rewriting the manual (this usually takes 30-120 seconds)...')
            raw, usage = await call_llm(messages, api_key, model, base)
            summary['llmUsage'] = {k: usage.get(k) for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')}
            return raw

        def log(msg):
            Actor.log.info(msg)

        try:
            await Actor.set_status_message(f'Reading {len(sources)} file(s) and cleaning pictures...')
            from .extract import check_cap
            check_cap(sources)
            if ppe:
                ev = EV_STANDARD if include_images else EV_TEXT
                if cm.calculate_max_event_charge_count_within_limit(EV_TEXT) < 1:
                    return await fail(summary, 'The maximum charge per run is lower than the price of a text-only remake. Raise "Maximum cost per run" and try again. Nothing was charged.')
                summary['plannedEvent'] = ev
            res = await run_pipeline(sources, include_images=include_images, title=opts['title'], checklist=opts['checklistMode'],
                                     paper=opts['paperSize'], password=inp.get('pdfPassword') or None, rewrite_fn=rewrite_fn, log=log)
        except InputError as e:
            return await fail(summary, f'{e} Nothing was charged.')
        except Exception as e:  # noqa: BLE001
            Actor.log.exception('Remake failed')
            return await fail(summary, f'The remake failed ({type(e).__name__}: {str(e)[:200]}). Nothing was charged; try again or contact us via the Issues tab.')

        event = EV_STANDARD if res['mode'] == 'standard' else EV_TEXT
        if ppe and cm.calculate_max_event_charge_count_within_limit(event) < 1:
            return await fail(summary, f"This upload qualifies for the {'Standard' if event == EV_STANDARD else 'Text-only'} edition but the maximum charge per run is lower than its price. "
                                       'Raise "Maximum cost per run" (or turn off "Reuse and clean pictures" for the Text-only edition) and run again. Nothing was charged.')

        await Actor.set_value('OUTPUT.pdf', res['pdf'], content_type='application/pdf')
        await Actor.set_value('REMAKE.md', res['markdown'].encode('utf-8'), content_type='text/markdown; charset=utf-8')
        await Actor.set_value('REWRITE.json', res['rewrite'])
        for fid, f in res['figures'].items():
            await Actor.set_value(f'{fid}.png', f['png'], content_type='image/png')
        rows = dataset_rows(res)
        if rows:
            await Actor.push_data(rows)
        charged = 0
        if ppe:
            r = await Actor.charge(event_name=event, count=1)
            charged = getattr(r, 'charged_count', 1) if r is not None else 1
        rw = res['rewrite']
        edition = 'Standard (text + cleaned pictures with numbered callouts)' if res['mode'] == 'standard' else 'Text-only'
        take = (f"{edition} remake of {res['units']} page(s)/image(s): {len(rw['steps'])} steps, {len(rw['parts'])} parts, "
                f"{len(rw['warnings'])} warnings, {len(rw['gaps'])} gaps flagged" + (f", {len(res['figures'])} pictures" if res['figures'] else '')
                + '. Download OUTPUT.pdf.' + (f" {res['modeNote']}" if res['modeNote'] else ''))
        summary.update({
            'status': 'succeeded', 'edition': res['mode'], 'chargedEvent': event if charged else None, 'charged': charged,
            'modeNote': res['modeNote'], 'sources': res['sources'], 'pagesOrImages': res['units'], 'textPages': res['textPages'],
            'pagesReadFromPictures': res['scanPages'], 'usablePictures': res['usablePictures'], 'picturesPlaced': len(res['figures']),
            'skippedPictures': res['skippedImages'][:50], 'hiddenTextRemoved': len(res['hiddenRemoved']),
            'hiddenTextDetails': res['hiddenRemoved'][:50], 'title': rw['title'], 'difficulty': rw['difficulty'], 'timeEstimate': rw['timeEstimate'],
            'counts': {'steps': len(rw['steps']), 'parts': len(rw['parts']), 'warnings': len(rw['warnings']), 'gaps': len(rw['gaps']), 'figures': len(res['figures'])},
            'outputs': {'pdf': 'OUTPUT.pdf', 'markdown': 'REMAKE.md', 'rewriteJson': 'REWRITE.json', 'figures': [f'{k}.png' for k in res['figures']]},
            'takeaway': take[:400], 'finishedAt': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'disclaimer': 'Rewrite of the uploaded source, not a certified replacement. No standards or compliance certification is claimed.',
        })
        await Actor.set_value('SUMMARY', summary)
        await Actor.set_status_message(f"Done: {take[:300]}")
