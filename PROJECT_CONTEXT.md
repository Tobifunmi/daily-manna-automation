# Project Context: Daily Manna Auto Poster

## What this is

A fully automated daily social media pipeline for "Deeper Christian Life
Ministry - Bahrain" (Instagram: @dclmbahrain / Facebook Page: "Deeper
Christian Life Ministry - Bahrain"). Every day at 1:00 PM Bahrain time
(no manual action required), it:

1. Scrapes the day's "Thought for the Day" + Bible reading from
   dailymanna.app
2. Renders it onto a branded graphic (a scroll-and-photo design originally
   built manually in Canva by the user, now fully templated)
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
text → paste into Canva → adjust date → export → schedule on Meta Business
Suite). X/Twitter was deliberately excluded (X's API lost its free tier in
Feb 2026; not worth the ~$0.015/post cost or fragile browser-automation
alternative for this use case).

## Tech stack & architecture

- **Orchestration**: GitHub Actions, scheduled cron (`0 10 * * *` = 10:00
  UTC = 1:00 PM Bahrain, no DST in Bahrain) plus manual `workflow_dispatch`
  trigger for testing.
- **Scraping**: Python + Playwright (headless Chromium) — dailymanna.app
  is JS-rendered client-side, so a plain HTTP request returns nothing
  useful; must render the page in a real browser first.
- **Image generation**: an HTML/CSS/JS template rendered via Playwright
  and screenshotted to PNG (736×736). NOT Canva's API — Canva's Autofill
  API requires an Enterprise plan the user doesn't have, so the design was
  rebuilt as a static background PNG (exported once from the original
  Canva design, with the date/text elements removed) plus dynamically
  positioned/sized text overlaid in HTML/CSS.
- **Posting**: direct Meta Graph API calls (`requests` library in Python)
  — not Meta Business Suite, not any third-party scheduler.
- **Image hosting for Instagram**: Instagram's API requires a public image
  URL (can't accept a raw file upload the way Facebook's photo endpoint
  can). Solution: the generated image is committed back into the same
  public GitHub repo, then served via **jsDelivr** (`cdn.jsdelivr.net/gh/
  <user>/<repo>@<commit-sha>/template/output.png`) — pinned to that day's
  exact commit SHA (not `@main`) so there's no risk of a stale cached
  image. (raw.githubusercontent.com was tried first and proved unreliable
  against Instagram's fetcher specifically — real production error:
  "Media download has failed... doesn't meet our requirements".)
- **Failure alerting**: on any pipeline failure, sends an email (via
  direct Gmail SMTP in Python, `smtplib`) containing which exact stage
  failed and the real error message/traceback — not just a generic
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
                                      (Regular) -- user explicitly chose
                                      this over 500/600 after a side-by-
                                      side comparison; NOT bold (700),
                                      which was the initial wrong guess
    Gistesy.ttf                      Script font for Bible reference +
                                      date. Had a serious bug -- see "Font
                                      bugs found and fixed" below
    OpenSauceSans-Black.ttf          Date badge text (small, white, bold,
                                      sits on the wax-seal graphic)
.github/workflows/
  daily_post.yml               Cron schedule + job steps: checkout, setup
                                Python, install Playwright+deps, run
                                run_daily_pipeline.py with secrets injected
                                as env vars
