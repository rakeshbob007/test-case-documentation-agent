# Test Case Documentation Agent — User Guide

**Repository:** https://github.com/rakeshbob007/test-case-documentation-agent

This guide covers two things: (1) setting up the complete environment from
scratch, and (2) the full functional flow of using the app once it's
running.

---

## Part 1 — Environment Setup (clone → running app)

### Prerequisites

- **Windows** with **PowerShell**.
- **Python 3.10+** (not the Microsoft Store version — see the note below).
- **Node.js** (for the local Claude Code CLI and Playwright).
- An active **Claude subscription** that `claude auth login` can sign into.

### Step 1 — Clone the repository

```bash
git clone https://github.com/rakeshbob007/test-case-documentation-agent.git
cd test-case-documentation-agent
```

### Step 2 — Install Node dependencies

This installs the Claude Code CLI and the Playwright MCP server *locally* to
the project (not globally/via `npx ...@latest`), which avoids Windows PATH
and corporate-security issues with the global npm install location, and
skips a network round-trip to the npm registry on every generation.

```bash
npm install
```

### Step 3 — Log the local Claude Code CLI into your account

```bash
.\node_modules\@anthropic-ai\claude-code\bin\claude.exe auth login
```

Follow the browser login prompt that opens.

### Step 4 — Install Python dependencies

```bash
pip install -r requirements.txt
```

> **Windows Store Python warning:** if plain `python`/`pip` on your PATH
> resolve to the sandboxed Microsoft Store Python, it can silently fail to
> see files outside a few whitelisted folders — including the Claude CLI
> itself. If you hit "claude CLI not found" errors later, locate your real
> Python install (commonly
> `C:\Users\<you>\AppData\Local\Python\bin\python.exe`) and use that
> explicitly for both `pip install` and running the app.

### Step 5 — Install the headless browser (for Manual Step Guide mode)

```bash
npx playwright install chromium
```

### Step 6 — Point the launcher at your Python install

Open `run_app.ps1` and confirm the `$py` path matches your real
(non-sandboxed) Python executable:

```powershell
$py = "C:\Users\<you>\AppData\Local\Python\bin\python.exe"
& $py -m streamlit run "$PSScriptRoot\app.py"
```

### Step 7 — Open the main page

```bash
powershell -ExecutionPolicy Bypass -File run_app.ps1
```

This starts the Streamlit server and opens **http://localhost:8501** in
your browser — that's the main page of the agent.

---

## Part 2 — Functional Flow (how to use the app)

The main page walks you through three numbered steps, plus a Generate
action.

### Step 1 — Task details

- **JIRA ID (optional):** a text label (e.g. `PROJ-1234`) stamped onto the
  generated document. No live JIRA connection is made — it's just a label.
- **Reference test case template (optional, `.docx`):** upload your team's
  existing test case Word template. If provided, Claude reproduces its
  exact table structure and headers, only filling in new content. If
  skipped, a clean standard table is generated (Test Case ID, Title,
  Preconditions, Test Steps, Test Data, Expected Result, Priority).

### Step 2 — Workflow source

Choose one of two modes:

**A. Video Upload**
1. Upload a screen recording (`.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`), **or**
2. Click the **🔴 Record** button instead of uploading:
   - A wide popup asks for a **save folder** (its own full-width field, with
     a **Browse...** button below it so long paths are easy to read and
     edit) and the **target URL** you want to record.
   - Click **Proceed** — the target page opens in a new tab, and a small
     floating recorder panel (draggable, top-right) opens alongside it.
   - Log in / navigate as needed, then click **Start** in the panel to
     begin recording your screen (a native browser permission prompt asks
     which screen/window/tab to share).
   - Use **Pause**/**Resume** as needed, then click **Stop** when done.
   - The recording uploads automatically; the panel tells you to close that
     tab and switch back to the main Test Case Agent tab.
   - The main page **auto-detects the finished recording within a couple of
     seconds** and shows a "🎥 Recorded video ready" banner — no manual
     refresh needed. Click **Discard** if you'd rather re-record.
3. Adjust the **Max video frames to analyze** slider (5–40) — more frames
   catch more detail but take longer to process.

**B. Manual Step Guide**
1. Type the workflow in plain English, one instruction per line, e.g.:
   ```
   Navigate to facebook page
   Click on Login without giving credentials
   Validate the error message
   ```
2. Choose **Browser mode**:
   - *Headless (invisible, faster)* — runs in the background.
   - *Headed (visible browser window)* — a real browser window opens so you
     can watch Claude perform the steps live; useful to sanity-check the
     flow.
3. Claude will actually **drive a real Playwright browser** through your
   instructions, highlight the specific element each step interacts with,
   and capture a screenshot as evidence for that step.

**Additional guidelines (optional, either mode):** free-text extra
instructions layered on top of the workflow source, e.g. "also cover mobile
viewport sizes" or "focus on validation messages."

**Test case scope:**
- *Step-by-step functional test cases* — covers exactly the demonstrated
  workflow.
- *Functional + edge/negative test cases* — adds reasonable boundary,
  invalid-input, and error-state cases on top.

### Step 3 — Save location

- Click **Browse...** for a native folder picker, or type the destination
  path directly.
- The **Generate** button stays disabled until both a workflow source and
  an output folder are set — and pulses gently once it's ready to go.

### Generate

Click **Generate**. A progress bar tracks the run while, under the hood,
the app:
1. Extracts video frames (Video mode) or hands control to Claude to drive
   the real browser (Manual mode).
2. Builds a detailed prompt (including your template, JIRA ID, guidelines,
   and scope).
3. Runs the local Claude Code CLI headlessly against that prompt.
4. Claude reads the evidence (frames or live screenshots), writes the test
   cases, embeds the single most relevant image into each Expected Result
   cell (auto-resized, with the table switched to landscape if needed to
   avoid overflow), and saves the final `.docx` to your chosen folder.

When it finishes, the progress bar reaches "Done" and a green success
message plus a **Download the generated document** button appear right on
the main page — the formal test case Word document is also already sitting
in the output folder you selected, ready to attach to JIRA or send to the
customer.

---

*Developed by Rakesh Yadav Kodigandla | Senior Specialist | Bristlecone.*
