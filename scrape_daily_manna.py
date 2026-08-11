"""
Scrapes today's "Thought for the Day" and Bible reading from dailymanna.app.

The site renders its content client-side with JavaScript, so a plain HTTP
request returns an empty shell — this uses Playwright to load the page in a
real (headless) browser first, then reads the rendered text.

Install:
    pip install playwright
    playwright install chromium --with-deps

Run:
    python scrape_daily_manna.py
"""

import json
import re
from playwright.sync_api import sync_playwright

URL = "https://www.dailymanna.app/"


def scrape_daily_manna() -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(URL, wait_until="networkidle")
        text = page.inner_text("body")
        browser.close()

    # "Bible Reading:" is followed on the next line by the reference, e.g. "Acts 10: 1-8"
    bible_match = re.search(r"Bible Reading:\s*\n\s*(.+)", text)
    bible_reading = bible_match.group(1).strip() if bible_match else ""

    # The thought sits between the "THOUGHT FOR THE DAY" heading and the
    # "BIBLE IN ONE YEAR" section that follows it.
    thought_match = re.search(
        r"THOUGHT FOR THE DAY\s*\n+\s*(.+?)\s*\n+\s*BIBLE IN ONE YEAR",
        text,
        re.DOTALL,
    )
    if not thought_match:
        raise RuntimeError(
            "Could not find the 'Thought for the Day' text — "
            "the site's markup may have changed; inspect the page and "
            "update the pattern."
        )
    thought = thought_match.group(1).strip()

    return {
        "thought_for_the_day": thought,
        "bible_reading": bible_reading,
    }


def debug_dump():
    """Prints the full visible text of the page, so we can see exactly
    what's there instead of guessing at the DOM structure."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(URL, wait_until="networkidle")
        text = page.inner_text("body")
        browser.close()

        print("=== Full visible page text ===")
        print(text)


if __name__ == "__main__":
    import sys

    if "--debug" in sys.argv:
        debug_dump()
    else:
        data = scrape_daily_manna()
        print(json.dumps(data, indent=2, ensure_ascii=False))
