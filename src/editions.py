"""Navigation copy for the three live Manual Remake editions.

Free sample, Text-only, and Standard. Prices match the live Store listing.
Do not add an edition that is not for sale.
"""

STORE_URL = "https://apify.com/pandadad0214/manual-remake"

STEP_FREE = (
    "To the free sample: leave Manual files and Manual links empty, or tick Free sample, then Start. No key needed."
)
STEP_TEXT = (
    "To Text-only ($9 per successful run): upload your PDF or photos in Manual files (or paste links in Manual links), "
    'paste your LLM API key, turn off "Reuse and clean pictures", then Start.'
)
STEP_STANDARD = (
    "To Standard ($39 per successful run): upload your PDF or photos in Manual files (or paste links in Manual links), "
    'paste your LLM API key, leave "Reuse and clean pictures" on, then Start.'
)
KEY_RULE = (
    "A paid run of your own file always needs your own key. If you upload files without a key, the run stops "
    "and asks for one. It never swaps in the demo."
)


def switch_editions(current: str) -> str:
    """Steps from the edition in hand to each of the other two. `current` is sample, text, or standard."""
    if current == "sample":
        lead = (
            "This file is the free sample: no upload, no LLM key, no charge. It is the bundled fictional "
            "Birchline ST-2 demo, marked FREE SAMPLE, and it is not a remake of your file. "
            "The other editions are Text-only ($9 per successful run) and Standard ($39 per successful run). "
        )
        steps = f"{STEP_TEXT} {STEP_STANDARD} "
    elif current == "text":
        lead = (
            "This file is the Text-only edition ($9 per successful run): a paid remake of your own manual with "
            "pictures off. The other editions are the free sample (no charge) and Standard ($39 per successful run). "
        )
        steps = f"{STEP_FREE} {STEP_STANDARD} "
    elif current == "standard":
        lead = (
            "This file is the Standard edition ($39 per successful run): a paid remake of your own manual with "
            "your pictures cleaned and numbered. The other editions are the free sample (no charge) and "
            "Text-only ($9 per successful run). "
        )
        steps = f"{STEP_FREE} {STEP_TEXT} "
    else:
        raise ValueError(f"unknown edition {current}")
    return f"{lead}{steps}{KEY_RULE} Store: {STORE_URL}"
