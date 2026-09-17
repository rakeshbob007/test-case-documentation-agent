import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.parse import urlencode

import streamlit as st

import recorder_server
from pipeline import (
    build_prompt,
    extract_frames,
    run_claude_streaming,
    write_mcp_config,
)

RUNS_DIR = Path(__file__).parent / ".runs"
AUTHOR_NAME = "Rakesh Yadav Kodigandla"
AUTHOR_TITLE = "Senior Specialist | Bristlecone"

RECORDER_PORT = recorder_server.ensure_recorder_server_running()


_PICK_FOLDER_SCRIPT = """
import tkinter as tk
from tkinter import filedialog
root = tk.Tk()
root.withdraw()
root.attributes("-topmost", True)
root.lift()
root.focus_force()
root.update()
print(filedialog.askdirectory(parent=root))
root.destroy()
"""


def pick_folder() -> str:
    """Open a native folder-picker dialog and return the chosen path (or ''
    if cancelled).

    Streamlit runs the script on a worker thread that shares the process
    with its own asyncio/Uvicorn event loop. A tkinter dialog created
    directly on that thread has to fight that loop for the OS message pump,
    and can silently return '' instead of actually waiting for the user's
    selection. Running the dialog in a completely separate process sidesteps
    that: it gets its own clean main thread with nothing else competing for
    the message loop, so the dialog reliably shows up, takes focus, and
    waits for a real answer."""
    result = subprocess.run(
        [sys.executable, "-c", _PICK_FOLDER_SCRIPT],
        capture_output=True,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return result.stdout.strip()


st.set_page_config(
    page_title="TEST_CASE_AGENT.exe",
    page_icon="\U0001F47E",
    layout="centered",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700;800&display=swap');

    :root {
        --brand-green: #0EA968;
        --brand-blue: #0284C7;
        --brand-purple: #7C3AED;
        --ink: #0F172A;
    }

    html, body, [class*="css"], .stMarkdown, label, p, span, div {
        font-family: 'JetBrains Mono', monospace !important;
    }
    /* Streamlit's icon glyphs are ligature text in the "Material Symbols
       Rounded" font - our blanket monospace override above breaks every
       icon on the page (upload icon, sidebar collapse arrow, help "?"
       icons, etc.) unless we explicitly restore the correct icon font here. */
    [data-testid="stIconMaterial"] {
        font-family: 'Material Symbols Rounded' !important;
    }

    .stApp {
        background: #FFFFFF;
    }
    .stApp::before {
        content: "";
        position: fixed;
        inset: 0;
        background-image:
            linear-gradient(rgba(15,23,42,0.035) 1px, transparent 1px),
            linear-gradient(90deg, rgba(15,23,42,0.035) 1px, transparent 1px);
        background-size: 42px 42px;
        pointer-events: none;
        z-index: 0;
    }

    .app-hero {
        position: relative;
        padding: 1.8rem 1.8rem 1.4rem;
        border-radius: 8px;
        border: 1px solid #E2E8F0;
        border-left: 4px solid var(--brand-green);
        background: #FAFCFB;
        margin-bottom: 1.6rem;
        overflow: hidden;
        animation: hero-glow 3s ease-in-out infinite;
    }
    @keyframes hero-glow {
        0%, 100% {
            box-shadow: 0 2px 14px rgba(15,23,42,0.06), 0 0 0 rgba(14,169,104,0);
            border-left-color: var(--brand-green);
        }
        50% {
            box-shadow: 0 4px 32px rgba(2,132,199,0.4), 0 0 26px rgba(2,132,199,0.28);
            border-left-color: var(--brand-blue);
        }
    }
    .app-hero::before {
        content: "";
        position: absolute;
        top: 0; left: -100%;
        width: 100%; height: 3px;
        background: linear-gradient(90deg, transparent, var(--brand-blue), var(--brand-green), transparent);
        box-shadow: 0 0 8px rgba(2,132,199,0.6);
        animation: scan 3.5s linear infinite;
    }
    @keyframes scan { 0% { left: -100%; } 100% { left: 100%; } }
    @keyframes blink { 50% { opacity: 0; } }

    .app-hero .tag {
        font-size: 0.72rem;
        letter-spacing: 0.28em;
        color: var(--brand-blue);
        text-transform: uppercase;
        margin-bottom: 0.5rem;
        opacity: 0.9;
    }
    .app-hero h1 {
        color: var(--brand-green) !important;
        font-size: 1.9rem !important;
        margin: 0 0 0.4rem 0 !important;
        letter-spacing: 0.01em;
    }
    .app-hero .cursor {
        display: inline-block;
        color: var(--brand-blue);
        animation: blink 1s step-end infinite;
    }
    .app-hero p {
        color: #334155;
        font-size: 0.88rem;
        margin: 0;
        line-height: 1.5;
    }
    .app-hero .prompt {
        color: var(--brand-purple);
        font-size: 0.8rem;
        margin-top: 0.7rem;
    }
    .app-hero .prompt .typewriter {
        display: inline-block;
        overflow: hidden;
        white-space: nowrap;
        vertical-align: bottom;
        border-right: 2px solid var(--brand-purple);
        width: 34ch;
        animation:
            typing-loop 7s ease-in-out infinite,
            caret-blink 0.8s step-end infinite;
    }
    @keyframes typing-loop {
        0% { width: 0; }
        30% { width: 34ch; }
        75% { width: 34ch; }
        95% { width: 0; }
        100% { width: 0; }
    }
    @keyframes caret-blink { 50% { border-color: transparent; } }

    .stMarkdown h3, .stMarkdown h4 {
        color: var(--brand-blue) !important;
        letter-spacing: 0.03em;
    }

    .stTextInput input, .stTextArea textarea {
        background-color: #FFFFFF !important;
        color: var(--ink) !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 4px !important;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: var(--brand-blue) !important;
        box-shadow: 0 0 0 3px rgba(2,132,199,0.15) !important;
    }

    .stButton>button[kind="primary"] {
        background: linear-gradient(135deg, #0EA968, #0284C7) !important;
        color: #FFFFFF !important;
        border: none !important;
        font-weight: 800 !important;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        box-shadow: 0 4px 14px rgba(14,169,104,0.3);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .stButton>button[kind="primary"]:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 20px rgba(2,132,199,0.4);
    }
    .stButton>button[kind="primary"]:not(:disabled) {
        animation: ready-pulse 2.4s ease-in-out infinite;
    }
    .stButton>button[kind="primary"]:not(:disabled):hover {
        animation: none;
    }
    @keyframes ready-pulse {
        0%, 100% { box-shadow: 0 4px 14px rgba(14,169,104,0.3); }
        50% { box-shadow: 0 4px 22px rgba(2,132,199,0.55); }
    }
    .stButton>button:not([kind="primary"]) {
        background: #F6F8FA !important;
        color: var(--brand-blue) !important;
        border: 1px solid #CBD5E1 !important;
    }

    div[data-testid="stProgress"] div div div {
        background: linear-gradient(90deg, #0EA968, #0284C7, #7C3AED) !important;
    }

    div[role="radiogroup"] label {
        border: 1px solid #CBD5E1;
        border-radius: 4px;
        padding: 2px 10px;
        margin-right: 6px;
    }

    section[data-testid="stSidebar"] {
        background: #FAFCFB;
        border-right: 1px solid #E2E8F0;
    }
    section[data-testid="stSidebar"] .credit-box {
        margin-top: 2rem;
        padding: 1rem;
        border-radius: 6px;
        border: 1px dashed var(--brand-purple);
        background: rgba(124,58,237,0.05);
        font-size: 0.82rem;
        text-align: center;
        color: var(--brand-purple);
    }
    section[data-testid="stSidebar"] .credit-box b {
        color: var(--brand-blue);
    }

    div[data-testid="stDivider"] hr, hr {
        border-top: 3px solid #0F172A !important;
        opacity: 1 !important;
    }
    div[data-testid="stDivider"] {
        position: relative;
        overflow: hidden;
    }
    div[data-testid="stDivider"]::after {
        content: "";
        position: absolute;
        top: -1px; left: -40%;
        width: 40%; height: 4px;
        background: linear-gradient(90deg, transparent, var(--brand-green), var(--brand-blue), transparent);
        box-shadow: 0 0 10px 1px rgba(2,132,199,0.7);
        animation: scan 3s linear infinite;
    }

    /* trim Streamlit's built-in hamburger menu down to what's relevant */
    [data-testid="stMainMenuItem-print"],
    [data-testid="stMainMenuItem-recordScreencast"] {
        display: none !important;
    }

    /* align a button placed beside a labeled input to the input's own
       bottom edge, not the top of the whole label+input block */
    div[data-testid="stHorizontalBlock"] {
        align-items: flex-end !important;
    }

    /* keep the hero readable and the layout from overflowing on narrow
       windows (e.g. a docked panel or a phone-width browser) */
    .block-container {
        max-width: 780px;
        padding-left: 1.2rem;
        padding-right: 1.2rem;
    }
    @media (max-width: 480px) {
        .app-hero { padding: 1.2rem 1.1rem 1rem; }
        .app-hero h1 { font-size: 1.4rem !important; }
        .app-hero p { font-size: 0.82rem; }
    }
    </style>
    <div class="app-hero">
        <div class="tag">// AI-POWERED QA AUTOMATION</div>
        <h1>&gt; TEST_CASE_AGENT<span class="cursor">_</span></h1>
        <p>Feed it a video or a plain-English step guide - it drives a real browser,
        captures evidence, and writes a polished Word test case doc. Powered by Claude Code.</p>
        <div class="prompt"><span class="typewriter">root@qa-agent:~$ awaiting input...</span></div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### // SYSTEM STATUS")
    st.write(
        "This tool drives Claude Code end-to-end: it reads your workflow "
        "(video or manual steps), writes formal test cases into a Word "
        "document matching your template, and backs each expected result "
        "with a real screenshot."
    )
    st.markdown(
        f'<div class="credit-box">&lt;/&gt; developed by<br>'
        f'<b>{AUTHOR_NAME}</b><br>'
        f'<span style="font-size:0.72rem; opacity:0.8;">{AUTHOR_TITLE}</span></div>',
        unsafe_allow_html=True,
    )

st.markdown("#### \U0001F4CB Step 1 - Task details")
jira_id = st.text_input("JIRA ID (optional)", placeholder="e.g. PROJ-1234")

template_file = st.file_uploader(
    "Reference test case template (optional, .docx)", type=["docx"]
)

st.divider()
st.markdown("#### \U0001F3AC Step 2 - Workflow source")
input_mode = st.radio(
    "Choose how to describe the workflow",
    options=["Video Upload", "Manual Step Guide"],
    horizontal=True,
    label_visibility="collapsed",
)

video_file = None
max_frames = 15
manual_step_guide = ""
headless = True

recorded_video_path = None

DEFAULT_RECORD_SAVE_DIR = str(RUNS_DIR / "recordings")

if "show_record_dialog" not in st.session_state:
    st.session_state.show_record_dialog = False
if "record_save_dir" not in st.session_state:
    st.session_state.record_save_dir = ""
if "record_target_url" not in st.session_state:
    st.session_state.record_target_url = ""


def _browse_record_save_dir():
    folder = pick_folder()
    if folder:
        st.session_state.record_save_dir = folder


@st.dialog("Record workflow", width="large")
def record_dialog():
    st.caption(
        "Choose where the finished recording should be saved, and the page "
        "you want to record. You'll get a chance to log in on that page "
        "before you click Start."
    )

    st.text_input(
        "Save recording to folder", key="record_save_dir",
        placeholder=DEFAULT_RECORD_SAVE_DIR,
    )
    st.button("Browse...", key="record_browse_btn", on_click=_browse_record_save_dir)

    st.text_input(
        "Page URL to record", placeholder="https://www.facebook.com",
        key="record_target_url",
    )

    save_dir = st.session_state.record_save_dir.strip() or DEFAULT_RECORD_SAVE_DIR
    target_url = st.session_state.record_target_url.strip()
    proceed_disabled = not target_url

    pspacer1, pcol1, pcol2, pspacer2 = st.columns([1, 1, 1, 1])
    with pcol1:
        if st.button("Proceed", type="primary", disabled=proceed_disabled, use_container_width=True):
            recorder_qs = urlencode({"save_dir": save_dir, "target_url": target_url})
            # Open the target page first, then the recorder panel last, so
            # the recorder ends up as the focused/visible tab or window -
            # opening two windows back-to-back otherwise tends to leave
            # only the LAST one focused, hiding whichever opened first.
            webbrowser.open(target_url, new=1)
            time.sleep(0.6)
            webbrowser.open(f"http://localhost:{RECORDER_PORT}/recorder?{recorder_qs}", new=1)
            st.session_state.show_record_dialog = False
            st.rerun()
    with pcol2:
        if st.button("Cancel", use_container_width=True):
            st.session_state.show_record_dialog = False
            st.rerun()


if input_mode == "Video Upload":
    col_upload, col_record = st.columns([4, 1])
    with col_upload:
        video_file = st.file_uploader(
            "Workflow screen recording", type=["mp4", "mov", "avi", "mkv", "webm"]
        )
    with col_record:
        st.markdown(
            "<div style='text-align:center; color:#64748B; font-size:0.8rem; "
            "margin-bottom:0.3rem;'>or</div>",
            unsafe_allow_html=True,
        )
        if st.button("\U0001F534 Record", use_container_width=True):
            st.session_state.show_record_dialog = True

    if st.session_state.show_record_dialog:
        record_dialog()

    @st.fragment(run_every="2s")
    def _poll_for_recording():
        # Never rerun the app out from under an in-progress generation - the
        # blocking Claude Code subprocess runs on the main script thread, so
        # a rerun triggered here (a separate, timer-driven request) would
        # tear down that run before it ever reaches its success/download UI.
        # The grace period after generation finishes covers it too: the
        # success/download UI was just rendered by that same run, and needs
        # a moment to actually be seen before anything reruns the page out
        # from under it.
        if st.session_state.get("_generating"):
            return
        if time.time() - st.session_state.get("_generation_done_at", 0) < 15:
            return
        pointer_path = recorder_server.LAST_SAVED_POINTER
        current = pointer_path.read_text(encoding="utf-8").strip() if pointer_path.exists() else None
        if current != st.session_state.get("_last_seen_recording"):
            st.session_state._last_seen_recording = current
            st.rerun()

    _poll_for_recording()

    pointer_path = recorder_server.LAST_SAVED_POINTER
    if video_file is None and pointer_path.exists():
        candidate = Path(pointer_path.read_text(encoding="utf-8").strip())
        if candidate.exists():
            size_mb = candidate.stat().st_size / (1024 * 1024)
            info_col, discard_col = st.columns([4, 1])
            with info_col:
                st.success(
                    f"\U0001F3A5 Recorded video ready: {candidate.name} "
                    f"({size_mb:.1f} MB) in {candidate.parent} - it will be "
                    "used since no file is uploaded above."
                )
            with discard_col:
                if st.button("Discard"):
                    pointer_path.unlink(missing_ok=True)
                    st.session_state._last_seen_recording = None
                    st.rerun()
            recorded_video_path = candidate

    max_frames = st.slider(
        "Max video frames to analyze", min_value=5, max_value=40, value=15,
        help="More frames capture more detail but take longer and use more context.",
    )
else:
    manual_step_guide = st.text_area(
        "Manual Step Guide",
        placeholder=(
            "Navigate to facebook page\n"
            "Click on Login without giving credentials\n"
            "Validate the error message"
        ),
        height=120,
        help="Claude will actually perform these steps itself in a real browser "
             "and capture screenshots as evidence.",
    )
    headless = st.radio(
        "Browser mode",
        options=["Headless (invisible, faster)", "Headed (visible browser window)"],
        horizontal=True,
        help="Headed mode opens a real, visible browser window so you can watch "
             "the automation happen - useful to confirm the flow is correct.",
    ) == "Headless (invisible, faster)"

additional_guidelines = st.text_area(
    "Additional guidelines (optional)",
    placeholder="e.g. Also cover mobile viewport sizes, or focus on validation messages",
    height=80,
    help="Applied on top of whichever workflow source you chose above (video or "
         "manual step guide).",
)

scope = st.radio(
    "Test case scope",
    options=["functional_only", "functional_plus_edge"],
    format_func=lambda v: {
        "functional_only": "Step-by-step functional test cases",
        "functional_plus_edge": "Functional + edge/negative test cases",
    }[v],
)

st.divider()
st.markdown("#### \U0001F4BE Step 3 - Save location")

if "output_folder" not in st.session_state:
    st.session_state.output_folder = ""


def _browse_output_folder():
    folder = pick_folder()
    if folder:
        st.session_state.output_folder = folder


output_folder = st.text_input(
    "Folder to save the completed test case document",
    placeholder=r"C:\Users\you\Documents\TestCases",
    key="output_folder",
)
st.button("Browse...", key="output_folder_browse_btn", on_click=_browse_output_folder)

has_video_source = video_file is not None or recorded_video_path is not None
has_workflow_source = (
    (input_mode == "Video Upload" and has_video_source)
    or (input_mode == "Manual Step Guide" and bool(manual_step_guide.strip()))
)
generate = st.button(
    "Generate", type="primary", disabled=not has_workflow_source or not output_folder
)
if not has_workflow_source:
    st.caption(
        "Upload or record a video, or fill in the Manual Step Guide, before generating."
    )

if generate:
    # Guards _poll_for_recording (above) from rerunning the app out from
    # under this in-progress, long-running generation - see the comment
    # there. Always reset in `finally`, including on every early st.stop().
    st.session_state["_generating"] = True
    try:
        out_dir = Path(output_folder)
        if not out_dir.exists():
            st.error(f"Output folder does not exist: {out_dir}")
            st.stop()

        run_id = time.strftime("%Y%m%d_%H%M%S")
        run_dir = RUNS_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        template_path = None
        if template_file is not None:
            template_path = run_dir / template_file.name
            template_path.write_bytes(template_file.getvalue())

        safe_jira = (jira_id or "NoJira").strip().replace(" ", "_").replace("/", "-")
        output_name = f"TestCases_{safe_jira}_{run_id}.docx"
        output_path = out_dir / output_name

        progress_bar = st.progress(0, text="Starting...")
        status_area = st.empty()

        frames_dir = None
        screenshots_dir = None
        add_dirs = [out_dir]
        mcp_config = None
        mode = "video" if input_mode == "Video Upload" else "manual"

        if mode == "video":
            if video_file is not None:
                video_path = run_dir / video_file.name
                video_path.write_bytes(video_file.getvalue())
            else:
                # Recorded video already lives at the user's chosen location -
                # use it directly in place, don't copy or delete it.
                video_path = recorded_video_path
                recorder_server.LAST_SAVED_POINTER.unlink(missing_ok=True)
                # Sync the poll fragment's tracked state to match right now,
                # so it doesn't notice this pointer-file deletion as a
                # "change" a couple seconds from now and rerun the app out
                # from under the success/download UI we're about to show.
                st.session_state["_last_seen_recording"] = None
            frames_dir = run_dir / "frames"

            status_area.write("Extracting frames from the video...")
            try:
                frames = extract_frames(str(video_path), frames_dir, max_frames=max_frames)
            except Exception as e:
                progress_bar.progress(100, text="Frame extraction failed")
                st.exception(e)
                st.stop()
            status_area.write(f"Extracted {len(frames)} frame(s).")
            add_dirs.append(frames_dir)
        else:
            status_area.write(
                "Claude will execute your manual step guide itself in a "
                f"{'headless' if headless else 'headed (visible)'} browser and "
                "capture screenshots as evidence."
            )
            screenshots_dir = run_dir / "screenshots"
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            add_dirs.append(screenshots_dir)
            mcp_config = write_mcp_config(run_dir, headless=headless)

        if template_path is not None:
            add_dirs.append(template_path.parent)

        prompt = build_prompt(
            jira_id, template_path, mode, frames_dir, manual_step_guide,
            additional_guidelines, scope, output_path, screenshots_dir,
        )

        estimated_seconds = 240 if mode == "manual" else 150

        def on_tick(elapsed: float) -> None:
            pct = min(int(elapsed / estimated_seconds * 90), 90)
            progress_bar.progress(
                pct, text=f"Claude Code is working... ({int(elapsed)}s elapsed)"
            )

        try:
            result = run_claude_streaming(
                prompt, work_dir=run_dir, add_dirs=add_dirs, on_tick=on_tick,
                mcp_config=mcp_config,
            )
        except subprocess.TimeoutExpired:
            progress_bar.progress(100, text="Timed out")
            st.error("Claude took too long and timed out.")
            st.stop()
        except FileNotFoundError as e:
            progress_bar.progress(100, text="'claude' CLI not found")
            st.error(f"Could not find/run the `claude` command.\n\n{e}")
            st.stop()

        if result.returncode != 0 or not output_path.exists():
            progress_bar.progress(100, text="Generation failed")
            st.error("Claude did not produce the output file.")
            with st.expander("Claude output (for troubleshooting)"):
                st.code(result.stdout or "(no stdout)")
                st.code(result.stderr or "(no stderr)")
            st.stop()

        progress_bar.progress(100, text="Done")
        status_area.empty()

        st.success(f"Test case document saved to: {output_path}")
        with open(output_path, "rb") as f:
            st.download_button(
                "Download the generated document",
                data=f.read(),
                file_name=output_path.name,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        with st.expander("Claude's run log"):
            st.code(result.stdout or "(no stdout)")
    finally:
        st.session_state["_generating"] = False
        st.session_state["_generation_done_at"] = time.time()
