"""
Full daily pipeline, run as one script so failures can be caught stage by
stage and reported with the actual reason (not just "it failed").

On any failure, sends an email via Gmail SMTP with the exact stage and
error message in the body, then exits with a non-zero code so the GitHub
Actions run also shows as failed.

Requires these environment variables (set as GitHub Secrets):
    PAGE_ACCESS_TOKEN    -- Meta Page access token
    GMAIL_ADDRESS        -- your Gmail address (sends the alert to itself)
    GMAIL_APP_PASSWORD   -- a Gmail "App Password" (not your normal password)
"""

import datetime
import os
import smtplib
import subprocess
import sys
import traceback
from email.mime.text import MIMEText

from scrape_daily_manna import scrape_daily_manna
from template.render_daily_image import render_image
from post_to_meta import post_to_facebook, post_to_instagram

REPO_RAW_BASE = "https://raw.githubusercontent.com/Tobifunmi/daily-manna-automation/main"
CAPTION_TEMPLATE = (
    '"{thought}."\n\n'
    "There is always manna for every day.\n"
    "Check it out in the Daily Manna.\n\n"
    "#dailymanna\n"
    "#dclmhq\n"
    "#dclmbahrain"
)


def notify_failure(stage: str, error: Exception):
    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not gmail_address or not gmail_app_password:
        print("Gmail credentials not set — skipping email notification.")
        return

    body = (
        f"The Daily Manna auto-post pipeline failed today.\n\n"
        f"Stage: {stage}\n"
        f"Error: {type(error).__name__}: {error}\n"
    )
    msg = MIMEText(body)
    msg["Subject"] = f"Daily Manna post FAILED — {stage}"
    msg["From"] = gmail_address
    msg["To"] = gmail_address

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_address, gmail_app_password)
            server.sendmail(gmail_address, [gmail_address], msg.as_string())
        print("Failure notification email sent.")
    except Exception as notify_err:
        # Don't let a notification failure hide the original error
        print(f"(Also failed to send notification email: {notify_err})")


def run_stage(stage_name, fn, *args, **kwargs):
    print(f"=== {stage_name} ===")
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        print(f"FAILED at stage: {stage_name}")
        traceback.print_exc()
        notify_failure(stage_name, e)
        sys.exit(1)


def git_commit_and_push() -> str:
    """Commits + pushes today's image, and returns the resulting commit SHA."""
    subprocess.run(["git", "config", "user.name", "daily-manna-bot"], check=True)
    subprocess.run(["git", "config", "user.email", "actions@github.com"], check=True)
    subprocess.run(["git", "add", "template/output.png", "template/caption.txt"], check=True)
    result = subprocess.run(["git", "commit", "-m", "Daily Manna image"])
    if result.returncode == 0:
        subprocess.run(["git", "push"], check=True)
    else:
        print("Nothing new to commit (image unchanged) — continuing anyway.")

    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    return sha


def main():
    data = run_stage("Scraping dailymanna.app", scrape_daily_manna)

    run_stage(
        "Rendering image",
        render_image,
        thought=data["thought_for_the_day"],
        bible_reference=data["bible_reading"],
        date=datetime.date.today(),
    )

    caption = CAPTION_TEMPLATE.format(thought=data["thought_for_the_day"])
    with open("template/caption.txt", "w", encoding="utf-8") as f:
        f.write(caption)

    commit_sha = run_stage("Committing + pushing image to GitHub", git_commit_and_push)

    import time
    print("Waiting for jsDelivr's CDN to pick up the new commit...")
    time.sleep(15)

    token = os.environ["PAGE_ACCESS_TOKEN"]

    run_stage(
        "Posting to Facebook",
        post_to_facebook,
        "template/output.png",
        caption,
        token,
    )

    jsdelivr_url = f"https://cdn.jsdelivr.net/gh/Tobifunmi/daily-manna-automation@{commit_sha}/template/output.png"

    run_stage(
        "Posting to Instagram",
        post_to_instagram,
        jsdelivr_url,
        caption,
        token,
    )

    print("All stages completed successfully.")


if __name__ == "__main__":
    main()
