"""
Runs the full daily content generation pipeline:
  1. Scrapes today's thought + Bible reading (once)
  2. Renders the image using that content
  3. Saves the caption text to a file, so the posting step doesn't need
     to re-scrape or duplicate the caption template logic

Outputs:
  template/output.png   -- the finished image
  template/caption.txt  -- the exact caption text to post
"""

import pathlib
import datetime

from scrape_daily_manna import scrape_daily_manna
from template.render_daily_image import render_image

BASE_DIR = pathlib.Path(__file__).parent
CAPTION_TEMPLATE = (
    '"{thought}."\n\n'
    "There is always manna for every day.\n"
    "Check it out in the Daily Manna.\n\n"
    "#dailymanna\n"
    "#dclmhq\n"
    "#dclmbahrain"
)

if __name__ == "__main__":
    print("Scraping today's content...")
    data = scrape_daily_manna()
    print("Got:", data)

    print("Rendering image...")
    render_image(
        thought=data["thought_for_the_day"],
        bible_reference=data["bible_reading"],
        date=datetime.date.today(),
        output_path=BASE_DIR / "template" / "output.png",
    )

    caption = CAPTION_TEMPLATE.format(thought=data["thought_for_the_day"])
    caption_path = BASE_DIR / "template" / "caption.txt"
    caption_path.write_text(caption, encoding="utf-8")
    print(f"Caption saved to {caption_path}:\n{caption}")
