"""Manual Remake by Panda Federation: turn a PDF or photos of an existing manual into a clearer English manual
(print-friendly PDF) with a clean parts list, warnings, difficulty/time estimate, flagged gaps, a checklist and,
in the Standard edition, the user's own pictures cleaned up with numbered callouts that match the steps."""

from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import UTC, datetime
from urllib.parse import unquote, urlparse

import httpx
from apify import Actor

from .editions import KEY_RULE, STEP_STANDARD, STEP_TEXT, switch_editions
from .extract import PAGE_CAP, InputError, check_cap, make_source
from .pipeline import run_pipeline
from .rewrite import DEFAULT_MODEL, call_llm

EV_TEXT, EV_STANDARD = "text-remake", "standard-remake"
MAX_BYTES = 50 * 1024 * 1024
HINT_403 = (
    ' Use the "Manual files" upload box or a public / share link. Private Apify storage links do not work because '
    "the Actor runs with limited permissions."
)
SAMPLE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample")
SAMPLE_NAME = "Birchline ST-2 demo manual (fictional sample).pdf"
SAMPLE_BANNER = (
    "FREE SAMPLE: this PDF was made from the bundled, fictional Birchline ST-2 demo manual, not from a file you "
    "uploaded. " + STEP_TEXT + " " + STEP_STANDARD + " " + KEY_RULE
)
SAMPLE_FOOTER = "Free sample made from a fictional demo manual (not your upload). Not a certified manual."
SAMPLE_NOTE = (
    "This free sample was made by Manual Remake (Panda Federation) from a short fictional demo manual that ships "
    "with the Actor, using a pre-made rewrite (no AI model was called and nothing was charged). A real remake "
    "rewrites your own upload with your own model key. Remakes are rewrites of the uploaded source, not official "
    "or certified replacements, and make no safety, standards or compliance claim."
)
UA = "Mozilla/5.0 (compatible; PandaFederation-ManualRemake/0.1; +https://apify.com/pandadad0214)"


def norm_url(u: str) -> str:
    u = u.strip()
    m = re.match(r"https?://drive\.google\.com/(?:file/d/|open\?id=)([\w-]+)", u)
    if m:
        return f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    m = re.match(r"https?://www\.dropbox\.com/(.+?)(\?.*)?$", u)
    if m:
        return f"https://www.dropbox.com/{m.group(1)}?dl=1"
    return u


def show_url(u: str) -> str:
    """URL for messages and logs: no query string (signed links carry a signature there), max 100 chars."""
    return re.sub(r"[?#].*$", "", u)[:100]


def collect_refs(inp: dict) -> list[str]:
    refs = []
    for k in ("files", "fileUrls"):
        for u in inp.get(k) or []:
            u = u.get("url") if isinstance(u, dict) else u
            if isinstance(u, str) and u.strip() and u.strip() not in refs:
                refs.append(u.strip())
    return refs


async def fetch(client: httpx.AsyncClient, ref: str) -> tuple[str, bytes]:
    if not ref.startswith(("http://", "https://")):
        store_id, _, key = ref.rpartition("/")
        try:
            store = await Actor.open_key_value_store(id=store_id) if store_id else await Actor.open_key_value_store()
            data = await store.get_value(key)
        except Exception as e:
            raise InputError(
                f'Could not read "{key}" from key-value store "{store_id or "default"}" ({type(e).__name__}).'
                + HINT_403
            ) from e
        if data is None:
            raise InputError(f'File "{key}" was not found in key-value store "{store_id or "default"}".')
        if isinstance(data, str):
            data = data.encode("latin-1", "ignore")
        if not isinstance(data, (bytes, bytearray)):
            raise InputError(f'Record "{key}" is not a file.')
        return key, bytes(data)
    url = norm_url(ref)
    headers = {"User-Agent": UA, "Accept": "application/pdf,image/*,*/*"}
    host = urlparse(url).hostname or ""
    if (host == "apify.com" or host.endswith(".apify.com")) and Actor.configuration.token:
        headers["Authorization"] = f"Bearer {Actor.configuration.token}"
    buf = bytearray()
    try:
        async with client.stream("GET", url, headers=headers) as r:
            if r.status_code in (401, 403) and "Authorization" in headers:
                headers.pop("Authorization")
                raise httpx.HTTPStatusError("retry", request=r.request, response=r)
            if r.status_code >= 400:
                raise InputError(
                    f"Download failed for {show_url(url)}: HTTP {r.status_code}."
                    + (HINT_403 if r.status_code in (401, 403) else "")
                )
            async for chunk in r.aiter_bytes(1 << 16):
                buf += chunk
                if len(buf) > MAX_BYTES:
                    raise InputError(f"{show_url(url)} is larger than 50 MB.")
            cd = r.headers.get("content-disposition", "")
            final = str(r.url)
    except httpx.HTTPStatusError:
        return await fetch_plain(client, url, headers)
    except httpx.HTTPError as e:
        raise InputError(f"Could not download {show_url(url)} ({type(e).__name__}).") from e
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', cd)
    name = unquote(m.group(1)) if m else unquote(os.path.basename(urlparse(final).path)) or "upload"
    return name[:120], bytes(buf)


