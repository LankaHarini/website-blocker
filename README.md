#  FocusGuard — Website Blocker

Block distracting websites for specific time windows. Blocks apply automatically and lift when the scheduled window ends.

---

##  Requirements

- **Python 3.7+**
- **Flask** (`pip install flask`)

---

##  How to Run

### Windows
1. Open **Command Prompt as Administrator** (right-click → Run as administrator).
2. Navigate to this folder:
   ```
   cd path\to\FocusGuard
   ```
3. Install Flask (if not already installed):
   ```
   pip install flask
   ```
4. Start the app:
   ```
   python app.py
   ```
5. Open your browser → **http://127.0.0.1:5000**

### Linux / macOS
1. Open a **Terminal as root** (`sudo bash`).
2. Navigate to this folder and run:
   ```
   pip install flask
   python app.py
   ```
3. Open **http://127.0.0.1:5000**

> **Administrator / Root access is required** because the app modifies the system `hosts` file to block sites.

---

##  How It Works

| Step | What happens |
|------|-------------|
| 1 | You add a website + a time window (e.g. facebook.com, 09:00–17:00). |
| 2 | During that window, the app writes the domain into your system **hosts** file pointing to `127.0.0.1`. |
| 3 | Any browser trying to load that site gets blocked. |
| 4 | When the time window ends, the entry is automatically removed (every 30 seconds). |

---

##  File Structure

```
FocusGuard/
├── app.py              ← Python backend (Flask server)
├── blocks.json         ← Saved blocks (auto-created)
├── static/
│   └── index.html      ← Full UI (HTML + CSS + JS)
└── README.md           ← This file
```

---

##  UI Features

- **Add Block** — Set a domain and a start/end time window.
- **Toggle** — Enable/disable any block without deleting it.
- **Check Access** — Test whether a site is currently blocked.
- **Live status** — Cards show "Blocking Active" or "Inactive" in real time.
- **Auto-refresh** — The UI and hosts file refresh every 30 seconds.
