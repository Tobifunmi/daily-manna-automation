# Daily Manna Auto Poster

Fully automated pipeline that scrapes the daily "Thought for the Day" and
Bible reading from [dailymanna.app](https://www.dailymanna.app/), renders
it onto a branded graphic, and posts it to Facebook, Instagram, and both
platforms' Stories — every day at 1:00 PM Bahrain time, with no manual
steps.

This repo also hosts a second, independent automation: the **Daily
Follower Report** (see the section of that name below), which pulls the
page's follower counts and sends them out by email (and WhatsApp, once
activated) every day.

## How it works

Runs once daily via GitHub Actions (`.github/workflows/daily_post.yml`).
The workflow is triggered by an external scheduler at
[cron-job.org](https://cron-job.org), which fires a `POST` request to
GitHub's REST API (`.../actions/workflows/daily_post.yml/dispatches`) at
exactly 10:00 UTC (1:00 PM Bahrain, UTC+3, no DST), using a fine-grained
GitHub PAT (Actions: read/write, scoped to this repo only) as a `Bearer`
token in the `Authorization` header, with body `{"ref":"main"}`. The
workflow can also be triggered manually from the **Actions** tab for
testing (`workflow_dispatch`).

**Why an external trigger:** GitHub's native `schedule:` cron trigger is
best-effort, not guaranteed-time — it queues jobs for a runner rather than
firing them instantly, and that queue delay got progressively worse (from
~30 minutes up to 10+ hours). The native `schedule:` block has since been
removed from `daily_post.yml` entirely; cron-job.org is the sole daily
trigger, and `workflow_dispatch` remains for manual testing.

Pipeline, in order (`run_daily_pipeline.py` orchestrates all of this):

1. **Scrape** — `scrape_daily_manna.py` loads dailymanna.app in a headless
   browser (Playwright; the site is JS-rendered, so a plain HTTP request
   returns nothing) and extracts the day's "Thought for the Day" text and
   Bible reading reference (e.g. "Acts 10: 1-8").
2. **Render** — `template/render_daily_image.py` fills
   `template/template.html` with that text plus today's date, and
   screenshots it to `template/output.png` at 736×736. Font size for the
   main thought auto-shrinks to fit without ever overlapping the Bible
   reference line below it; the Bible reference auto-shrinks independently
   too, so nothing ever gets clipped regardless of length.
3. **Commit** — the generated image + caption are committed and pushed
   back into this repo, so Instagram (which requires a public image URL,
   not a file upload) has something to fetch.
4. **Post** — `post_to_meta.py` posts to:
   - Facebook Page (direct file upload)
   - Instagram feed (via jsDelivr CDN URL pinned to that day's exact
     commit hash — see "Why jsDelivr" below)
   - Facebook Story
   - Instagram Story
5. **Alert on failure** — if any stage throws, `run_daily_pipeline.py`
   emails the failure reason (which stage, the actual error message) via
   Gmail SMTP, and the GitHub Actions run also shows as failed (red ❌).

## Daily Follower Report

A separate workflow that reports the DCLM Bahrain follower counts every
day, replacing a manual task (checking each platform and typing the numbers
into a WhatsApp message for a group).

**Output format** (month/day/year):

```
10/12/2026 - DCLM Followers
Facebook: 1604
Instagram: 23
Twitter: 1
YouTube: 33
```

**How it runs:** `.github/workflows/follower_report.yml` (manual
`workflow_dispatch` only, no native schedule) runs `follower_report.py`.
A second cron-job.org job, "Follower report", fires a `POST` to
`https://api.github.com/repos/Tobifunmi/daily-manna-automation/actions/workflows/follower_report.yml/dispatches`
daily at 12:30 PM WAT (11:30 UTC), using the same fine-grained PAT and
`{"ref":"main"}` body as the posting job (it was created by cloning that
job). A successful dispatch returns HTTP 204.

**Where each number comes from:**

| Platform  | Source |
|-----------|--------|
| Facebook  | Graph API `followers_count` for the Page, using the existing `PAGE_ACCESS_TOKEN` |
| Instagram | Graph API `followers_count` for the Instagram Business Account, same token |
| YouTube   | YouTube Data API v3 `subscriberCount`, using `YT_API_KEY` + `YT_CHANNEL_ID` |
| Twitter/X | **Not fetched** — X's API isn't free. The value is a manual number (default `1`) set by `X_FOLLOWERS_MANUAL` in `follower_report.py`; update it by hand when it changes (or pass `X_FOLLOWERS_MANUAL` as an env var in `follower_report.yml`) |

If one platform's call fails, that line shows `n/a` and the rest of the
report still goes out.

**Delivery:** the script sends the finished message two ways, so the
report can be forwarded to the WhatsApp group with one tap:

- **Email** (always on) — Gmail SMTP using the existing `GMAIL_ADDRESS` and
  `GMAIL_APP_PASSWORD` secrets. Sent to `GMAIL_ADDRESS` unless an optional
  `EMAIL_TO` secret is set. Subject = the report's first line.
- **WhatsApp via [CallMeBot](https://www.callmebot.com/blog/free-api-whatsapp-messages/)**
  (free, personal use) — skipped automatically while `CALLMEBOT_APIKEY` is
  not set. Once set, both channels fire every run. Note the message arrives
  from CallMeBot's number, not your own; it can only message the number that
  activated it. **Status as of Oct 12, 2026:** activation still pending
  (CallMeBot says to retry after 24 hours if no key arrives within
  2 minutes).

**Failure behavior:** CallMeBot returns HTTP 200 even when it rejects a
request, so the script also checks the response text for `ERROR`. If
WhatsApp is configured but fails, the email still goes out with
"(WhatsApp failed)" in the subject and the error in the body, and the run
turns red. If the email send fails, the run turns red too.

**Secrets used by this workflow** (in addition to the existing
`PAGE_ACCESS_TOKEN`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`):
`YT_API_KEY`, `YT_CHANNEL_ID`, `CALLMEBOT_PHONE`, `CALLMEBOT_APIKEY`, and
optionally `EMAIL_TO`. The Facebook Page ID and Instagram Business Account
ID are set directly in the workflow file (they aren't sensitive).
Optional env vars supported by the script: `DATE_ORDER` (`MDY` default,
or `DMY`), `TIMEZONE` (default `Asia/Bahrain`, used for the date),
`REPORT_LABEL` (default `DCLM Followers`).

**Considered and rejected:** Telegram delivery (explicitly not wanted).
ntfy.sh was offered as a free push alternative but not adopted.

## Repo structure

```
scrape_daily_manna.py       Scrapes dailymanna.app (Playwright)
build_caption.py            Standalone caption builder (used by early
                             version; superseded by run_daily_pipeline.py,
                             kept for reference/manual testing)
post_to_meta.py             Facebook/Instagram feed + Story posting,
                             with retries and real error messages
run_daily_pipeline.py       Orchestrates the full daily pipeline with
                             per-stage error handling + email alerts
debug_instagram_post.py     Manual diagnostic script -- shows the full
                             Instagram container/publish response instead
                             of a generic error
follower_report.py          Daily follower report: pulls Facebook /
                             Instagram / YouTube counts (X is manual),
                             formats the message, sends by email and
                             (when activated) WhatsApp via CallMeBot
template/
  template.html              HTML/CSS/JS template -- the image design
  render_daily_image.py      Fills the template + screenshots it via
                              Playwright
  background.png              Static background export from Canva (scroll,
                              photo, logo -- everything except the daily
                              text/date)
  fonts/
    Raleway-VariableFont_wght.ttf   Main thought text (Regular/400 weight)
    Gistesy.ttf                      Bible reference + date script font
                                      (repaired -- see "Font fixes" below)
    OpenSauceSans-Black.ttf          Date badge text
.github/workflows/
  daily_post.yml              The GitHub Actions job definition for the
                              daily post (workflow_dispatch only)
  follower_report.yml         The GitHub Actions job definition for the
                              follower report (workflow_dispatch only)
```

## One-time setup (already done, documented for reference)

- **Meta Developer app** ("DCLM Bahrain Auto Poster") with the Instagram
  and Facebook Login for Business products added, generating a permanent
  Page Access Token (via Graph API Explorer → long-lived token exchange →
  Page token exchange).
- **GitHub repo secrets**: `PAGE_ACCESS_TOKEN`, `GMAIL_ADDRESS`,
  `GMAIL_APP_PASSWORD`, plus the follower-report secrets listed above.
- **Repo visibility: public.** Required because Instagram's API must be
  able to fetch the image from a public URL; nothing sensitive is stored
  in the repo itself (tokens and keys only ever live as GitHub Secrets /
  local environment variables, never committed as a file). Don't hardcode
  phone numbers or API keys in workflow files for the same reason.
- **Facebook Page ID**: `1169129646275057`
- **Instagram Business Account ID**: `17841416232075414`
- **YouTube Data API key**: created in Google Cloud Console (project with
  "YouTube Data API v3" enabled) — AI Studio is not needed.

## Why jsDelivr instead of raw.githubusercontent.com

Instagram's media-fetch step was unreliable against `raw.githubusercontent.com` directly (real error hit in production: `"Media download has failed... doesn't meet our requirements"`). Switched
to jsDelivr (`cdn.jsdelivr.net/gh/...`), a CDN built for exactly this kind
of hotlinking, and pinned the URL to that day's exact git commit SHA
(rather than `@main`) so there's zero risk of Instagram ever fetching a
stale cached image from a previous day.

## Font fixes (Gistesy)

The Gistesy script font (used for the Bible reference + date) had a real,
reproducible bug: the digits **"0" and "2" rendered as literally
invisible** in every context (confirmed via isolated testing with both
Pillow/raqm and basic layout engines — not a shaping/ligature issue, a
genuine broken glyph). Root cause: self-overlapping contour paths in
those two glyphs specifically — a common defect in fonts generated from
handwriting samples.

Fixed by running the font through FontForge's `removeOverlap()` + `simplify()` + `correctDirection()` on just those two glyphs, then
re-exporting. Verified against every real Bible reference that had
previously failed in production. (Philip subsequently applied his own
additional fix on top of this for a separate letter-rendering issue.)

## Known behaviors / things to know

- **Posting time can drift slightly.** Small (single-digit-minute) delays
  from GitHub Actions are normal and not a bug. Large deviations (hours
  late) were traced to GitHub's native `schedule:` trigger queuing jobs —
  now eliminated by using cron-job.org as the only trigger. Separately,
  large *apparent* deviations in a planner/calendar view in the past
  turned out to be manual `workflow_dispatch` test runs overlapping with
  real scheduled runs in the same view, not an actual scheduler bug.
- **Instagram's API is occasionally flaky** at the container-creation and
  publish steps ("media could not be fetched", "Media Not Found" right
  after a container reports finished). Both are handled with automatic
  retries (up to 4 attempts, 10s apart) rather than failing immediately.
- **X/Twitter is intentionally not included in the daily post** — X's API
  no longer has a free tier as of Feb 2026 (pay-per-post, ~$0.015/post);
  decision was made to skip it rather than pay or use fragile browser
  automation. In the follower report, X is a manually maintained number.
- **The cron-job.org GitHub PAT expires.** Both cron-job.org jobs share
  one fine-grained PAT; renew it before it expires or both triggers will
  silently start failing with 401s.
- If a daily-post run fails for any reason, check your email first — the
  failure alert names the exact stage and the real error message. For the
  follower report, a red run in the Actions tab (and, for WhatsApp
  failures, a "(WhatsApp failed)" email subject) is the signal.

## Local testing

Requires Python 3.12+, plus:

```
pip install playwright requests
playwright install chromium --with-deps
```

Run the full pipeline locally:

```
python run_daily_pipeline.py
```

Requires `PAGE_ACCESS_TOKEN`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD` set as
environment variables first (PowerShell: `$env:VAR_NAME="value"`).

**Warning:** running this locally makes real, live posts to Facebook and
Instagram (main feed + Stories on both) — there's no "dry run" mode.

The follower report only needs `requests`
(`python follower_report.py`) and is safe to run locally: it posts
nothing publicly, it only sends you the email (and WhatsApp message, if
configured). Set the env vars listed in the follower-report section first.
