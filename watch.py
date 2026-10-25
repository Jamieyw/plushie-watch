#!/usr/bin/env python3
"""Watch claude.dev/terminal for a plushie/sticker restock or a new swag drop.

Signals checked each run:
  1. https://claude.dev/terminal/swag-status.json  -> {"off": [...]}; the site itself
     uses this to decide "All claimed for now". An item missing from "off" = available.
  2. The swag list embedded in the terminal page (new items = new drop).
  3. The Brilliant redemption forms; they currently redirect to .../sorry.

Alerts via macOS notification (+ optional phone push through ntfy.sh if
NTFY_TOPIC is set). Only alerts when the state changes, so it won't spam.
"""
import json, os, re, subprocess, sys, urllib.request, urllib.error
from datetime import datetime
from pathlib import Path

UA = "Mozilla/5.0 (plushie-watch; personal restock monitor)"
HERE = Path(__file__).resolve().parent
STATE = HERE / "state.json"
LOG = Path(os.environ.get("PLUSHIE_LOG", HERE / "watch.log"))
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
STATUS_URL = "https://claude.dev/terminal/swag-status.json"
PAGE_URL = "https://claude.dev/terminal/"


def log(msg):
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line)
    with LOG.open("a") as f:
        f.write(line + "\n")


def get(url, follow=True):
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    opener = urllib.request.build_opener() if follow else urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Cache-Control": "no-cache"})
    try:
        with opener.open(req, timeout=20) as r:
            return r.status, r.headers, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.headers, ""


def notify(title, body, url=PAGE_URL):
    log(f"ALERT: {title} - {body}")
    if sys.platform == "darwin":
        mac_alert(title, body, url)
    if NTFY_TOPIC:
        req = urllib.request.Request(
            f"https://ntfy.sh/{NTFY_TOPIC}", data=body.encode(),
            headers={"Title": title, "Priority": "urgent", "Click": url, "Tags": "teddy_bear"})
        try:
            urllib.request.urlopen(req, timeout=20)
        except Exception as e:
            log(f"ntfy push failed: {e}")


def mac_alert(title, body, url):
    # A sound + a dialog that stays up until clicked (and shows through Focus modes);
    # gives up after an hour so checks resume.
    subprocess.Popen(["afplay", "/System/Library/Sounds/Glass.aiff"])
    script = (f'set r to display alert {json.dumps(title)} message {json.dumps(body)} '
              f'buttons {{"Dismiss", "Open claude.dev"}} default button 2 giving up after 3600\n'
              f'if button returned of r is "Open claude.dev" then open location {json.dumps(url)}')
    subprocess.run(["osascript", "-e", script], check=False)


def swag_items():
    """Parse the swag config (id, command, formUrl) embedded in the page."""
    _, _, html = get(PAGE_URL)
    html = html.replace('\\"', '"')
    items = {}
    for m in re.finditer(r'\{"id":"([a-z0-9_-]+)","command":"(/[a-z]+)","name":"([^"]+)"(?:,"formUrl":"([^"]+)")?', html):
        items[m.group(1)] = {"command": m.group(2), "name": m.group(3), "formUrl": m.group(4)}
    return items


def form_open(url):
    if not url:
        return False
    code, headers, _ = get(url, follow=False)
    loc = headers.get("Location", "") if headers else ""
    return not (300 <= code < 400 and loc.rstrip("/").endswith("/sorry"))


def main():
    prev = json.loads(STATE.read_text()) if STATE.exists() else {}

    code, _, body = get(STATUS_URL)
    off = set(json.loads(body).get("off", [])) if code == 200 else None
    items = swag_items()
    if off is None or not items:
        log(f"check failed (status {code}, {len(items)} items parsed); will retry next run")
        return

    cur = {}
    for sid, it in items.items():
        cur[sid] = {**it, "available": sid not in off, "form_open": form_open(it["formUrl"])}

    for sid, it in cur.items():
        was = prev.get(sid)
        live = it["available"] or it["form_open"]
        if was is None and prev:
            notify("New claude.dev swag drop!", f"{it['name']}: type {it['command']} at claude.dev/terminal")
        elif live and not (was["available"] or was["form_open"]):
            notify("Claude swag is BACK!", f"{it['name']} looks available. Type {it['command']} at claude.dev/terminal NOW")

    STATE.write_text(json.dumps(cur, indent=2))
    summary = ", ".join(f"{k}={'AVAILABLE' if v['available'] else 'off'}/form={'open' if v['form_open'] else 'sorry'}"
                        for k, v in cur.items())
    log(summary)


if __name__ == "__main__":
    if "--test-notify" in sys.argv:
        notify("plushie-watch test", "Notifications work. You'll see this when Clawd is back.")
    else:
        main()
