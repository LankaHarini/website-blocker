"""
╔════════════════════════════════════════════════════════════╗
║            FocusGuard — Website Blocker                    ║
║                                                            ║
║  pip install flask                                         ║
║  python app.py                                             ║
║  → open http://127.0.0.1:5000                              ║
║                                                            ║
║  Windows : run Command Prompt as Administrator             ║
║  Linux/Mac: sudo python app.py                             ║
╚════════════════════════════════════════════════════════════╝

Architecture
────────────
• ALL logic lives here: time checks, hosts-file edits, validation,
  HTML generation, routing.
• index.html contains ONLY <style> (CSS).  Python reads that file,
  extracts the <style> block, and wraps it around dynamically-built
  HTML on every request.  The browser never sees a "template" —
  it receives a fully-formed page assembled by Python.
"""

import os
import json
import platform
import threading
import time
from datetime import datetime
from flask import Flask, request, redirect, url_for

# ──────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder=None)          # no static dir needed

BASE      = os.path.dirname(os.path.abspath(__file__))
DATA      = os.path.join(BASE, "blocks.json")
CSS_FILE  = os.path.join(BASE, "index.html")       # contains only <style>…</style>

if platform.system() == "Windows":
    HOSTS = os.path.join(
        os.environ.get("SystemRoot", r"C:\Windows"),
        "System32", "drivers", "etc", "hosts"
    )
else:
    HOSTS = "/etc/hosts"

HDR_START = "# === FocusGuard START ===\n"
HDR_END   = "# === FocusGuard END ===\n"

# ──────────────────────────────────────────────────────────────
# DATA  (os + json)
# ──────────────────────────────────────────────────────────────
def load() -> list:
    if not os.path.exists(DATA):
        return []
    with open(DATA, "r", encoding="utf-8") as fh:
        return json.load(fh)

def save(blocks: list) -> None:
    with open(DATA, "w", encoding="utf-8") as fh:
        json.dump(blocks, fh, indent=2, ensure_ascii=False)
# ──────────────────────────────────────────────────────────────
# DOMAIN
# ──────────────────────────────────────────────────────────────
def clean_domain(raw: str) -> str:
    d = raw.strip().lower()
    for p in ("https://", "http://", "www."):
        d = d.replace(p, "")
    return d.split("/")[0]

# ──────────────────────────────────────────────────────────────
# TIME  (datetime)
# ──────────────────────────────────────────────────────────────
def hhmm_to_mins(t: str) -> int:
    h, m = map(int, t.split(":"))
    return h * 60 + m

def now_mins() -> int:
    n = datetime.now()
    return n.hour * 60 + n.minute

def now_secs() -> int:
    n = datetime.now()
    return n.hour * 3600 + n.minute * 60 + n.second

def is_active(b: dict) -> bool:
    """True when block is enabled AND current time is inside its window."""
    if not b.get("enabled", True):
        return False
    now   = now_mins()
    start = hhmm_to_mins(b["start"])
    end   = hhmm_to_mins(b["end"])
    if end <= start:                    # overnight eg 22:00-06:00
        return now >= start or now < end
    return start <= now < end

def secs_left(b: dict) -> int:
    """Seconds until the block's end time."""
    ns  = now_secs()
    eh, em = map(int, b["end"].split(":"))
    end_s  = eh * 3600 + em * 60
    sh, sm = map(int, b["start"].split(":"))
    start_s = sh * 3600 + sm * 60
    if end_s <= start_s:
        end_s += 86400
    d = end_s - ns
    return d if d >= 0 else d + 86400

def fmt_countdown(s: int) -> str:
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m {sec:02d}s"
    if m:
        return f"{m}m {sec:02d}s"
    return f"{sec}s"

# ──────────────────────────────────────────────────────────────
# HOSTS FILE  (os)
# ──────────────────────────────────────────────────────────────
def apply_hosts(blocks: list) -> bool:
    """
    Rewrite the system hosts file.
    Returns True on success, False on permission error.
    """
    try:
        with open(HOSTS, "r") as fh:
            txt = fh.read()
    except PermissionError:
        return False
    except FileNotFoundError:
        txt = ""

    # strip old block
    if HDR_START in txt and HDR_END in txt:
        txt = txt[:txt.index(HDR_START)] + txt[txt.index(HDR_END) + len(HDR_END):]

    # new entries
    lines = ""
    for b in blocks:
        if is_active(b):
            lines += f"127.0.0.1\t{b['domain']}\n"
            lines += f"127.0.0.1\twww.{b['domain']}\n"

    if lines:
        txt = txt.rstrip("\n") + "\n\n" + HDR_START + lines + HDR_END

    try:
        with open(HOSTS, "w") as fh:
            fh.write(txt)
        return True
    except PermissionError:
        return False

