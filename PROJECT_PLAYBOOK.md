# Test Case Documentation Agent — Project Playbook

**Repository:** https://github.com/rakeshbob007/test-case-documentation-agent (private)

---

## 1. Complete Overview

The **Test Case Documentation Agent** is a self-hosted, zero-license-cost tool
that converts a demonstrated application workflow — either a screen recording
or a plain-English step guide — into a formal, client-ready Word (`.docx`)
test case document.

Instead of a QA engineer manually watching a workflow, writing steps, taking
screenshots, cropping/pasting them into a table, and formatting a document by
hand, this agent automates the entire chain:

1. Capture the workflow (upload a video, or record one in-app; or just type
   the steps in English).
2. Understand the workflow (Claude reads the video frames, or drives a real
   browser through the typed steps itself).
3. Author the test cases (functional, or functional + edge/negative cases).
4. Produce a Word document that matches the QA team's own template
   structure, with a real screenshot as evidence embedded directly in each
   Expected Result cell.

It runs entirely on the user's own machine, using the user's own Claude
subscription — there is no server, no SaaS fee, and no data leaves the
laptop except the Claude API calls themselves.

## 2. System Design

```
                        ┌───────────────────────────────┐
                        │        Streamlit UI (app.py)   │
                        │  - JIRA ID / template upload    │
                        │  - Workflow source picker        │
                        │  - Save-location picker          │
                        └───────────────┬───────────────┘
                                        │
              ┌─────────────────────────┼─────────────────────────┐
              │                         │                         │
   ┌──────────▼─────────┐   ┌───────────▼───────────┐   ┌─────────▼─────────┐
   │  Video Upload mode  │   │ Manual Step Guide mode │   │  Built-in Recorder │
   │  imageio-ffmpeg     │   │ Playwright MCP browser │   │  recorder_server.py│
   │  extracts N frames  │   │ automation, driven      │   │  (local HTTP)      │
   │                     │   │ live by Claude          │   │  recorder.html     │
   └──────────┬──────────┘   └───────────┬────────────┘   │  (floating panel,  │
              │                          │                 │  MediaRecorder API)│
              └────────────┬─────────────┘                 └─────────┬──────────┘
                           │                                          │
                           ▼                                          │
              ┌────────────────────────────┐                          │
              │  pipeline.py                │◄─── recording handed off via
              │  - build_prompt()            │      LAST_SAVED_POINTER file
              │  - write_mcp_config()         │
              │  - run_claude_streaming()      │
              └─────────────┬──────────────┘
                            │  subprocess: local claude.exe CLI
                            │  ("-p" headless mode, --dangerously-skip-permissions,
                            │   --mcp-config for Playwright tools)
                            ▼
              ┌────────────────────────────┐
              │  Claude Code (engine)        │
              │  - reads frames / drives      │
              │    real browser + screenshots │
              │  - reads reference .docx       │
              │    template structure           │
              │  - writes formal test cases      │
              │    with embedded screenshots       │
              └─────────────┬──────────────────┘
                            ▼
                 Final .docx test case document
                 saved to the user-chosen folder
```

**Key design decisions:**

- **Local-first, no server**: a Streamlit app on `localhost:8501` plus a
  small local HTTP server (`recorder_server.py`) for the recorder — nothing
  is hosted externally.
- **Claude Code as the reasoning + authoring engine**, invoked headlessly
  (`claude -p ... --dangerously-skip-permissions`) via a **project-local**
  native `claude.exe` binary (installed by `npm install`, not global) to
  sidestep Windows PATH/shim and corporate-security restrictions on the
  global npm install location.
- **Two independent workflow-capture paths** feeding one shared prompt
  builder (`pipeline.build_prompt`): video frames (extracted with
  `imageio-ffmpeg`) or a live Playwright browser session (via a **locally
  pinned** `@playwright/mcp` dependency, run directly instead of
  `npx ...@latest` so every generation skips a registry round-trip) that
  Claude itself drives, highlighting and screenshotting each interacted
  element.
- **Template-matching**: if the user uploads a reference `.docx`, Claude is
  instructed to replicate its exact structure/headers and only populate the
  content — otherwise a clean standard test case table is generated.
- **Built-in recorder** as a third capture option: a floating, draggable
  control panel (`recorder.html`, plain JS + the browser's native
  `MediaRecorder`/`getDisplayMedia` APIs) that uploads the finished
  recording to the local server, which writes a pointer file the main
  Streamlit page auto-polls (`st.fragment(run_every="2s")`) so the recording
  appears without a manual refresh.

## 3. Tokens Used to Build This Setup

Exact cumulative token spend across the *entire* multi-session build (this
project was built over several Claude Code sessions with automatic context
compaction in between) isn't retained anywhere as a single number — Claude
Code doesn't keep a running total across sessions. The one number that is
directly measurable is this session's own usage, reported by the platform:

