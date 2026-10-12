# Master Context: Daily Manna Auto Poster (+ Daily Follower Report)

Paste this entire document into a new conversation to bring Claude fully
up to speed on this project before asking a new question.

---

## What this is

This repo runs **two independent automations** for "Deeper Christian Life
Ministry - Bahrain" (Instagram: @dclmbahrain / Facebook Page: "Deeper
Christian Life Ministry - Bahrain"):

1. **Daily Manna Auto Poster** — a fully automated daily social media
   pipeline.
2. **Daily Follower Report** — a daily report of the page's follower counts
   (added Oct 12, 2026; see its own section below).

### 1. Daily Manna Auto Poster

Every day at ~1:00 PM Bahrain time (see "Scheduling" below), with no manual
action required, it:

1. Scrapes the day's "Thought for the Day" + Bible reading from
   dailymanna.app
2. Renders it onto a branded graphic (a scroll-and-photo design originally
   built manually in Canva, now fully templated)
3. Posts the graphic to Facebook (feed + Story) and Instagram (feed +
   Story), with the caption format:

```
"[thought for the day]."

There is always manna for every day.
Check it out in the Daily Manna.

#dailymanna
#dclmhq
#dclmbahrain
```

This replaced a fully manual daily process (visit dailymanna.app → copy
text → paste into Canva → adjust date → export → schedule on Meta
Business Suite). X/Twitter was deliberately excluded from the daily post
(X's API lost its free tier in Feb 2026; not worth the ~$0.015/post cost or
fragile browser-automation alternative for this use case).

## Tech stack & architecture

- **Orchestration**: GitHub Actions, triggered externally by cron-job.org
  — see "Scheduling" below. Plus manual `workflow_dispatch` trigger for
  testing.
- **Scraping**: Python + Playwright (headless Chromium) — dailymanna.app
  is JS-rendered client-side, so a plain HTTP request returns nothing
  useful; must render the page in a real browser first.
- **Image generation**: an HTML/CSS/JS template rendered via Playwright
  and screenshotted to PNG (736×736). NOT Canva's API — Canva's Autofill
  API requires an Enterprise plan not available here, so the design was
  rebuilt as a static background PNG (exported once from the original
  Canva design, with the date/text elements removed) plus dynamically
  positioned/sized text overlaid in HTML/CSS.
- **Posting**: direct Meta Graph API calls (`requests` library in Python)
  — not Meta Business Suite, not any third-party scheduler.
