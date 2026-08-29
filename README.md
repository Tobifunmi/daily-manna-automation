# Daily Manna Auto Poster

Fully automated pipeline that scrapes the daily "Thought for the Day" and
Bible reading from [dailymanna.app](https://www.dailymanna.app/), renders
it onto a branded graphic, and posts it to Facebook, Instagram, and both
platforms' Stories — every day at 1:00 PM Bahrain time, with no manual
steps.

## How it works

Runs once daily via GitHub Actions (`.github/workflows/daily_post.yml`),
on a schedule of `13 10 * * *` (10:13 UTC ≈ 1:13 PM Bahrain, UTC+3, no
DST). Can also be triggered manually from the **Actions** tab for testing
(`workflow_dispatch`).

**Dual-trigger setup:** GitHub's native `schedule:` cron trigger is
best-effort, not guaranteed-time — it queues jobs for a runner rather than
firing them instantly, and that queue delay got progressively worse (from
~30 minutes up to 10+ hours) around the busy top-of-the-hour slot. Two
fixes are layered on top of each other:
1. The cron was shifted off the top of the hour (`10:13` instead of
   `10:00`) to dodge the busiest queue window.
2. An external scheduler at [cron-job.org](https://cron-job.org) fires a
   `POST` request to GitHub's REST API
   (`.../actions/workflows/daily_post.yml/dispatches`) at exactly 10:00
   UTC daily, using a fine-grained GitHub PAT (Actions: read/write,
   scoped to this repo only) as a `Bearer` token in the `Authorization`
   header, with body `{"ref":"main"}`. This bypasses GitHub's internal
   queuing entirely and acts as the reliable trigger, with the native
   cron as a backup.

**Known tradeoff:** both triggers fire independently every day, so on a
normal day you should expect *two* full pipeline runs ~13 minutes apart
(cron-job.org's dispatch at 10:00 UTC, then the native cron at 10:13
UTC) — meaning the content gets posted to Facebook/Instagram twice daily
unless this is addressed. This was accepted as a stopgap while confirming
the external trigger works reliably; the intended next step is to
**remove the native `schedule:` block from `daily_post.yml`** once
cron-job.org has proven reliable over several days, leaving
`workflow_dispatch` in place for manual testing only.

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
  daily_post.yml              The GitHub Actions schedule + job definition
```

## One-time setup (already done, documented for reference)

- **Meta Developer app** ("DCLM Bahrain Auto Poster") with the Instagram
  and Facebook Login for Business products added, generating a permanent
  Page Access Token (via Graph API Explorer → long-lived token exchange →
  Page token exchange).
- **GitHub repo secrets**: `PAGE_ACCESS_TOKEN`, `GMAIL_ADDRESS`,
  `GMAIL_APP_PASSWORD`.
- **Repo visibility: public.** Required because Instagram's API must be
  able to fetch the image from a public URL; nothing sensitive is stored
  in the repo itself (the token only ever lives as a GitHub Secret / local
  environment variable, never committed as a file).
- **Facebook Page ID**: `1169129646275057`
- **Instagram Business Account ID**: `17841416232075414`

## Why jsDelivr instead of raw.githubusercontent.com

Instagram's media-fetch step was unreliable against
`raw.githubusercontent.com` directly (real error hit in production:
`"Media download has failed... doesn't meet our requirements"`). Switched
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

Fixed by running the font through FontForge's `removeOverlap()` +
`simplify()` + `correctDirection()` on just those two glyphs, then
re-exporting. Verified against every real Bible reference that had
previously failed in production. (Philip subsequently applied his own
additional fix on top of this for a separate letter-rendering issue.)

## Known behaviors / things to know

- **Posting time can drift.** Small (single-digit-minute) delays from
  GitHub Actions' scheduler are normal and not a bug. Large deviations
  (hours late) were traced to GitHub's `schedule:` trigger queuing jobs
  rather than firing them promptly, worse around the top of the hour —
  now mitigated by the dual-trigger setup described above. Separately,
  large *apparent* deviations in a planner/calendar view in the past
  turned out to be manual `workflow_dispatch` test runs overlapping with
  real scheduled runs in the same view, not an actual scheduler bug.
- **Instagram's API is occasionally flaky** at the container-creation and
  publish steps ("media could not be fetched", "Media Not Found" right
  after a container reports finished). Both are handled with automatic
  retries (up to 4 attempts, 10s apart) rather than failing immediately.
- **X/Twitter is intentionally not included** — X's API no longer has a
  free tier as of Feb 2026 (pay-per-post, ~$0.015/post); decision was made
  to skip it rather than pay or use fragile browser automation.
- If a run fails for any reason, check your email first — the failure
  alert names the exact stage and the real error message.

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