# ──────────────────────────────────────────────────────────────
# BACKGROUND THREAD — keeps hosts in sync every 30 s
# ──────────────────────────────────────────────────────────────
def _bg():
    while True:
        apply_hosts(load())
        time.sleep(30)

# ──────────────────────────────────────────────────────────────
# CSS LOADER  — reads the single <style> block from index.html
# ──────────────────────────────────────────────────────────────
_CSS_CACHE = None

def get_css() -> str:
    global _CSS_CACHE
    if _CSS_CACHE is None:
        with open("index.html", "r", encoding="utf-8") as fh:
            raw = fh.read()
        with open("index.html", "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
        # extract everything between <style> and </style>
        s = raw.index("<style>")
        e = raw.index("</style>") + len("</style>")
        _CSS_CACHE = raw[s:e]
    return _CSS_CACHE

# ──────────────────────────────────────────────────────────────
# HTML BUILDERS  — Python assembles every pixel
# ──────────────────────────────────────────────────────────────

def _navbar() -> str:
    return """
<header class="navbar">
  <div class="navbar-left">
    <div class="navbar-icon">
      <svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" width="22" height="22">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
      </svg>
    </div>
    <div>
      <div class="navbar-title">FocusGuard</div>
      <div class="navbar-sub">Reclaim your attention</div>
    </div>
  </div>
  <a href="#add-modal" class="btn-add">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" width="15" height="15">
      <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
    </svg>
    Add Block
  </a>
</header>"""

def _hero(toast: str) -> str:
    return f"""
<section class="hero">
  <h1>Test your filters</h1>
  <p>Try visiting a blocked site to see FocusGuard in action.</p>
  <form class="search-bar" action="/check" method="POST">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" width="18" height="18" class="search-icon">
      <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
    </svg>
    <input type="text" name="domain" placeholder="Enter a website URL (e.g. facebook.com)…" autocomplete="off"/>
    <button type="submit" class="btn-check">Check Access</button>
  </form>
  {toast}
</section>"""

def _toast_blocked(domain, until):
    return f'<div class="toast toast-blocked">🚧 <strong>{domain}</strong> is currently blocked until <strong>{until}</strong>.</div>'

def _toast_scheduled(domain, window):
    return f'<div class="toast toast-info">ℹ️ <strong>{domain}</strong> is scheduled ({window}) but not active right now.</div>'

def _toast_free(domain):
    return f'<div class="toast toast-ok">✅ <strong>{domain}</strong> is not blocked — it\'s not in your list.</div>'

def _toast_empty():
    return '<div class="toast toast-info">ℹ️ Please enter a domain to check.</div>'


def _one_card(b: dict) -> str:
    """Build a single block-card exactly matching the screenshot."""
    active      = is_active(b)
    left_color  = "var(--red)" if active else "transparent"
    border_color= "rgba(239,68,68,.18)" if active else "var(--border)"

    # --- toggle: a <form> with a styled checkbox + hidden submit ---
    checked = "checked" if b.get("enabled", True) else ""
    toggle = f"""
    <form class="toggle-wrap" action="/toggle" method="POST">
      <input type="hidden" name="domain" value="{b['domain']}"/>
      <div class="toggle">
        <input type="checkbox" {checked} class="toggle-input"/>
        <span class="toggle-knob"></span>
        <button type="submit" class="toggle-submit"></button>
      </div>
    </form>"""

    # --- countdown line (only when active) ---
    countdown = ""
    if active:
        countdown = f'<div class="card-countdown">Unblocks in {fmt_countdown(secs_left(b))}</div>'

    # --- badge ---
    if active:
        badge = '<span class="badge badge-active"><span class="badge-dot"></span>Blocking Active</span>'
    else:
        badge = '<span class="badge badge-inactive">Inactive</span>'

    # --- delete button (form) ---
    delete = f"""
    <form class="delete-wrap" action="/delete" method="POST">
      <input type="hidden" name="domain" value="{b['domain']}"/>
      <button type="submit" class="btn-delete" title="Remove">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="18" height="18">
          <polyline points="3 6 5 6 21 6"/>
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
        </svg>
      </button>
    </form>"""

    return f"""
<div class="card" style="border-left:4px solid {left_color}; border-color:{border_color};">
  <div class="card-top">
    <div class="card-left">
      <div class="card-domain">{b['domain']}</div>
      <div class="card-time">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" width="14" height="14">
          <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
        </svg>
        {b['start']} – {b['end']}
      </div>
      {countdown}
    </div>
    {toggle}
  </div>
  <div class="card-bottom">
    {badge}
    {delete}
  </div>
</div>"""


def _cards_section(blocks: list) -> str:
    count = len(blocks)
    label = f"{count} site{'s' if count != 1 else ''} configured"

    if count == 0:
        inner = """
        <div class="empty-state">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" width="48" height="48">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          </svg>
          <p><strong>No blocks yet.</strong><br/>Click <strong style="color:var(--blue)">+ Add Block</strong> to get started.</p>
        </div>"""
    else:
        inner = "\n".join(_one_card(b) for b in blocks)

    return f"""
<section class="blocks-section">
  <div class="blocks-header">
    <div class="blocks-header-left">
      <svg viewBox="0 0 24 24" fill="none" stroke="var(--blue)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="20" height="20">
        <circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/>
        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
      </svg>
      <h2>Active Blocks</h2>
    </div>
    <span class="blocks-count">{label}</span>
  </div>
  <div class="cards-grid">
    {inner}
  </div>
</section>"""


def _modal(error: str) -> str:
    """
    The "Add Block" modal.  Triggered by the <a href="#add-modal">
    in the navbar and closed by <a href="#close-modal">.
    Pure CSS :target trick — no JS.
    """
    err_html = f'<div class="modal-error">{error}</div>' if error else ""
    return f"""
<div class="modal-overlay" id="add-modal">
  <div class="modal">
    <div class="modal-head">
      <h3>Block a Website</h3>
      <a href="#close-modal" class="modal-close">&#x2715;</a>
    </div>
    <form action="/add" method="POST">
      <div class="field">
        <label>Website Domain</label>
        <input type="text" name="domain" placeholder="e.g. facebook.com" autocomplete="off"/>
      </div>
      <div class="field">
        <label>Block Time Window</label>
        <div class="time-row">
          <div class="time-col">
            <label class="time-label">Start</label>
            <input type="time" name="start" value="09:00"/>
          </div>
          <span class="time-arrow">→</span>
          <div class="time-col">
            <label class="time-label">End</label>
            <input type="time" name="end" value="17:00"/>
          </div>
        </div>
      </div>
      <button type="submit" class="btn-submit">Add Block</button>
    </form>
    {err_html}
  </div>
</div>"""


def full_page(toast: str = "", error: str = "") -> str:
    """Assemble the complete HTML document.  CSS comes from index.html."""
    blocks = load()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>FocusGuard – Reclaim Your Attention</title>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet"/>
{get_css()}
</head>
<body>
{_navbar()}
<main class="main">
  {_hero(toast)}
  {_cards_section(blocks)}
</main>
{_modal(error)}
</body>
</html>"""

# ──────────────────────────────────────────────────────────────
# ROUTES
# ──────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return full_page()

@app.route("/check", methods=["POST"])
def check():
    raw = request.form.get("domain", "")
    domain = clean_domain(raw)
    if not domain:
        return full_page(toast=_toast_empty())

    for b in load():
        if b["domain"] == domain:
            if is_active(b):
                return full_page(toast=_toast_blocked(domain, b["end"]))
            return full_page(toast=_toast_scheduled(domain, f"{b['start']} – {b['end']}"))

    return full_page(toast=_toast_free(domain))

@app.route("/add", methods=["POST"])
def add():
    domain = clean_domain(request.form.get("domain", ""))
    start  = request.form.get("start", "09:00")
    end    = request.form.get("end",   "17:00")

    # validation — errors re-render page with modal open via error param
    if not domain:
        return full_page(error="Please enter a valid domain.")
    blocks = load()
    if any(b["domain"] == domain for b in blocks):
        return full_page(error=f"{domain} is already blocked.")
    if start == end:
        return full_page(error="Start and end time cannot be the same.")

    blocks.append({
        "domain":  domain,
        "start":   start,
        "end":     end,
        "enabled": True,
        "added":   datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    save(blocks)
    apply_hosts(blocks)
    return redirect(url_for("index"))

@app.route("/delete", methods=["POST"])
def delete():
    domain = request.form.get("domain", "")
    blocks = [b for b in load() if b["domain"] != domain]
    save(blocks)
    apply_hosts(blocks)
    return redirect(url_for("index"))

@app.route("/toggle", methods=["POST"])
def toggle():
    domain = request.form.get("domain", "")
    blocks = load()
    for b in blocks:
        if b["domain"] == domain:
            b["enabled"] = not b.get("enabled", True)
            break
    save(blocks)
    apply_hosts(blocks)
    return redirect(url_for("index"))

# ──────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    apply_hosts(load())
    threading.Thread(target=_bg, daemon=True).start()

    print("=" * 56)
    print("  🛡  FocusGuard")
    print(f"  🌐  http://127.0.0.1:5000")
    print(f"  📄  Hosts : {HOSTS}")
    print(f"  💾  Data  : {DATA}")
    print("  ⚠   Run as Administrator / root for real blocking")
    print("=" * 56)

    app.run(debug=False, host="127.0.0.1", port=5000)