| Metric (this session, live measurement) | Value |
|---|---|
| Tokens used | **~79,300 tokens** |
| % of a 1,000,000-token context window | **8%** |
| Plan | Team |
| 5-hour usage window consumed | 35% |
| Weekly usage window consumed | 23% |

Given the number of prior sessions this project went through (initial
scaffolding, the Video Upload pipeline, the Manual Step Guide/Playwright
integration, the built-in recorder, multiple rounds of UI/UX polish, the
GitHub push tooling, and this documentation pass), a reasonable order of
magnitude for the **full build** is in the **low hundreds of thousands of
tokens** — but treat that as an estimate, not a metered figure, since no
single tool reports it.

## 4. Advantages of Using This Agent

*(Manual-side figures reflect real-world, live-project experience — full
test case documentation for a workflow typically runs half a day to a full
working day by hand. Adjust to your own team's actuals as you track more
generations.)*

| Activity | Manual process (real-world) | With this agent | Estimated savings |
|---|---|---|---|
| Full test case documentation for one workflow (replay/study the flow, write steps, capture & place screenshots, format into the team's template, review) | **Half a day – 1 full day (~4–8 hours)** | **~5–10 minutes** (mostly the generation run itself) | **~95–99% time — roughly 3.8–7.8 hours saved per document** |

**Cost angle:** at a loaded QA rate of roughly $25–$40/hour, saving
~4–8 hours per test case document works out to **~$100–$320 saved per
document** in engineer time. For a QA function producing, say, 20 documents
a month, that's **~$2,000–$6,400/month, ~$24,000–$76,800/year** in reclaimed
engineer time — against **$0 licensing cost**, since this runs on an
existing Claude subscription with no additional SaaS spend.

**Non-monetary advantages:**
- Consistent formatting every time — no more per-engineer style drift.
- Evidence (screenshots) is never forgotten or mismatched to the wrong step.
- Frees QA engineers to spend time on actual test *design* and exploratory
  testing rather than document production.
- Fully private/local — no workflow data or credentials leave the machine
  except what's sent to Claude itself.

## 5. Complete Features (End to End)

- **JIRA ID field (optional)** — stamped into the generated document as a
  label/ID prefix; no live JIRA connection required.
- **Reference template upload (optional, `.docx`)** — Claude replicates the
  uploaded template's exact structure and headers, only filling in content.
- **Two workflow-source modes:**
  - **Video Upload** — upload a screen recording (`mp4`/`mov`/`avi`/`mkv`/`webm`);
    frames are sampled (`imageio-ffmpeg`, user-adjustable 5–40 frames) and
    the most relevant frame is embedded per test case.
  - **Manual Step Guide** — type the workflow in plain English; Claude
    drives a **real Playwright browser** through it, highlights the exact
    element each step acted on, and screenshots it as evidence. Choice of
    **headless** (fast, invisible) or **headed** (visible, for
    watching/verifying the run).
- **Built-in screen recorder** — a "Record" button opens a popup collecting
  a save folder and target URL, opens the target page plus a floating,
  draggable recording control panel (Start/Pause/Stop) in the user's real
  browser, uploads the finished recording to a local server, and
  auto-populates the main page the moment it's ready (no manual refresh).
- **Additional guidelines (optional free text)** — applied on top of
  whichever workflow source was used (e.g. "also cover mobile viewport
  sizes").
- **Test case scope control** — functional-only, or functional + edge/negative
  cases.
- **Output folder picker** — native OS folder-browse dialog (runs in its own
  isolated process for reliability) or manual path entry; validated before
  generation.
- **Live progress bar** during generation, streaming from the underlying
  headless Claude Code CLI run, ending in a success message and a one-click
  download button for the finished document.
- **Automatic image handling** — each embedded screenshot/frame is resized
  to fit cleanly inside its table cell, and the document auto-switches to
  landscape orientation if needed so the table never overflows the page.
- **Polished terminal-style UI** — a live-typing hero prompt, a pulsing
  status glow, and scanning section dividers, with full author credit.

## 6. Credits

Designed, built, and delivered end-to-end by:

**Rakesh Yadav Kodigandla**
Senior Specialist | Bristlecone
QA Engineer — 6.5+ years of experience
Built using **Python**, **Playwright** browser automation, **Streamlit**,
and **Claude Code**, applying hands-on QA domain expertise to shape the
prompt design, workflow-capture UX, and template-matching logic that make
the generated documents production-ready.

**Repository:** https://github.com/rakeshbob007/test-case-documentation-agent

## 7. Developer Details

| | |
|---|---|
| Name | Rakesh Yadav Kodigandla |
| Title | Senior Specialist |
| Organization | Bristlecone |