- **Image hosting for Instagram**: Instagram's API requires a public
  image URL (can't accept a raw file upload the way Facebook's photo
  endpoint can). Solution: the generated image is committed back into
  the same public GitHub repo, then served via **jsDelivr**
  (`cdn.jsdelivr.net/gh/<user>/<repo>@<commit-sha>/template/output.png`)
  — pinned to that day's exact commit SHA (not `@main`) so there's no
  risk of a stale cached image. (raw.githubusercontent.com was tried
  first and proved unreliable against Instagram's fetcher specifically —
  real production error: "Media download has failed... doesn't meet our
  requirements".)
- **Failure alerting (daily post)**: on any pipeline failure, sends an
  email (via direct Gmail SMTP in Python, `smtplib`) containing which exact
  stage failed and the real error message/traceback — not just a generic
  "workflow failed" notification. GitHub Actions' own run also shows red
  ❌ on failure regardless.

## Repo structure

```
scrape_daily_manna.py       Scrapes dailymanna.app (Playwright); has a
                             --debug mode that dumps the full visible page
                             text, used historically to fix selector bugs
build_caption.py            Standalone/early caption builder (superseded
                             by run_daily_pipeline.py's inline version,
                             kept for manual testing)
post_to_meta.py             All Meta Graph API posting logic: Facebook
                             feed, Instagram feed, Facebook Story,
                             Instagram Story. Every function retries
                             transient failures (up to 4 attempts, 10s
                             apart) and raises the REAL error message from
                             Meta's response body, not a generic
                             "400 Bad Request"
run_daily_pipeline.py       The actual orchestrator run by the GitHub
                             Action. Wraps every stage (scrape, render,
                             git commit+push, Facebook post, Instagram
                             post, Facebook Story, Instagram Story) in a
                             run_stage() helper that catches exceptions,
                             prints full tracebacks, and emails a failure
                             notification naming the stage + real error
debug_instagram_post.py     Manual diagnostic script -- prints the full
                             JSON response at every step of the Instagram
                             container-create -> status-check -> publish
                             flow, for when something fails mysteriously
follower_report.py          Daily follower report (see its section):
                             Facebook / Instagram / YouTube counts + manual
                             X count, formatted and sent by email and
                             (when activated) WhatsApp via CallMeBot
template/
  template.html              The actual image design: background image +
                              absolutely-positioned text overlays, with a
                              JS auto-shrink-to-fit routine (see "Layout
                              logic" below)
  render_daily_image.py      Fills the HTML template's placeholders,
                              launches Playwright, screenshots to PNG
  background.png              Static export from the original Canva
                              design with all daily-changing elements
                              (thought text, Bible ref, date) removed,
                              everything else (scroll, photo, logo, social
                              handles, "THOUGHT FOR THE DAY" label) intact
  fonts/
    Raleway-VariableFont_wght.ttf   Main thought text. Weight 400
                                      (Regular) -- explicitly chosen over
                                      500/600 after a side-by-side
                                      comparison; NOT bold (700), which
                                      was the initial wrong guess
    Gistesy.ttf                      Script font for Bible reference +
                                      date. Had a serious bug -- see "Font
                                      bugs found and fixed" below
    OpenSauceSans-Black.ttf          Date badge text (small, white, bold,
                                      sits on the wax-seal graphic)
.github/workflows/
  daily_post.yml               Job definition for the daily post:
                                checkout, setup Python, install
                                Playwright+deps, run run_daily_pipeline.py
                                with secrets injected as env vars.
                                workflow_dispatch only (native schedule
                                removed Aug 30, 2026)
  follower_report.yml          Job definition for the follower report:
                                checkout, setup Python 3.12, pip install
                                requests, run follower_report.py with
                                secrets/IDs as env vars. workflow_dispatch
                                only
.gitignore                     Excludes __pycache__/*.pyc
```

## Credentials / secrets (names only — values are NOT in this document)

Stored as GitHub Actions repo secrets (Settings → Secrets and variables →
Actions):

- `PAGE_ACCESS_TOKEN` — permanent Meta Page access token (generated via
  Graph API Explorer: short-lived user token → long-lived user token
  exchange → Page token exchange; doesn't expire under normal conditions;
  generated with Instagram permissions). Used by both the daily post and
  the follower report.
- `GMAIL_ADDRESS` — sends failure alerts (daily post) and the follower
  report email, to itself by default
- `GMAIL_APP_PASSWORD` — Gmail App Password (not the real account
  password), requires 2-Step Verification enabled on the Google account
- `YT_API_KEY`, `YT_CHANNEL_ID` — YouTube Data API v3 key (from Google
  Cloud Console, not AI Studio) and the channel ID (follower report)
- `CALLMEBOT_PHONE`, `CALLMEBOT_APIKEY` — WhatsApp delivery via CallMeBot
  (follower report). `CALLMEBOT_PHONE` is the number in international
  format with `+`; keep it as a secret because the repo is public
- `EMAIL_TO` — optional; overrides the follower-report email recipient
  (defaults to `GMAIL_ADDRESS`)

Also in use (not a GitHub secret — lives in cron-job.org's own header
config, see "Scheduling" below):

- A **fine-grained GitHub personal access token**, scoped to only the
  `daily-manna-automation` repo, with `Actions: Read and write`
  permission — used by cron-job.org to call the GitHub REST API. Both
  cron-job.org jobs share this one token.

Known IDs (not secret, safe to reference directly; the Page and Instagram
IDs are hardcoded in `follower_report.yml`):

- Facebook Page ID: `1169129646275057`
- Instagram Business Account ID: `17841416232075414`
- Meta Developer app name: "DCLM Bahrain Auto Poster"
- GitHub repo: `Tobifunmi/daily-manna-automation` (public)

## Daily Follower Report (added Oct 12, 2026)

**Why it exists:** a manager asked Philip to report the client's social
media follower counts daily to a WhatsApp group, in this format (month/day/
year — confirmed MDY):

```
10/12/2026 - DCLM Followers
Facebook: 1604
Instagram: 23
Twitter: 1
YouTube: 33
```

**How it works:** `follower_report.py` fetches the counts, builds the
message, and sends it to Philip, who forwards it to the group (posting
directly into a WhatsApp group isn't possible with the free/official
options, and unofficial libraries risk a number ban, so the last tap is
manual by design).

- **Facebook** — Graph API `followers_count` for the Page, using
  `PAGE_ACCESS_TOKEN`.
- **Instagram** — Graph API `followers_count` for the Business Account,
  same token.
- **YouTube** — YouTube Data API v3 `subscriberCount` using `YT_API_KEY` +
  `YT_CHANNEL_ID`.
- **Twitter/X** — not fetched (X API isn't free). Hardcoded manual value:
  `X_FOLLOWERS_MANUAL` default `"1"` in `follower_report.py`, which Philip
  updates himself. The workflow does not currently pass
  `X_FOLLOWERS_MANUAL`, so the script default is what's used; change the
  default in the script (or add the env var to `follower_report.yml`).
  `X_BEARER_TOKEN`/`X_USERNAME` are supported by the script but unused.
- If one platform's call fails, its line shows `n/a` and the rest still
  goes out.
- Optional env vars: `DATE_ORDER` (`MDY` default; `DMY` also supported),
  `TIMEZONE` (default `Asia/Bahrain`, used for the date), `REPORT_LABEL`
  (default `DCLM Followers`).

**Delivery (both channels run each time):**

1. **Email** — Gmail SMTP (`smtplib`, port 465) using `GMAIL_ADDRESS` /
   `GMAIL_APP_PASSWORD`. Subject is the report's first line; body is the
   message ready to copy. Confirmed working on Oct 12, 2026.
2. **WhatsApp via CallMeBot** (free, personal-use API; sends from
   CallMeBot's number to the number that activated it, NOT from Philip's
   own number). Skipped automatically while `CALLMEBOT_APIKEY` is unset.
   Activation: save the bot's number from callmebot.com's WhatsApp page
   as a contact and send it "I allow callmebot to send me messages"; it
   replies with an API key. If nothing arrives within 2 minutes, CallMeBot
   says to retry after 24 hours. **Status as of Oct 12, 2026: activation
   still pending** — when the key arrives, add `CALLMEBOT_APIKEY` and
   `CALLMEBOT_PHONE` as secrets and WhatsApp starts firing with no code
   change.

**Failure behavior:** CallMeBot returns HTTP 200 even on rejection (e.g.
`ERROR: apikey can not be empty or it has an invalid format`), so the
script checks the response text for `ERROR` and raises. If WhatsApp is
configured but fails, the email is still sent with "(WhatsApp failed)" in
the subject and the error in the body, and the run exits non-zero (red ❌).
An email failure also turns the run red. Both channels are always
attempted.

**Scheduling:** a second cron-job.org job named "Follower report" (created
by cloning the daily-post job so it reuses the same GitHub PAT header and
`{"ref":"main"}` body) POSTs daily at **12:30 PM WAT (11:30 UTC)** to:

```
https://api.github.com/repos/Tobifunmi/daily-manna-automation/actions/workflows/follower_report.yml/dispatches
```

Tested successfully on Oct 12, 2026 (HTTP 204; Actions run + email
confirmed). Free cron-job.org plan allows the additional job.

**Decisions for the follower report (so they aren't re-litigated):**

- Telegram: explicitly rejected ("don't want to use Telegram at all").
- ntfy.sh: offered again as a possible third channel, not adopted (it was
  also rejected earlier for the daily post because it needs a phone app).
- Delivery "from my own WhatsApp number to myself": not possible from a
  GitHub Action without an always-on unofficial client (ban risk) — hence
  CallMeBot (different sender number) plus email as the dependable backup.
  Paid alternatives mentioned but unevaluated: TextMeBot, Twilio.
- Facebook/Instagram IDs hardcoded in the workflow (not sensitive);
  phone number and API keys always via secrets because the repo is public.
- Added to the existing repo rather than a new one: separate workflow
  file, shared secrets and PAT.

## Layout logic (template.html) — exact current values

- Parchment/text-safe zone was measured directly from background.png
  pixel data (not eyeballed): roughly x=94–414, y=195–460 in the 736×736
  canvas.
- Main thought text: `#content-wrap` positioned `left:130px; top:195px;
  width:250px` (narrower than the full parchment width, to leave visible
  margin on both sides — this was an explicit fix after the first version
  ran text edge-to-edge). Font-size auto-shrinks from 34px down to a 14px
  floor via JS, checking the WHOLE stacked block (thought + Bible
  reference together, not just the thought alone) against a max height of
  265px, so the two can never collide or overflow past the seal, however
  many lines it takes (tested up to 6 lines successfully).
- Bible reference: stacked directly beneath the thought text
  (`margin-top: 18px`), NOT in a separately fixed-position box — this was a
  deliberate fix so short text sits tight under the logo instead of
  floating centered in empty space. Also auto-shrinks independently by
  width (own loop, checking `scrollWidth > 250` down to a 14px floor) so a
  long reference can never get clipped.
- Date badge: `#date-box` at `left:96px; top:509px; width:54px;
  height:50px`, `#date-text` at `font-size:12px`. These exact pixel
  values were arrived at through several rounds of user feedback
  (initially too big/touching the seal edges, then shifted down/left to
  clear the seal's inner dashed border ring). Date format is two lines:
  `"M/D/"` (note: trailing slash IS part of the dynamically injected
  text, added at explicit request to read as "M/D/YYYY" split across two
  lines) and `"YYYY"`.
- All three text elements load real local font files via `@font-face`
  (NOT Google Fonts CDN — an earlier attempt using the CDN link for
  Raleway silently failed to apply in some environments; switched to
  bundling the actual `.ttf` files for reliability). Important: use
  `format('truetype')` in the `@font-face` src, NOT
  `format('truetype-variations')` — the latter was silently rejected by
  some Chromium builds with no visible error, wasting significant
  debugging time before being traced via `document.fonts` status
  reporting + browser console/pageerror forwarding added to
  `render_daily_image.py`.

## Font bugs found and fixed (Gistesy.ttf)

Two separate real bugs were found in the original Gistesy font file, both
affecting actual information accuracy (not just style):

1. **Digits "0" and "2" render as literally invisible**, unconditionally,
   in every context — confirmed via isolated character-by-character
   testing with Pillow, in both RAQM (HarfBuzz shaping, matches real
   browsers) and BASIC (direct FreeType rasterization, no shaping) layout
   engines. This is NOT a shaping/ligature/kerning issue (checked and
   ruled out: no GSUB rules involve digits at all, only an unrelated `s`/
   `t` ligature). It's a genuine corrupted-glyph issue: root cause found
   to be self-overlapping contour paths in the "zero" and "two" glyphs
   specifically (common defect in fonts generated from handwriting
   samples via tools like Calligraphr). Fixed via FontForge:
   `glyph.removeOverlap(); glyph.simplify(); glyph.correctDirection()` on
   just those two glyphs, then re-exported keeping the same filename.
   Verified fix against every real-world failing example encountered
   (`"Acts 10: 1-8"`, `"Matthew 1: 18-25"`, etc.) — all render correctly
   now. This confirmed-broken/fixed version was delivered.
2. **A separate letter-rendering bug** (word "Genesis" rendering
   scrambled as "enezig" in a live post) was found afterward. This was
   fixed independently before a full diagnosis was completed in the
   conversation that found it — so the exact root cause of the letter
   issue (as opposed to the digit issue) was NOT conclusively identified,
   only reported and handed off. If it resurfaces, start by checking
   whether that fix is still in place in `template/fonts/Gistesy.ttf`.

## Known Instagram API flakiness (handled, not a mystery if it recurs)

Instagram's Graph API has shown two distinct transient failure modes in
production, both now handled with retry logic (not fully eliminated,
since they're on Meta's side, but retried automatically):

1. **"Media could not be fetched from this URI"** (error code 9004,
   subcode 2207052) at container-creation time — usually a CDN timing
   issue. Handled with up to 4 retries, 10s apart, at the container
   creation step.
2. **"Media Not Found" / "The media... cannot be found"** (error code 24,
   subcode 2207006) at the media_publish step, occurring even right after
   the container's `status_code` reported `"FINISHED"` — a known Meta
   backend registration-lag quirk. Handled with a 5-second buffer pause
   after "FINISHED" is confirmed, plus up to 4 retries, 10s apart, at the
   publish step itself. This exact fix was applied to
   `post_to_instagram_story`; the equivalent retry pattern already existed
   in the regular feed `post_to_instagram` function.

## Scheduling — full history and current state (as of Oct 12, 2026)

**Original setup:** GitHub Actions native `schedule:` cron, `0 10 * * *`
(10:00 UTC = 1:00 PM Bahrain, UTC+3, no DST) — confirmed correct multiple
times; the cron *expression* itself was never the bug.

**The actual bug, diagnosed Aug 29, 2026:** GitHub's native `schedule:`
trigger is best-effort and queues jobs for a runner rather than firing
them instantly. This queuing delay grew progressively worse day over day
— from ~30 minutes (normal/acceptable) up to over 10 hours late — almost
certainly worse around the busy top-of-the-hour slot (`:00`) when many
GitHub-wide scheduled workflows compete for runners at once. This also
explained an earlier double-post: a manual `workflow_dispatch` test ran
fine, and then the *original* queued 10:00 UTC scheduled run — which had
been sitting queued all day — finally got a runner about an hour later
and fired too, posting the same content twice.

**Fix, implemented in stages:**

1. Aug 29: shifted the native cron off the top of the hour (`13 10 * * *`)
   to dodge the busiest queue window, and added an **external trigger** via
   [cron-job.org](https://cron-job.org) (free tier): a cron job named
   "Daily Manna Automation" that fires a `POST` request at exactly
   **10:00 UTC** daily (timezone explicitly set to UTC in cron-job.org,
   not browser-local) to:

   ```
   https://api.github.com/repos/Tobifunmi/daily-manna-automation/actions/workflows/daily_post.yml/dispatches
   ```

   with headers `Content-Type: application/json` and
   `Authorization: Bearer <fine-grained GitHub PAT, scoped to this repo,
   Actions: Read and write>`, and body `{"ref":"main"}`. This bypasses
   GitHub's internal queuing entirely. A test run confirmed a `204 No
   Content` response (GitHub's correct success response for
   `workflow_dispatch` — no body expected).
2. Aug 30: confirmed the native trigger was still unreliable (it fired
   ~5 hours late, at 14:52 UTC, while cron-job.org fired on time, causing
   a duplicate post that day). **Removed the native `schedule:` block from
   `daily_post.yml` entirely.** cron-job.org is now the sole daily trigger
   for the post; `workflow_dispatch` remains for manual testing only. The
   earlier "duplicate posts from two triggers" tradeoff is resolved.
3. Oct 12: added a second cron-job.org job for the follower report (see
   that section), at 12:30 PM WAT (11:30 UTC), using the same PAT and
   body, triggering `follower_report.yml`. That workflow has no native
   schedule either.

**Other timing notes (still true, not the bug):**

- GitHub Actions workflows are never guaranteed to the exact second;
  minor delays (low single-digit minutes) are normal and not worth
  chasing.
- Apparent large time deviations seen in a planner/calendar view in the
  past were traced to manual `workflow_dispatch` test runs overlapping
  with real scheduled runs in the same calendar view — not a scheduler
  bug.

## Design decisions made along the way (so they aren't re-litigated)

- Repo is deliberately **public** — required for Instagram's fetcher;
  nothing sensitive is stored in it (tokens/keys/phone numbers are never
  committed as files; use secrets).
- Scheduling posts natively via Facebook's `scheduled_publish_time` was
  deliberately rejected in favor of just running the whole pipeline at
  the real target time — fewer moving parts, one thing to debug instead
  of two.
- X/Twitter is deliberately excluded from the daily post (see "What this
  is" above). In the follower report it is a manually maintained number.
- Failure alerts for the daily post deliberately go via **email (Gmail
  SMTP)**, not a push notification app (ntfy.sh was proposed and
  explicitly rejected because it required installing a new phone app).
- The `__pycache__` folders got accidentally committed once; a
  `.gitignore` was added afterward to stop it recurring — if you see
  compiled `.pyc` files tracked in the repo again, that's a regression.
- Chose cron-job.org (free tier) over other external-scheduler options
  for the trigger fix — no evaluation of alternatives was recorded, so if
  it ever becomes a problem (reliability, free-tier limits), that
  comparison hasn't been done yet.
- The follower report lives in this same repo as a separate workflow
  rather than a new repo (see the follower-report decisions above).

## How the user (Philip) works — useful context for future help

- Uses Windows + VS Code + PowerShell terminal + Git. Needs detailed,
  literal, copy-paste-exact command guidance throughout (not assumed
  comfortable with CLI) — explain *where* to run a command (which
  terminal/app) as well as *what* to run, don't assume environment
  variables persist across terminal restarts, etc.
- Prefers being shown a visual preview/comparison before a change is
  applied to the live template, especially for anything involving exact
  positioning or sizing (established pattern: render a preview, get
  explicit approval, then apply to the real file).
- Wants failures to be genuinely informative (the whole point of the
  email-alert feature) — not just "it broke," but which stage and why.
- Prefers to do setup step by step, one stage at a time, confirming each
  works before moving on.
- Works across multiple client projects/pipelines (this is one of
  several) under or adjacent to ZeroToZenith Media — a digital marketing
  and cybersecurity training organization — so scheduling collisions or
  patterns affecting one project may be worth checking against others.

## Outstanding items as of Oct 12, 2026

1. **Finish CallMeBot activation** for the follower report: retry the
   activation WhatsApp message after the 24-hour wait, then add
   `CALLMEBOT_APIKEY` and `CALLMEBOT_PHONE` as repo secrets and re-run the
   `follower-report` workflow to confirm the WhatsApp message arrives
   alongside the email.
2. **Confirm the first scheduled follower-report run** lands at the
   configured 12:30 PM WAT time and that the email arrives.
3. **Keep the X/Twitter follower number current** — update
   `X_FOLLOWERS_MANUAL` (default in `follower_report.py`) by hand when it
   changes from `1`.
4. **Fine-grained GitHub PAT expiration** — set during creation (a
   typical choice is 90 days); needs manual renewal before it expires or
   both cron-job.org triggers (daily post and follower report) will
   silently start failing with 401s. Not currently on any
   calendar/reminder.
