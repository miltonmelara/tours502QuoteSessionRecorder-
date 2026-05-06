# Tours502 Quote Session Recorder

A local desktop development tool for recording how human travel agents manually create travel quotes.

This tool is **NOT** the main quote-generation agent. Its sole purpose is to capture correct human quoting sessions so they can later be used as training data, decision examples, and golden test cases for the automated Tours502 quote creation system.

---

## 1. What the App Does

- Launches a Playwright-controlled Chromium browser on the agent's computer
- Records every URL visited, page title, click, and form input (with automatic redaction of sensitive fields)
- Takes automatic screenshots after page navigations and when notes are added
- Lets the agent write structured reasoning notes during the session:
  - Why they chose a particular site
  - Why they rejected or shortlisted an option
  - Reusable protocol rules observed
  - Escalation or uncertainty notes
- Lets the agent record structured decision records for each option evaluated
- At session end, packages everything into a structured ZIP file ready to email to the developer

---

## 2. What It Does NOT Do

- Does **not** automate quote creation — it only records human work
- Does **not** send data anywhere automatically
- Does **not** require a cloud backend, internet connection (beyond browsing), or API keys
- Does **not** store passwords, credit cards, CVV, passport numbers, or other sensitive values
- Does **not** require a server, Docker, or any cloud account

---

## 3. Installation

### Prerequisites

- Python 3.11 or newer
- `pip` (bundled with Python)
- Internet access for `pip install` and `playwright install chromium`

### Step 1 — Clone or extract the project

```bash
cd ~/projects
# git clone <repo-url> tours502QuoteSessionRecorder
# OR extract the ZIP you received
cd tours502QuoteSessionRecorder
```

### Step 2 — Create a virtual environment

```bash
python -m venv .venv
```

**Windows (Command Prompt):**
```cmd
.venv\Scripts\activate
```

**macOS / Linux:**
```bash
source .venv/bin/activate
```

### Step 3 — Install Python dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Install Playwright Browsers

After installing the Python packages, download the Chromium browser binary:

```bash
playwright install chromium
```

This downloads ~150 MB and only needs to be done once per machine (or when Playwright is upgraded).

---

## 5. Running Locally

With the virtual environment active:

```bash
python -m app.main
```

The desktop window will open. Logs are written to `logs/app.log`.

---

## 6. Starting a Recording Session

1. **Fill in the Session Setup form** on the left panel:
   - Agent Name (required)
   - Client / Reference (required)
   - Destination, travel dates, travelers, budget, trip type, etc.

2. Click **▶ Start Recording**

3. A Chromium browser window opens. Browse normally to research the quote.

4. The app records all navigations, clicks, and form inputs automatically.

5. Use the **Notes panel** on the right to add reasoning notes at any time:
   - Select a note type (Site Choice Reason, Option Rejected, etc.)
   - Type your reasoning
   - Click **Add Note**

6. Use **⚖ Add Decision** in the toolbar to record a structured decision about a specific option (hotel, flight, tour, etc.).

7. Use **⏸ Pause** if you need to enter sensitive information (payment details, passwords). Recording resumes with **▶ Resume**.

8. Use **📷 Screenshot** to capture a manual screenshot at any moment.

---

## 7. Finishing a Session and Exporting the ZIP

1. Click **⏹ Finish Recording** in the toolbar.
2. Confirm the dialog.
3. Click **🗜 Generate ZIP**.
4. The app creates a ZIP file in the `exports/` folder.
5. A success dialog shows the exact file path.
6. Click **📂 Open Folder** to open the folder in your file explorer.
7. Attach the ZIP file to an email to the developer.

---

## 8. Export / Folder Structure

Each session creates a folder:

```
exports/
  session_YYYYMMDD_HHMMSS_AgentName_ClientRef/
    session.json          ← session metadata and form fields
    events.json           ← all browser events (navigations, clicks, inputs)
    notes.json            ← all reasoning notes written during the session
    decisions.json        ← all structured decision records
    metadata.json         ← summary counts, app version, OS, browser engine
    screenshots/
      001_navigation_example_com.png
      002_note_site_choice_reason.png
      …
    snapshots/            ← text snapshots of visited pages (MVP: .txt)
    final_quote/          ← (empty unless you manually place files here)

exports/
  quote-session_AgentName_ClientRef_YYYYMMDD_HHMMSS.zip   ← final export
```

All timestamps are ISO 8601 UTC. All session IDs are UUIDs.

---

## 9. Privacy Warning

> **IMPORTANT:** This tool records your browser activity.
>
> - **Do NOT** type passwords, credit card numbers, CVV codes, personal ID documents, or passport numbers while recording is active.
> - **Pause recording** before entering any sensitive information, then resume afterwards.
> - The app automatically redacts common sensitive field types (password fields, hidden fields, fields named `password`, `card`, `cvv`, `token`, `passport`, etc.) but **automated redaction is not 100% reliable**.
> - The recorded ZIP files contain session data. Treat them as confidential internal development files.
> - Do not share ZIP files outside the development team.

---

## 10. Packaging for Windows and macOS

The project is structured for packaging with **Briefcase** (recommended) or **PyInstaller**.

### Option A — Briefcase (recommended)

Install Briefcase:
```bash
pip install briefcase
```

**Create the app scaffolding** (first time only):
```bash
briefcase create
```

**Build:**
```bash
# macOS .app
briefcase build macOS

# Windows .exe
briefcase build windows
```

**Run the built app:**
```bash
briefcase run macOS
briefcase run windows
```

> **Note:** Playwright browsers must be available inside the packaged app. You may need to bundle the Chromium binary manually or add a first-run install step. Playwright packaging with PyInstaller/Briefcase requires extra care — see the [Playwright packaging docs](https://playwright.dev/python/docs/intro).

### Option B — PyInstaller (one-file exe)

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "Tours502QuoteRecorder" app/main.py
```

The output `.exe` / `.app` will be in `dist/`.

> PyInstaller does not bundle Playwright browsers automatically. Ship a post-install script that runs `playwright install chromium`.

---

## Running Tests

```bash
pytest tests/
```

Tests cover:
- Pydantic schema round-trip validation for all 4 schemas
- ZIP export structure and contents

Tests do **not** require a browser or display.

---

## MVP Limitations

- HTML snapshots are not implemented (text snapshots only)
- Email sending is not implemented — attach ZIP manually
- Playwright browser packaging in `.exe`/`.app` requires additional configuration beyond this MVP
- The event bridge from Playwright's thread to Qt uses `QMetaObject.invokeMethod`; a `QueuedConnection` signal approach would be slightly cleaner in a future refactor
- No support for multi-tab tracking (only the primary Playwright page is instrumented)