async def fetch_plain(client, url, headers):
    r = await client.get(url, headers=headers)
    if r.status_code >= 400:
        raise InputError(
            f"Download failed for {show_url(url)}: HTTP {r.status_code}."
            + (HINT_403 if r.status_code in (401, 403) else "")
        )
    if len(r.content) > MAX_BYTES:
        raise InputError(f"{show_url(url)} is larger than 50 MB.")
    return (unquote(os.path.basename(urlparse(str(r.url)).path)) or "upload")[:120], r.content


def dataset_rows(res: dict) -> list[dict]:
    rw, rows = res["rewrite"], []
    for w in rw["warnings"]:
        rows.append(
            {"type": "warning", "number": None, "title": "Warning", "text": w["text"], "sourceRef": w["sourceRef"]}
        )
    for p in rw["parts"]:
        rows.append(
            {
                "type": "part",
                "number": None,
                "title": f"{p['id']} {p['name']}".strip(),
                "text": f"Qty {p['quantity'] or '?'}" + (f"; {p['notes']}" if p["notes"] else ""),
                "sourceRef": "",
            }
        )
    for s in rw["steps"]:
        rows.append(
            {
                "type": "step",
                "number": s["number"],
                "title": s["title"],
                "text": " ".join(s["instructions"]),
                "parts": s["parts"],
                "tools": s["tools"],
                "caution": s["caution"],
                "figures": s["figures"] if res["mode"] == "standard" else [],
                "sourceRef": s["sourceRef"],
            }
        )
    for g in rw["gaps"]:
        rows.append(
            {
                "type": "gap",
                "number": g["afterStep"],
                "title": f"Missing or unclear (after step {g['afterStep']})",
                "text": g["issue"] + (f" ({g['suggestion']})" if g["suggestion"] else ""),
                "sourceRef": "",
            }
        )
    for f in res["figureRecords"]:
        rows.append(
            {
                "type": "figure",
                "number": None,
                "title": f["id"],
                "text": f["caption"],
                "figureKey": f"{f['id']}.png",
                "figureSteps": f["steps"],
                "deskewDegrees": f["deskewDegrees"],
                "sourceRef": f["source"] + (f", page {f['page']}" if f["page"] else ""),
            }
        )
    overview = {
        "type": "overview",
        "number": None,
        "title": rw["title"],
        "text": f"{'Free sample' if res.get('sample') else ('Standard' if res['mode'] == 'standard' else 'Text-only')} edition; "  # noqa: E501
        f"difficulty {rw['difficulty']}; time {rw['timeEstimate']}; {len(rw['steps'])} steps, {len(rw['parts'])} parts, "  # noqa: E501
        f"{len(rw['warnings'])} warnings, {len(rw['gaps'])} gaps. PDF: OUTPUT.pdf",
        "sourceRef": ", ".join(res["sources"]),
    }
    rows.insert(0, overview)
    for r in rows:
        r["summary"] = (
            f"{r['type']}{' ' + str(r['number']) if r['number'] is not None else ''}: {r['title']} | {r['text'][:160]}"
        )
    return rows


def _nc(e) -> str:
    m = str(e)
    return m if "charged" in m else f"{m} Nothing was charged."


