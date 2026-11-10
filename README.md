# Manual Remake: rewrite a confusing manual into a clear, printable PDF

**Upload a PDF or photos of an existing instruction manual and get back a clearer English manual you can keep or print.** Manual Remake by Panda Federation rewrites the steps in plain English, cleans up the parts list, pulls every warning into one place, estimates difficulty and time, flags missing or unclear steps instead of guessing, adds a checklist, and (Standard edition) straightens, crops and cleans **your own pictures** and adds red numbered markers that match the rewritten steps. Three editions share one Actor: the free sample (no upload, no key, no charge), Text-only ($9 per successful run, pictures off), and Standard ($39 per successful run, pictures on). Steps to switch are in [Switch editions](#switch-editions).

This is a rewrite of the file you upload. It is not an official or certified replacement for the manufacturer's manual and makes no safety, standards or compliance claim.

## Part of [Panda Federation](https://pandafederation.com/)

[![Part of Panda Federation](https://pandafederation.com/assets/badge.svg)](https://pandafederation.com/)

This project is a module of the Panda Federation — public-data tools, MCP servers, and local-first apps in one catalog. See the rest of the work, including books when they publish and the matching free or paid editions of this tool, at the [official site](https://pandafederation.com/).

## How to use this

Open **[apify.com/pandadad0214/manual-remake](https://apify.com/pandadad0214/manual-remake)** (nothing to install; a free Apify account is enough for the free sample).

1. **Try it free:** click **Start** with **Manual files** and **Manual links** empty (or tick **Free sample**). You get a real remade PDF of a fictional demo manual, marked FREE SAMPLE, with no key and no charge.
2. **Remake your own manual:** upload your PDF or photos in **Manual files** (or paste **Manual links**) and paste your **LLM API key**.
3. **Pick the edition and Start:** leave **Reuse and clean pictures** on for Standard ($39 per successful run) or turn it off for Text-only ($9 per successful run). Download `OUTPUT.pdf` from the run.

Full switch steps between all three editions: [Switch editions](#switch-editions).

## For AI agents

| Field | Value |
| --- | --- |
| Purpose | Rewrite a confusing instruction manual (PDF or photos) into a clear, printable English PDF with steps, parts, warnings, gaps flagged and a checklist. |
| Use when | A user has an existing manual that is hard to follow and wants a finished document to keep or print. |
| Do not use when | The user needs an official, certified or safety-compliant manual, a non-English output, new artwork, or a live step-by-step chat walkthrough. |
| How to call | Apify MCP server `https://mcp.apify.com`, Actor `pandadad0214/manual-remake`; or the Apify API. |
| Inputs | `sampleMode` (free sample), `files` / `fileUrls` (up to 15 pages or photos), `includeImages` (Standard on, Text-only off), `llmApiKey`, optional `llmModel`, `llmBaseUrl`, `checklistMode`, `paperSize`, `title` |
| Outputs | `OUTPUT.pdf` (print PDF), Markdown, and a `SUMMARY` record with `switchEditions` steps |
| Cost | Free sample: free. Text-only: $9 per successful run. Standard: $39 per successful run. Refused or failed runs are not charged. |
| Side effects | Calls the model on the caller's own key for paid runs; the key is encrypted and never logged. |

## Releases

Tagged builds match the Apify Actor version (latest: [v0.1.3](https://github.com/pandadad0214/manual-remake/releases/latest)). There is nothing to install locally — run it on the [Apify Store](https://apify.com/pandadad0214/manual-remake).

## Use it on Apify

Manual Remake runs as an Apify Actor at [apify.com/pandadad0214/manual-remake](https://apify.com/pandadad0214/manual-remake). There is nothing to install. The same page runs all three editions: the free sample, Text-only ($9 per successful run), and Standard ($39 per successful run).

### Free sample (no upload, no key, no charge)

Click **Start** with **Manual files** and **Manual links** empty (or tick **Free sample**) and you get a real remade PDF of a short, fictional demo manual (the "Birchline ST-2 side table") that ships with the Actor. It shows the full layout: at-a-glance box, warnings, parts list, plain-English steps, flagged gaps, cleaned pictures with numbered markers and the checklist. The sample uses a pre-made rewrite, so no AI model is called, no key is needed and nothing is charged. The PDF and the run summary are clearly marked **FREE SAMPLE**: it is never presented as a remake of your file.

To remake your own manual, use a paid edition. A paid run always needs your own key. If you upload files without a key, the run stops and asks for one; it never swaps in the demo.

- **Text-only ($9 per successful run):** upload your PDF or photos in **Manual files** (or paste links in **Manual links**), paste your **LLM API key**, turn off **Reuse and clean pictures**, then **Start**.
- **Standard ($39 per successful run):** upload your PDF or photos in **Manual files** (or paste links in **Manual links**), paste your **LLM API key**, leave **Reuse and clean pictures** on, then **Start**.

### Text-only ($9 per successful run)

A paid remake of your own manual with pictures off: plain-English steps, parts list, warnings, difficulty and time, flagged gaps, and a checklist. You get this edition when **Reuse and clean pictures** is off, or when the upload has no usable pictures (the run is then priced as Text-only). Open it from the [Store page](https://apify.com/pandadad0214/manual-remake): upload your PDF or photos (or paste links), paste your **LLM API key**, turn off **Reuse and clean pictures**, then **Start**.

From a Text-only result you can open the other two editions on that same page:

- **Free sample (no charge):** leave **Manual files** and **Manual links** empty, or tick **Free sample**, then **Start**. No key needed. The PDF and summary are marked **FREE SAMPLE** (bundled fictional Birchline ST-2 demo).
- **Standard ($39 per successful run):** upload your PDF or photos (or paste links), paste your **LLM API key**, leave **Reuse and clean pictures** on, then **Start**.

### Standard ($39 per successful run)

A paid remake of your own manual with your pictures straightened, cropped, cleaned, and numbered to match the steps. This is the default. Open it from the [Store page](https://apify.com/pandadad0214/manual-remake): upload your PDF or photos (or paste links), paste your **LLM API key**, leave **Reuse and clean pictures** on, then **Start**.

From a Standard result you can open the other two editions on that same page:

- **Free sample (no charge):** leave **Manual files** and **Manual links** empty, or tick **Free sample**, then **Start**. No key needed. The PDF and summary are marked **FREE SAMPLE** (bundled fictional Birchline ST-2 demo).
- **Text-only ($9 per successful run):** upload your PDF or photos (or paste links), paste your **LLM API key**, turn off **Reuse and clean pictures**, then **Start**.

### Run a paid remake

1. Upload the manual in **Manual files** (PDF or photos of the pages), or paste direct public or share links in **Manual links**.
2. Paste your **LLM API key** (OpenAI, or any OpenAI-compatible provider with an https **LLM base URL**). Your own manual is always rewritten with your own key, so model usage is billed by your provider. The key is stored encrypted and never logged. If you upload files without a key, the run stops and asks for one; it never swaps in the demo.
3. Leave **Reuse and clean pictures** on for Standard, or turn it off for Text-only.
4. Click **Start**, then download **OUTPUT.pdf** from the run's **Output** tab (or **Storage → Key-value store**). The PDF and `SUMMARY` name the edition you got and spell out how to open the other two.

**Supported inputs:** files uploaded in the **Manual files** box, and direct public links (including Google Drive and Dropbox share links). Links to private Apify storage do not work, because the Actor runs with limited permissions and cannot read other stores in your account; upload the file instead.

**Model provider errors:** if your provider says the key is wrong, the model does not exist, or the account has no credit left (`insufficient_quota`), the run stops with that message and nothing is charged. Add credit or fix the key with your provider and run again.

### Pricing (pay per successful run)

| Edition | What you get | Price |
|---|---|---|
| **Standard** | Text remake + your pictures straightened, cropped, cleaned and numbered to match the steps | **$39 per run** |
| **Text-only** | Text remake: plain-English steps, parts list, warnings, difficulty/time, flagged gaps, checklist | **$9 per run** |

- You are charged once, only when the remade PDF is delivered.
- If your upload has no usable pictures (or you turn pictures off), the run is Text-only and priced as Text-only. The PDF and the run summary say so.
- Up to **15 pages or photos per run** (PDF pages plus extra photos; pictures inside a PDF page are not counted twice). Over 15, the run stops with a clear message and nothing is charged. Split longer manuals into several runs.
- Refused or failed runs cost nothing, and the free sample is always free.
- If your **Maximum cost per run** is below the edition's price, the run stops before calling your model, so you do not spend model credit on a remake that cannot be delivered.

### Switch editions

All three editions are the same Actor: [apify.com/pandadad0214/manual-remake](https://apify.com/pandadad0214/manual-remake).

| To open | Price | What you do |
|---|---|---|
| **Free sample** | No charge | Leave **Manual files** and **Manual links** empty, or tick **Free sample**, then **Start**. No LLM API key. You get the bundled fictional Birchline ST-2 demo. The PDF and summary are marked **FREE SAMPLE**. |
| **Text-only** | **$9 per successful run** | Upload your PDF or photos (or paste links), paste your **LLM API key**, turn off **Reuse and clean pictures**, then **Start**. |
| **Standard** | **$39 per successful run** | Upload your PDF or photos (or paste links), paste your **LLM API key**, leave **Reuse and clean pictures** on, then **Start**. |

A paid run of your own file always needs your own key. If you upload files without a key, the run stops and asks for one. It never swaps in the demo.

### Input examples

Free sample: `{}` or `{"sampleMode": true}`

Your own manual:

```json
{
  "fileUrls": ["https://example.com/side-table-manual.pdf"],
  "includeImages": true,
  "checklistMode": true,
  "paperSize": "letter",
  "llmApiKey": "<your key>",
  "llmModel": "gpt-4o-mini"
}
```

Text-only is the same input with `"includeImages": false` (turn off **Reuse and clean pictures**).

### What is in the PDF

- **At a glance:** difficulty (Easy / Moderate / Hard, with the reason), time estimate, people needed, tools
- **Warnings from the original manual**, kept in plain words and never softened
- **Parts list** with tick boxes; quantities the source does not give are shown as "?"
- **Steps** in plain English, one action per line, with parts and tools per step and the source page
- **Missing or unclear in the source** boxes where a step, value or part use is missing (nothing is invented: no made-up torque values, voltages, sizes or safety steps)
- **Your pictures, cleaned** (Standard): straightened, cropped, paper evened out, with red numbered markers matching the step numbers
- **Checklist page** to tick off as you go
- A footer on every page: *rewrite of your uploaded manual, not a certified replacement*
- **Switch editions** at the end (and on the free-sample banner): how to open the free sample, Text-only, and Standard, with the Store link

### Other outputs

| Key / view | What it is |
|---|---|
| `OUTPUT.pdf` | The print-friendly remade manual |
| `REMAKE.md` | The same content as Markdown |
| `REWRITE.json` | Structured rewrite (steps, parts, warnings, gaps, figures) |
| `fig-N.png` | Each cleaned picture with its numbered markers (Standard) |
| `SUMMARY` | Edition (`sample`, `text` or `standard`), `sample` flag, counts, pictures used or skipped and why, hidden text removed, what was charged, `takeaway`, and `switchEditions` (how to open the free sample, Text-only, and Standard) |
| Dataset (overview view) | An overview row, then one row per warning, part, step, gap and picture, each with a one-line `summary` |

### Hidden text in uploads

Some PDFs carry text people cannot see (white, microscopic, invisible or off-page text) or lines aimed at AI tools ("ignore previous instructions..."). Manual Remake removes that text before the rewrite (white text on a coloured warning banner and the invisible text layer of scanned PDFs are kept, because those are real content), tells the model to ignore any that slips through, never copies it into the output, and reports how many items were removed in `SUMMARY`.

### Good to know

- **English output only** in this version.
- **No new artwork:** only your own pictures are reused. Phone layout, video scripts and zoomed insets are not in this version.
- **Photos and scans:** pages without a text layer are read from the picture by the model, so use a model that accepts images (gpt-4o-mini does).
- **HEIC photos:** export them as JPEG or PNG first.
- How this differs from step-by-step chat helpers: those walk you through a manual on screen; Manual Remake gives you a finished document to keep, print or share.

## FAQ

**Is there a free way to try Manual Remake?** Yes. Leave **Manual files** and **Manual links** empty, or tick **Free sample**, then **Start**. You get a remade PDF of the bundled fictional Birchline ST-2 demo with no upload, no LLM key and no charge. The PDF and summary are marked **FREE SAMPLE**.

**How do I switch between free sample, Text-only and Standard?** All three editions are the same Actor. See [Switch editions](#switch-editions): empty upload (or **Free sample**) for free; upload + LLM key with **Reuse and clean pictures** off for Text-only; leave pictures on for Standard.

**Do I need my own AI key?** Only for paid remakes of your own file. The free sample never calls a model. Your key stays encrypted and is never logged.

**What if a paid run fails?** Refused or failed runs are not charged. If your run's maximum cost is below the edition price, the Actor stops before calling your model.

**Can an AI agent use it?** Yes, through Apify's MCP server (`https://mcp.apify.com`, Actor `pandadad0214/manual-remake`). Start with `{"sampleMode": true}` for the free sample; the `SUMMARY` record includes `switchEditions` steps for Text-only and Standard.

## For developers

Python 3.13 Actor (`apify/actor-python`). The pipeline is split so every stage except the model call can be tested offline:

| Module | Job |
|---|---|
| `src/extract.py` | Sniffs PDF vs image, enforces the 15-unit cap, extracts visible text (drops hidden/AI-directed text), pulls embedded pictures and renders scanned pages |
| `src/imaging.py` | Deskew (projection profile), crop to content, clean (paper to white, despeckle, contrast, sharpen), numbered callouts |
| `src/rewrite.py` | Prompt, OpenAI-compatible call on the user's key, and `normalize()` (renumbers steps, re-maps callouts, drops dangling references and AI-directed text) |
| `src/pdfout.py` | reportlab print PDF and Markdown |
| `src/pipeline.py` | Ties it together with an injectable `rewrite_fn` |
| `src/main.py` | Apify input, free sample mode, downloads, max-charge check before the model call, pay-per-event charging (`text-remake` / `standard-remake`, once per successful run, only after `OUTPUT.pdf` is saved), outputs |

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt pytest
.venv/bin/python tests/make_fixtures.py      # builds the fictional 3-page sample manual
.venv/bin/python -m pytest -q tests           # no model calls; uses tests/fixtures/rewrite_fixture.json
```

The free sample is bundled in `src/sample/` (the fictional manual and its pre-made rewrite); `tests/fixtures` holds the same manual plus a test-only rewrite. The sample manual is fictional and was written for this repo, including its drawings and a planted hidden line used to test the hidden-text filter.

Issues and ideas: open an issue on this repo.

Made by [Panda Federation](https://github.com/pandadad0214/panda-federation-tools).
