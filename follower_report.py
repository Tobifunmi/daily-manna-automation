"""Daily follower-count report for DCLM Bahrain.

Pulls follower counts from Facebook, Instagram, YouTube (and X if possible),
formats the WhatsApp-ready message, and sends it to you by email (Gmail SMTP)
and on WhatsApp (via CallMeBot, skipped until CALLMEBOT_APIKEY is set) so you
can forward it to the group with one tap.

All secrets come from environment variables (GitHub Actions secrets).
"""
import os
import smtplib
import sys
from datetime import datetime
from email.message import EmailMessage
from zoneinfo import ZoneInfo

import requests

GRAPH = "https://graph.facebook.com/v21.0"
TIMEOUT = 20


def env(name, default=None):
    return os.environ.get(name, default)


def facebook_followers():
    r = requests.get(
        f"{GRAPH}/{env('FB_PAGE_ID')}",
        params={"fields": "followers_count", "access_token": env("FB_PAGE_TOKEN")},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["followers_count"]


def instagram_followers():
    r = requests.get(
        f"{GRAPH}/{env('IG_USER_ID')}",
        params={"fields": "followers_count", "access_token": env("FB_PAGE_TOKEN")},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["followers_count"]


def youtube_subscribers():
    r = requests.get(
        "https://www.googleapis.com/youtube/v3/channels",
        params={
            "part": "statistics",
            "id": env("YT_CHANNEL_ID"),
            "key": env("YT_API_KEY"),
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return int(r.json()["items"][0]["statistics"]["subscriberCount"])


def twitter_followers():
    # The X API free tier may not allow this. Fall back to a manually set value.
    token, user = env("X_BEARER_TOKEN"), env("X_USERNAME")
    if token and user:
        r = requests.get(
            f"https://api.twitter.com/2/users/by/username/{user}",
            params={"user.fields": "public_metrics"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json()["data"]["public_metrics"]["followers_count"]
    return int(env("X_FOLLOWERS_MANUAL", "1"))


def safe(fn):
    try:
        return fn()
    except Exception as exc:  # keep the report going if one platform fails
        print(f"{fn.__name__} failed: {exc}")
        return "n/a"


def build_message():
    now = datetime.now(ZoneInfo(env("TIMEZONE", "Asia/Bahrain")))
    if env("DATE_ORDER", "MDY") == "MDY":
        date = f"{now.month}/{now.day}/{now.year}"
    else:
        date = f"{now.day}/{now.month}/{now.year}"

    label = env("REPORT_LABEL", "DCLM Followers")
    return (
        f"{date} - {label}\n"
        f"Facebook: {safe(facebook_followers)}\n"
        f"Instagram: {safe(instagram_followers)}\n"
        f"Twitter: {safe(twitter_followers)}\n"
        f"YouTube: {safe(youtube_subscribers)}"
    )


def send_whatsapp(text):
    r = requests.get(
        "https://api.callmebot.com/whatsapp.php",
        params={
            "phone": env("CALLMEBOT_PHONE"),
            "apikey": env("CALLMEBOT_APIKEY"),
            "text": text,
        },
        timeout=TIMEOUT,
    )
    print("CallMeBot response:", r.status_code, r.text[:200])
    r.raise_for_status()
    if "ERROR" in r.text.upper():
        raise RuntimeError(f"CallMeBot rejected the message: {r.text[:200]}")


def send_email(text, note=""):
    sender = env("GMAIL_ADDRESS")
    msg = EmailMessage()
    msg["Subject"] = text.splitlines()[0] + (" (WhatsApp failed)" if note else "")
    msg["From"] = sender
    msg["To"] = env("EMAIL_TO") or sender
    msg.set_content(text + (f"\n\n{note}" if note else ""))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=TIMEOUT) as smtp:
        smtp.login(sender, env("GMAIL_APP_PASSWORD"))
        smtp.send_message(msg)


if __name__ == "__main__":
    message = build_message()
    print(message)
    errors = []

    note = ""
    if env("CALLMEBOT_APIKEY"):
        try:
            send_whatsapp(message)
        except Exception as exc:
            note = f"WhatsApp send failed: {exc}"
            errors.append(note)
            print(note)
    else:
        print("CALLMEBOT_APIKEY not set - skipping WhatsApp")

    try:
        send_email(message, note)
        print("Email sent")
    except Exception as exc:
        errors.append(f"Email send failed: {exc}")
        print(errors[-1])

    if errors:
        sys.exit(1)
