# Japan Visa Appointment Checker — Vancouver

Polls [cgjvancouver.rsvsys.jp](https://cgjvancouver.rsvsys.jp/reservations/calendar) for the **Visa application** category, walks the week view 6 weeks forward, and emails you when any time slot has remaining capacity > 0.

Two alert channels (both by email):

1. **Main alert** — fires whenever the full open-slot list changes (silent when unchanged so you don't get spammed every 15 min).
2. **Earlier-than alert** — fires only when an open slot appears strictly before `EARLIER_THAN` (edit in `check_visa.py`). Useful for "reschedule to an earlier date" watching.

Runs every 15 minutes on **GitHub Actions** (free for public repos). Can also be run locally.

## Files

| File | Purpose |
|---|---|
| `check_visa.py` | Main checker |
| `requirements.txt` | `playwright` |
| `.github/workflows/check.yml` | 15-minute scheduled GitHub Actions workflow |

Runtime state (`last_state.json`, `earlier_state.json`, `last.html`) is git-ignored and regenerated each run.

## Configure the "earlier than" cutoff

The "earlier-than" alert fires when any open slot appears strictly before this date. Two ways to configure it (the variable takes precedence):

- **Recommended — GitHub repo variable (no commit required):**
  Go to **Settings → Secrets and variables → Actions → Variables → New repository variable**, name it `EARLIER_THAN`, value in `YYYY-MM-DD` form (e.g. `2026-06-08`). Or via CLI:
  ```bash
  gh variable set EARLIER_THAN --body "2026-06-08"
  ```
  The next scheduled run picks up the new value.

- **Fallback — default in the workflow file:**
  If the variable is unset, `check.yml` falls back to a hard-coded default (currently `2026-06-08`). Edit that default in `.github/workflows/check.yml` and commit.

For local runs, set the `EARLIER_THAN` environment variable before invoking `check_visa.py`; if unset, the script uses the same default.

## GitHub Actions setup

1. **Fork or clone this repo** into your own GitHub account (public repo, for free unlimited Actions minutes).
2. Set up a Gmail **App Password**:
   - Enable 2-Step Verification on your Google account.
   - Create an app password at <https://myaccount.google.com/apppasswords> (16-char string).
3. In your repo, go to **Settings → Secrets and variables → Actions → New repository secret**, and add:
   - `GMAIL_USER` — the Gmail address you're sending from
   - `GMAIL_APP_PASSWORD` — the 16-char app password
   - `NOTIFY_TO` — where alerts should be delivered (can be the same address)
4. Push any commit, or open the **Actions** tab and use **Run workflow** on the `check` workflow to trigger manually.

### Notes on GitHub scheduling

- Cron is best-effort; runs may be delayed 5–15 minutes during high load. Fine for a 15-min poll.
- Scheduled workflows on a repo with no recent activity get paused after 60 days. Any push resets this.
- Scheduled workflows run only on the default branch.

## Local run (optional)

```bash
python -m venv .venv
# Windows:  .\.venv\Scripts\Activate.ps1
# Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium

# Set the three env vars for notifications:
export GMAIL_USER="you@gmail.com"
export GMAIL_APP_PASSWORD="xxxxxxxxxxxxxxxx"
export NOTIFY_TO="you@gmail.com"

python check_visa.py
```

## How detection works

1. Navigates to the calendar, selects category "Visa application" (`event=2`).
2. In the week view, scans each `<td>` in `table.c_cal_time`:
   - Skips cells with class `c_cal_time_cell--disabled`.
   - Reads the "残N人" (remaining-N) number; keeps only N > 0.
3. Advances one week via the "次の週" button (`a.next02`) up to 6 times.
4. Diffs against previous run's state; emails on the main list if changed.
5. Filters for dates strictly before `EARLIER_THAN`; diffs separately; emails if changed.

If the site layout changes, the last scraped page is uploaded as an Actions artifact (on failure) named `last-html-*`; download it and update selectors in `scan_week()`.