async def fail(summary: dict, msg: str) -> None:
    summary.update(
        {
            "status": "failed",
            "charged": 0,
            "chargedEvent": None,
            "takeaway": msg[:400],
            "finishedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        }
    )
    await Actor.set_value("SUMMARY", summary)
    Actor.log.error(msg)
    await Actor.fail(status_message=msg[:900])


async def main() -> None:
    async with Actor:
        inp = await Actor.get_input() or {}
        summary = {"startedAt": datetime.now(UTC).isoformat(timespec="seconds"), "pageCap": PAGE_CAP}
        refs = collect_refs(inp)
        sample = bool(inp.get("sampleMode")) or not refs
        api_key = "" if sample else str(inp.get("llmApiKey") or "").strip()
        model = (inp.get("llmModel") or DEFAULT_MODEL).strip()
        base = (inp.get("llmBaseUrl") or "").strip() or None
        include_images = inp.get("includeImages", True) is not False
        opts = {
            "sampleMode": sample,
            "includeImages": include_images,
            "checklistMode": inp.get("checklistMode", True) is not False,
            "paperSize": "a4" if str(inp.get("paperSize", "letter")).lower() == "a4" else "letter",
            "llmModel": None if sample else model,
            "llmBaseUrl": None if sample else ("custom" if base else "default (OpenAI)"),
            "title": (inp.get("title") or "").strip() or None,
        }
        summary["options"] = opts
        if not sample and base and not re.match(r"^(https://|http://(localhost|127\.0\.0\.1)[:/])", base):
            return await fail(
                summary,
                '"LLM base URL" must start with https:// so your key is never sent unencrypted '
                "(for example https://api.openai.com/v1). Nothing was charged.",
            )

        if sample:
            if refs:
                Actor.log.warning(
                    'Free sample mode is on: your files/links were NOT processed. Turn "Free sample" off to remake them.'  # noqa: E501
                )
                summary["ignoredInputs"] = len(refs)
            sources = [make_source(SAMPLE_NAME, open(os.path.join(SAMPLE_DIR, "sample_manual.pdf"), "rb").read())]
            fixture = json.load(open(os.path.join(SAMPLE_DIR, "sample_rewrite.json")))

            async def sample_rewrite(messages):
                return fixture

            await Actor.set_status_message(
                "Making the free sample from the bundled demo manual (no model call, no charge)..."
            )
            try:
                res = await run_pipeline(
                    sources,
                    include_images=include_images,
                    title="Free sample: " + (opts["title"] or fixture["title"]),
                    checklist=opts["checklistMode"],
                    paper=opts["paperSize"],
                    rewrite_fn=sample_rewrite,
                    log=Actor.log.info,
                    banner=SAMPLE_BANNER,
                    footer=SAMPLE_FOOTER,
                    origin="the bundled sample manual",
                    source_note=SAMPLE_NOTE,
                    sample=True,
                )
            except Exception as e:
                Actor.log.exception("Sample failed")
                return await fail(
                    summary,
                    f"The free sample could not be built ({type(e).__name__}). Please report it in the Issues tab.",
                )
            res["sample"] = True
            await save_outputs(res)
            take = (
                f"FREE SAMPLE (not your upload): remake of the bundled fictional Birchline ST-2 demo manual, "
                f"{'Standard' if res['mode'] == 'standard' else 'Text-only'} layout. Download OUTPUT.pdf. Nothing was charged. "  # noqa: E501
                "To remake your own manual, upload it and add your own LLM API key."
            )
            await finish_summary(summary, res, None, 0, take, sample=True)
            await Actor.set_status_message(take[:300])
            return

        if len(refs) > PAGE_CAP:
            return await fail(
                summary,
                f"This run has {len(refs)} files/links; the limit is {PAGE_CAP} pages or photos per run. "
                "Nothing was downloaded, processed or charged. Split the manual into several runs.",
            )
        if not api_key:
            return await fail(
                summary,
                'Missing "LLM API key": your own manual is rewritten with your own OpenAI-compatible key '
                '(stored encrypted, never logged). Add it and run again, or turn on "Free sample" to see a demo. '
                "Your files were not processed and nothing was charged.",
            )

        await Actor.set_status_message(f"Downloading {len(refs)} file(s)...")
        sources = []
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(120, connect=20)) as client:
                for ref in refs:
                    name, data = await fetch(client, ref)
                    sources.append(await asyncio.to_thread(make_source, name, data, inp.get("pdfPassword") or None))
            check_cap(sources)
        except InputError as e:
            return await fail(summary, _nc(e))

        cm = Actor.get_charging_manager()
        ppe = bool(getattr(cm.get_pricing_info(), "is_pay_per_event", False))

        async def before_rewrite(mode: str):
            # the edition is known before the model call: refuse now if the run's max charge cannot cover it,
            # so the user does not spend model credit on a remake we could not deliver
            ev = EV_STANDARD if mode == "standard" else EV_TEXT
            summary["plannedEvent"] = ev
            if ppe and not affordable(cm, ev):
                hint = ' or turn off "Reuse and clean pictures" for the Text-only edition' if ev == EV_STANDARD else ""
                raise InputError(
                    f"The maximum charge per run is lower than the price of this "
                    f'{"Standard" if ev == EV_STANDARD else "Text-only"} remake. Raise "Maximum cost per run"{hint} and run again. '  # noqa: E501
                    "The model was not called and nothing was charged."
                )
            await Actor.set_status_message("Rewriting the manual (this usually takes 30-120 seconds)...")

        async def rewrite_fn(messages):
            raw, usage = await call_llm(messages, api_key, model, base)
            summary["llmUsage"] = {k: usage.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
            return raw

        try:
            await Actor.set_status_message(f"Reading {len(sources)} file(s) and cleaning pictures...")
            res = await run_pipeline(
                sources,
                include_images=include_images,
                title=opts["title"],
                checklist=opts["checklistMode"],
                paper=opts["paperSize"],
                password=inp.get("pdfPassword") or None,
                rewrite_fn=rewrite_fn,
                log=Actor.log.info,
                before_rewrite=before_rewrite,
            )
        except InputError as e:
            return await fail(summary, _nc(e))
        except Exception as e:
            Actor.log.error(f"Remake failed: {type(e).__name__}")
            return await fail(
                summary,
                f"The remake failed ({type(e).__name__}: {redact(str(e), api_key)[:200]}). Nothing was charged; "
                "try again or report it in the Issues tab.",
            )

        event = EV_STANDARD if res["mode"] == "standard" else EV_TEXT
        if ppe and not affordable(cm, event):
            return await fail(
                summary,
                'The maximum charge per run is lower than the price of this remake. Raise "Maximum cost per run" and run again. Nothing was charged.',  # noqa: E501
            )

        await save_outputs(res)  # OUTPUT.pdf is stored before anything is charged
        charged = 0
        if ppe:
            r = await Actor.charge(event_name=event, count=1)
            charged = getattr(r, "charged_count", 1) if r is not None else 1
        rw = res["rewrite"]
        edition = (
            "Standard (text + cleaned pictures with numbered callouts)" if res["mode"] == "standard" else "Text-only"
        )
        take = (
            f"{edition} remake of {res['units']} page(s)/image(s): {len(rw['steps'])} steps, {len(rw['parts'])} parts, "
            f"{len(rw['warnings'])} warnings, {len(rw['gaps'])} gaps flagged"
            + (f", {len(res['figures'])} pictures" if res["figures"] else "")
            + ". Download OUTPUT.pdf."
            + (f" {res['modeNote']}" if res["modeNote"] else "")
        )
        await finish_summary(summary, res, event if charged else None, charged, take)
        await Actor.set_status_message(f"Done: {take[:300]}")


def affordable(cm, event: str) -> bool:
    """Can the run's maximum charge still cover one `event`? None from the SDK means no limit / unknown price."""
    n = cm.calculate_max_event_charge_count_within_limit(event)
    return n is None or n >= 1


def redact(text: str, secret: str) -> str:
    return text.replace(secret, "***") if secret else text


async def save_outputs(res: dict) -> None:
    await Actor.set_value("OUTPUT.pdf", res["pdf"], content_type="application/pdf")
    await Actor.set_value("REMAKE.md", res["markdown"].encode("utf-8"), content_type="text/markdown; charset=utf-8")
    await Actor.set_value("REWRITE.json", res["rewrite"])
    for fid, f in res["figures"].items():
        await Actor.set_value(f"{fid}.png", f["png"], content_type="image/png")
    rows = dataset_rows(res)
    if rows:
        await Actor.push_data(rows)


async def finish_summary(summary: dict, res: dict, event, charged: int, take: str, sample: bool = False) -> None:
    rw = res["rewrite"]
    nav = switch_editions("sample" if sample else res["mode"])
    if nav not in take:
        take = f"{take} {nav}"
    summary.update(
        {
            "status": "succeeded",
            "sample": sample,
            "edition": "sample" if sample else res["mode"],
            "layout": res["mode"],
            "chargedEvent": event,
            "charged": charged,
            "modeNote": res["modeNote"],
            "sources": res["sources"],
            "pagesOrImages": res["units"],
            "textPages": res["textPages"],
            "pagesReadFromPictures": res["scanPages"],
            "usablePictures": res["usablePictures"],
            "picturesPlaced": len(res["figures"]),
            "skippedPictures": res["skippedImages"][:50],
            "hiddenTextRemoved": len(res["hiddenRemoved"]),
            "hiddenTextDetails": res["hiddenRemoved"][:50],
            "title": rw["title"],
            "difficulty": rw["difficulty"],
            "timeEstimate": rw["timeEstimate"],
            "counts": {
                "steps": len(rw["steps"]),
                "parts": len(rw["parts"]),
                "warnings": len(rw["warnings"]),
                "gaps": len(rw["gaps"]),
                "figures": len(res["figures"]),
            },
            "outputs": {
                "pdf": "OUTPUT.pdf",
                "markdown": "REMAKE.md",
                "rewriteJson": "REWRITE.json",
                "figures": [f"{k}.png" for k in res["figures"]],
            },
            "switchEditions": nav,
            "takeaway": take[:2000],
            "finishedAt": datetime.now(UTC).isoformat(timespec="seconds"),
            "disclaimer": "Rewrite of the uploaded source, not a certified replacement. No standards or compliance certification is claimed."  # noqa: E501
            if not sample
            else "Free sample made from a fictional demo manual bundled with the Actor; not a remake of any upload; nothing charged.",  # noqa: E501
        }
    )
    await Actor.set_value("SUMMARY", summary)
