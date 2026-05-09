"""Japan Consulate Vancouver visa appointment checker.
Scans the week view for real open time slots (remaining capacity > 0) across
the next ~6 weeks for "Visa application", and notifies on new availability.
"""
import os, sys, json, smtplib, datetime
from email.message import EmailMessage
from playwright.sync_api import sync_playwright

URL = "https://cgjvancouver.rsvsys.jp/reservations/calendar"
WEEKS_AHEAD = 6
EARLIER_THAN = "2026-06-08"  # alert only if slot strictly before this date (your booking day)
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_state.json")
EARLIER_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "earlier_state.json")


def notify(title: str, msg: str):
    print(f"[NOTIFY] {title}\n{msg}")
    u, p, to = os.environ.get("GMAIL_USER"), os.environ.get("GMAIL_APP_PASSWORD"), os.environ.get("NOTIFY_TO")
    if not (u and p and to):
        print("email skipped: GMAIL_USER / GMAIL_APP_PASSWORD / NOTIFY_TO not set")
        return
    try:
        m = EmailMessage()
        m["From"], m["To"], m["Subject"] = u, to, title
        m.set_content(f"{msg}\n\n{URL}")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(u, p)
            s.send_message(m)
    except Exception as e:
        print(f"email failed: {e}")


def scan_week(page) -> list[str]:
    """Return list like 'YYYY-MM-DD HH:MM (N left)' for every slot with remaining > 0."""
    # JS returns [{date, time, remain}] for each bookable cell
    data = page.evaluate(r"""() => {
        const res = [];
        const table = document.querySelector('table.c_cal_time');
        if (!table) return res;
        const heads = [...table.querySelectorAll('thead th')].slice(1);
        // header text like "04/24(金)" — combine with current nav year
        const navDate = document.querySelector('a.next02.js_change_date')?.getAttribute('data-date') || '';
        const year = navDate.split('/')[0] || new Date().getFullYear();
        const dates = heads.map(th => {
            const m = th.innerText.match(/(\d{1,2})\/(\d{1,2})/);
            return m ? `${year}-${m[1].padStart(2,'0')}-${m[2].padStart(2,'0')}` : '';
        });
        for (const tr of table.querySelectorAll('tbody tr')) {
            const timeCell = tr.querySelector('th');
            const time = timeCell ? timeCell.innerText.trim() : '';
            const tds = [...tr.querySelectorAll('td')];
            tds.forEach((td, i) => {
                const cell = td.querySelector('.c_cal_time_cell');
                if (!cell) return;
                if (cell.classList.contains('c_cal_time_cell--disabled')) return;
                const txt = cell.innerText.trim();
                // Extract remaining number from "残N人" or similar
                const m = txt.match(/(\d+)/);
                const remain = m ? parseInt(m[1], 10) : 0;
                if (remain > 0) res.push(`${dates[i]} ${time} (${remain} left)`);
            });
        }
        return res;
    }""")
    return data


def check() -> list[str]:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = browser.new_context().new_page()
        page.goto(URL, wait_until="networkidle")

        # Select "Visa application"
        page.locator('a[href="#event-select"]').first.click()
        page.wait_for_timeout(1500)
        page.locator('.modaal-wrapper label[for="event-2"]').click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1500)

        found = []
        for _ in range(WEEKS_AHEAD):
            found += scan_week(page)
            prev = page.locator('a.next02.js_change_date').first.get_attribute('data-date') or ''
            nxt = page.locator('a.next02.js_change_date').first
            if nxt.count() == 0:
                break
            nxt.click()
            # Wait for nav date to change
            for _ in range(20):
                page.wait_for_timeout(400)
                cur = page.locator('a.next02.js_change_date').first.get_attribute('data-date') or ''
                if cur and cur != prev:
                    break
            page.wait_for_load_state("networkidle")

        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "last.html"), "w", encoding="utf-8") as f:
            f.write(page.content())
        browser.close()
        return sorted(set(found))


def main():
    try:
        slots = check()
    except Exception as e:
        notify("Visa checker ERROR", str(e)[:500])
        sys.exit(1)

    prev = {}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            prev = json.load(f)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

    if slots and slots != prev.get("slots", []):
        notify(f"Japan visa slots available ({len(slots)} open)",
               "\n".join(slots[:20]) + (f"\n...and {len(slots)-20} more" if len(slots) > 20 else ""))
    else:
        print(f"[{now}] no change (open: {len(slots)})")

    with open(STATE_FILE, "w") as f:
        json.dump({"ts": now, "slots": slots}, f)

    # Earlier-than filter: alert if any slot is strictly before EARLIER_THAN
    earlier = [s for s in slots if s[:10] < EARLIER_THAN]
    prev_earlier = []
    if os.path.exists(EARLIER_STATE_FILE):
        with open(EARLIER_STATE_FILE) as f:
            prev_earlier = json.load(f).get("slots", [])
    if earlier and earlier != prev_earlier:
        notify(f"EARLIER visa slot before {EARLIER_THAN}! ({len(earlier)} open)",
               "\n".join(earlier))
    with open(EARLIER_STATE_FILE, "w") as f:
        json.dump({"ts": now, "slots": earlier}, f)


if __name__ == "__main__":
    main()
