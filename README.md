# Manual Remake: rewrite a confusing manual into a clear, printable PDF

**Upload a PDF or photos of an existing instruction manual and get back a clearer English manual you can keep or print.** Manual Remake by Panda Federation rewrites the steps in plain English, cleans up the parts list, pulls every warning into one place, estimates difficulty and time, flags missing or unclear steps instead of guessing, adds a checklist, and (Standard edition) straightens, crops and cleans **your own pictures** and adds red numbered markers that match the rewritten steps.

This is a rewrite of the file you upload. It is not an official or certified replacement for the manufacturer's manual and makes no safety, standards or compliance claim.

## Use it on Apify

Manual Remake runs as an Apify Actor (publishing soon at `apify.com/pandadad0214/manual-remake`). There is nothing to install.

1. Open the Actor and click **Try for free** / **Start**.
2. Upload the manual in **Manual files** (PDF or photos of the pages), or paste direct links in **Manual links**.
3. Paste your **LLM API key** (OpenAI, or any OpenAI-compatible provider with **LLM base URL**). The rewrite runs on your key, so model usage is billed by your provider. The key is stored encrypted and never logged.
4. Leave **Reuse and clean pictures** on for the Standard edition, or turn it off for a Text-only edition.
5. Click **Start**, then download **OUTPUT.pdf** from the run's **Output** tab (or **Storage → Key-value store**).

### Pricing (pay per successful run)

| Edition | What you get | Price |
|---|---|---|
| **Standard** | Text remake + your pictures straightened, cropped, cleaned and numbered to match the steps | **$39 per run** |
| **Text-only** | Text remake: plain-English steps, parts list, warnings, difficulty/time, flagged gaps, checklist | **$9 per run** |

- You are charged once, only when the remade PDF is delivered.
- If your upload has no usable pictures (or you turn pictures off), the run is Text-only and priced as Text-only. The PDF and the run summary say so.
- Up to **15 pages or photos per run** (PDF pages plus extra photos; pictures inside a PDF page are not counted twice). Over 15, the run stops with a clear message and nothing is charged. Split longer manuals into several runs.
- Refused or failed runs cost nothing.

### Input example

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

### What is in the PDF

- **At a glance:** difficulty (Easy / Moderate / Hard, with the reason), time estimate, people needed, tools
- **Warnings from the original manual**, kept in plain words and never softened
- **Parts list** with tick boxes; quantities the source does not give are shown as "?"
- **Steps** in plain English, one action per line, with parts and tools per step and the source page
- **Missing or unclear in the source** boxes where a step, value or part use is missing (nothing is invented: no made-up torque values, voltages, sizes or safety steps)
- **Your pictures, cleaned** (Standard): straightened, cropped, paper evened out, with red numbered markers matching the step numbers
- **Checklist page** to tick off as you go
- A footer on every page: *rewrite of your uploaded manual, not a certified replacement*

### Other outputs

| Key / view | What it is |
|---|---|
| `OUTPUT.pdf` | The print-friendly remade manual |
| `REMAKE.md` | The same content as Markdown |
| `REWRITE.json` | Structured rewrite (steps, parts, warnings, gaps, figures) |
| `fig-N.png` | Each cleaned picture with its numbered markers (Standard) |
| `SUMMARY` | Edition, counts, pictures used or skipped and why, hidden text removed, one-line `takeaway` |
| Dataset (overview view) | One row per warning, part, step, gap and picture |

### Hidden text in uploads

Some PDFs carry text people cannot see (white, microscopic, invisible or off-page text) or lines aimed at AI tools ("ignore previous instructions..."). Manual Remake removes that text before the rewrite, tells the model to ignore any that slips through, never copies it into the output, and reports how many items were removed in `SUMMARY`.

### Good to know

- **English output only** in this version.
- **No new artwork:** only your own pictures are reused. Phone layout, video scripts and zoomed insets are not in this version.
- **Photos and scans:** pages without a text layer are read from the picture by the model, so use a model that accepts images (gpt-4o-mini does).
- **HEIC photos:** export them as JPEG or PNG first.
- How this differs from step-by-step chat helpers: those walk you through a manual on screen; Manual Remake gives you a finished document to keep, print or share.

## For developers

Python 3.13 Actor (`apify/actor-python`). The pipeline is split so every stage except the model call can be tested offline:

| Module | Job |
|---|---|
| `src/extract.py` | Sniffs PDF vs image, enforces the 15-unit cap, extracts visible text (drops hidden/AI-directed text), pulls embedded pictures and renders scanned pages |
| `src/imaging.py` | Deskew (projection profile), crop to content, clean (paper to white, despeckle, contrast, sharpen), numbered callouts |
| `src/rewrite.py` | Prompt, OpenAI-compatible call on the user's key, and `normalize()` (renumbers steps, re-maps callouts, drops dangling references and AI-directed text) |
| `src/pdfout.py` | reportlab print PDF and Markdown |
| `src/pipeline.py` | Ties it together with an injectable `rewrite_fn` |
| `src/main.py` | Apify input, downloads, pay-per-event charging (`text-remake` / `standard-remake`, once per successful run), outputs |

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt pytest
.venv/bin/python tests/make_fixtures.py      # builds the fictional 3-page sample manual
.venv/bin/python -m pytest -q tests           # no model calls; uses tests/fixtures/rewrite_fixture.json
```

The sample manual in `tests/fixtures` is fictional and was written for this repo, including its drawings and a planted hidden line used to test the hidden-text filter.

Issues and ideas: open an issue on this repo.

Made by [Panda Federation](https://github.com/pandadad0214/panda-federation-tools).
