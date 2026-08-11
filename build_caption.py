from scrape_daily_manna import scrape_daily_manna

CAPTION_TEMPLATE = (
    '"{thought}."\n\n'
    "There is always manna for every day.\n"
    "Check it out in the Daily Manna.\n\n"
    "#dailymanna\n"
    "#dclmhq\n"
    "#dclmbahrain"
)


def build_caption() -> str:
    data = scrape_daily_manna()
    return CAPTION_TEMPLATE.format(thought=data["thought_for_the_day"])


if __name__ == "__main__":
    print(build_caption())
