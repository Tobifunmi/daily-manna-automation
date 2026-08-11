"""
Renders today's Daily Manna graphic by filling template.html with the
scraped thought/Bible reading and today's date, then screenshotting it
to a PNG at the exact 736x736 canvas size.

Install:
    pip install playwright
    playwright install chromium --with-deps

Run:
    python render_daily_image.py
(pulls today's content automatically via scrape_daily_manna.py)

Or import render_image(thought, bible_reference, date) directly to
supply your own text.
"""

import datetime
import pathlib
from playwright.sync_api import sync_playwright

TEMPLATE_DIR = pathlib.Path(__file__).parent
TEMPLATE_PATH = TEMPLATE_DIR / "template.html"
OUTPUT_PATH = TEMPLATE_DIR / "output.png"


def render_image(thought: str, bible_reference: str, date: datetime.date, output_path=OUTPUT_PATH):
    html = TEMPLATE_PATH.read_text(encoding="utf-8")

    date_line_1 = f"{date.month}/{date.day}/"  # e.g. "8/10" — works on every OS
    date_line_2 = str(date.year)              # e.g. "2026"

    html = (
        html.replace("{{THOUGHT}}", thought)
        .replace("{{BIBLE_REFERENCE}}", bible_reference)
        .replace("{{DATE_LINE_1}}", date_line_1)
        .replace("{{DATE_LINE_2}}", date_line_2)
    )

    filled_path = TEMPLATE_DIR / "_filled.html"
    filled_path.write_text(html, encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 736, "height": 736})
        page.on("console", lambda msg: print(f"[browser console] {msg.text}"))
        page.on("pageerror", lambda exc: print(f"[browser error] {exc}"))
        page.goto(filled_path.as_uri())
        # Wait for the auto-fit script (runs once fonts are ready) to finish
        page.wait_for_function("window.__fitDone === true", timeout=10000)

        loaded_fonts = page.evaluate(
            "() => [...document.fonts].map(f => `${f.family} (${f.status})`)"
        )
        print("Fonts loaded in page:", loaded_fonts)

        page.screenshot(path=str(output_path))
        browser.close()

    filled_path.unlink(missing_ok=True)
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(TEMPLATE_DIR.parent))
    from scrape_daily_manna import scrape_daily_manna

    data = scrape_daily_manna()
    render_image(
        thought=data["thought_for_the_day"],
        bible_reference=data["bible_reading"],
        date=datetime.date.today(),
    )
