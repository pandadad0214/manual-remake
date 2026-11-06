# Manual Remake: rewrite a confusing manual into a clear, printable PDF

**Upload a PDF or photos of an existing instruction manual and get back a clearer English manual you can keep or print.** Manual Remake by Panda Federation rewrites the steps in plain English, cleans up the parts list, pulls every warning into one place, estimates difficulty and time, flags missing or unclear steps instead of guessing, adds a checklist, and (Standard edition) straightens, crops and cleans **your own pictures** and adds red numbered markers that match the rewritten steps.

This is a rewrite of the file you upload. It is not an official or certified replacement for the manufacturer's manual and makes no safety, standards or compliance claim.

## Use it on Apify

Manual Remake runs as an Apify Actor at [apify.com/pandadad0214/manual-remake](https://apify.com/pandadad0214/manual-remake). There is nothing to install.

### Free sample (no upload, no key, no charge)

Click **Start** with no files (or tick **Free sample**) and you get a real remade PDF of a short, fictional demo manual (the "Birchline ST-2 side table") that ships with the Actor. It shows the full layout: at-a-glance box, warnings, parts list, plain-English steps, flagged gaps, cleaned pictures with numbered markers and the checklist. The sample uses a pre-made rewrite, so no AI model is called, no key is needed and nothing is charged. The PDF and the run summary are clearly marked **FREE SAMPLE**: it is never presented as a remake of your file.

### Remake your own manual (paid)

1. Upload the manual in **Manual files** (PDF or photos of the pages), or paste direct public or share links in **Manual links**.
2. Paste your **LLM API key** (OpenAI, or any OpenAI-compatible provider with an https **LLM base URL**). Your own manual is always rewritten with your own key, so model usage is billed by your provider. The key is stored encrypted and never logged. If you upload files without a key, the run stops and asks for one; it never swaps in the demo.
3. Leave **Reuse and clean pictures** on for the Standard edition, or turn it off for a Text-only edition.
4. Click **Start**, then download **OUTPUT.pdf** from the run's **Output** tab (or **Storage → Key-value store**).

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
| `SUMMARY` | Edition (`sample`, `text` or `standard`), `sample` flag, counts, pictures used or skipped and why, hidden text removed, what was charged, one-line `takeaway` |
| Dataset (overview view) | An overview row, then one row per warning, part, step, gap and picture, each with a one-line `summary` |

### Hidden text in uploads

Some PDFs carry text people cannot see (white, microscopic, invisible or off-page text) or lines aimed at AI tools ("ignore previous instructions..."). Manual Remake removes that text before the rewrite (white text on a coloured warning banner and the invisible text layer of scanned PDFs are kept, because those are real content), tells the model to ignore any that slips through, never copies it into the output, and reports how many items were removed in `SUMMARY`.

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
| `src/main.py` | Apify input, free sample mode, downloads, max-charge check before the model call, pay-per-event charging (`text-remake` / `standard-remake`, once per successful run, only after `OUTPUT.pdf` is saved), outputs |

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt pytest
.venv/bin/python tests/make_fixtures.py      # builds the fictional 3-page sample manual
.venv/bin/python -m pytest -q tests           # no model calls; uses tests/fixtures/rewrite_fixture.json
```

The free sample is bundled in `src/sample/` (the fictional manual and its pre-made rewrite); `tests/fixtures` holds the same manual plus a test-only rewrite. The sample manual is fictional and was written for this repo, including its drawings and a planted hidden line used to test the hidden-text filter.

Issues and ideas: open an issue on this repo.

Made by [Panda Federation](https://github.com/pandadad0214/panda-federation-tools).