.gitignore                     Excludes __pycache__/*.pyc
```

## Credentials / secrets (names only -- values are NOT in this document)

Stored as GitHub Actions repo secrets (Settings → Secrets and variables →
Actions):
- `PAGE_ACCESS_TOKEN` — permanent Meta Page access token (generated via
  Graph API Explorer: short-lived user token → long-lived user token
  exchange → Page token exchange; doesn't expire under normal conditions)
- `GMAIL_ADDRESS` — sends failure alerts to itself
- `GMAIL_APP_PASSWORD` — Gmail App Password (not the real account
  password), requires 2-Step Verification enabled on the Google account

Known IDs (not secret, safe to reference directly):
- Facebook Page ID: `1169129646275057`
- Instagram Business Account ID: `17841416232075414`
- Meta Developer app name: "DCLM Bahrain Auto Poster"
- GitHub repo: `Tobifunmi/daily-manna-automation` (public)

## Layout logic (template.html) -- exact current values

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
- Bible reference: stacked directly beneath the thought text (`margin-top:
  18px`), NOT in a separately fixed-position box — this was a deliberate
  fix so short text sits tight under the logo instead of floating
  centered in empty space. Also auto-shrinks independently by width (own
  loop, checking `scrollWidth > 250` down to a 14px floor) so a long
  reference can never get clipped.
- Date badge: `#date-box` at `left:96px; top:509px; width:54px;
  height:50px`, `#date-text` at `font-size:12px`. These exact pixel
  values were arrived at through several rounds of user feedback
  (initially too big/touching the seal edges, then shifted down/left to
  clear the seal's inner dashed border ring). Date format is two lines:
  `"M/D/"` (note: trailing slash IS part of the dynamically injected
  text, added at the user's explicit request to read as "M/D/YYYY" split
  across two lines) and `"YYYY"`.
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
   now. This confirmed-broken/fixed version was delivered to the user.
2. **A separate letter-rendering bug** (word "Genesis" rendering
   scrambled as "enezig" in a live post) was found afterward. The user
   said they fixed this one themselves before a full diagnosis was
   completed in this conversation — so the exact root cause of the letter
   issue (as opposed to the digit issue) was NOT conclusively identified
   here, only reported and handed off. If it resurfaces, start by
   checking whether the user's own fix is still in place in
   `template/fonts/Gistesy.ttf`.

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

## Timing / scheduling notes

- Cron is `0 10 * * *`, correctly corresponding to 1:00 PM Bahrain
  (UTC+3, no DST) — confirmed correct multiple times, this has NOT been
  the actual bug on the occasions posting time looked inconsistent.
- Apparent large time deviations in the daily planner (e.g. posts showing
  at 11:20 AM or 8:56 PM instead of 1:00 PM) were traced to manual
  `workflow_dispatch` test runs during development overlapping with the
  real scheduled runs in the same calendar view — not a scheduler bug.
- GitHub Actions scheduled workflows are NOT guaranteed to fire at the
  exact second; minor delays (low single-digit minutes) are normal and
  not a bug to chase.
- **OPEN/UNRESOLVED at time of writing**: user reported the workflow had
  not fired by 5:00 PM on a day it should have run at 1:00 PM. Diagnosis
  was started (asked user to check the Actions tab for: no runs at all /
  a stuck run / a failed run) but the user redirected to other tasks
  before an answer was given. **This should be revisited** — possible
  causes not yet ruled out: workflow accidentally disabled in repo
  settings, a YAML syntax issue despite "looking okay", GitHub's 60-day
  inactivity auto-disable (unlikely given active commit history, but
  worth checking), or repo visibility/Actions permission changes from
  earlier in the project (the repo was toggled private→public partway
  through this project for Instagram's fetcher to work).

## Design decisions made along the way (so they aren't re-litigated)

- Repo is deliberately **public** — required for Instagram's fetcher;
  nothing sensitive is stored in it (token is never committed as a file).
- Scheduling posts natively via Facebook's `scheduled_publish_time` was
  deliberately rejected in favor of just running the whole pipeline at
  the real target time (1PM) — fewer moving parts, one thing to debug
  instead of two.
- X/Twitter is deliberately excluded (see "What this is" above).
- Failure alerts deliberately go via **email (Gmail SMTP)**, not a push
  notification app (ntfy.sh was proposed and explicitly rejected by the
  user because it required installing a new phone app).
- The `__pycache__` folders got accidentally committed once; a
  `.gitignore` was added afterward to stop it recurring — if you see
  compiled `.pyc` files tracked in the repo again, that's a regression.

## How the user works (useful context for future help)

- Uses Windows + VS Code + PowerShell terminal + Git. Needed detailed,
  literal, copy-paste-exact command guidance throughout (not
  comfortable assuming CLI familiarity) -- explain *where* to run a
  command (which terminal/app) as well as *what* to run, don't assume
  environment variables persist across terminal restarts, etc.
- Prefers being shown a visual preview/comparison before a change is
  applied to the live template, especially for anything involving exact
  positioning or sizing (established pattern: render a preview, get
  explicit approval, then apply to the real file).
- Wants failures to be genuinely informative (the whole point of the
  email-alert feature) — not just "it broke," but which stage and why.
