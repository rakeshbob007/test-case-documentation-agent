"""Core pipeline: extract video frames (or drive a live browser from a manual
step guide), build the Claude prompt, and run the headless Claude Code CLI to
produce the filled-in test case Word document."""

import getpass
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import imageio_ffmpeg


def write_startup_diagnostics() -> None:
    """Dump environment info to a log file at import time, so we can see
    exactly what this running process's environment looks like without
    needing to trigger the full generate flow."""
    lines = [
        f"module file: {__file__}",
        f"sys.executable: {sys.executable}",
        f"user: {getpass.getuser()!r}",
        f"cwd: {os.getcwd()!r}",
        f"APPDATA: {os.environ.get('APPDATA')!r}",
        f"USERPROFILE: {os.environ.get('USERPROFILE')!r}",
        f"shutil.which('claude'): {shutil.which('claude')!r}",
    ]
    log_path = Path(__file__).parent / "claude_debug.log"
    log_path.write_text("\n".join(lines), encoding="utf-8")


write_startup_diagnostics()


def candidate_claude_executables() -> list[str]:
    """Return every plausible path to the claude CLI, in priority order."""
    candidates = []
    # Native binary: a real .exe, so no cmd.exe/.bat shell parsing is
    # involved at all (project paths on this machine contain '&', which
    # breaks .cmd/.bat shim scripts - see candidates below).
    native_exe = Path(__file__).parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    candidates.append(str(native_exe))
    local_bin = Path(__file__).parent / "node_modules" / ".bin"
    for name in ("claude.cmd", "claude.CMD", "claude.ps1"):
        candidates.append(str(local_bin / name))
    exe = shutil.which("claude")
    if exe:
        candidates.append(exe)
    appdata = os.environ.get("APPDATA")
    if appdata:
        for name in ("claude.cmd", "claude.CMD", "claude.ps1"):
            candidates.append(str(Path(appdata) / "npm" / name))
    seen = set()
    ordered = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    return ordered


def get_video_duration(ffmpeg_exe: str, video_path: str) -> float:
    result = subprocess.run(
        [ffmpeg_exe, "-i", video_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", result.stderr)
    if not match:
        return 60.0
    h, m, s = match.groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def extract_frames(video_path: str, out_dir: Path, max_frames: int = 15) -> list[Path]:
    """Sample up to max_frames evenly-spaced frames from the video as jpgs."""
    out_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    duration = get_video_duration(ffmpeg_exe, video_path)
    interval = max(1.0, duration / max_frames)
    fps = 1.0 / interval
    pattern = str(out_dir / "frame_%03d.jpg")
    subprocess.run(
        [ffmpeg_exe, "-y", "-i", video_path, "-vf", f"fps={fps}", "-q:v", "3", pattern],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return sorted(out_dir.glob("frame_*.jpg"))[:max_frames]


def write_mcp_config(run_dir: Path, headless: bool) -> Path:
    """Write a per-run MCP config enabling the Playwright browser tools,
    in headed or headless mode as chosen by the user."""
    args = ["-y", "@playwright/mcp@latest"]
    if headless:
        args.append("--headless")
    config = {"mcpServers": {"playwright": {"command": "npx", "args": args}}}
    path = run_dir / "mcp_config.json"
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return path


def build_prompt(
    jira_id: str | None,
    template_path: Path | None,
    mode: str,  # "video" or "manual"
    frames_dir: Path | None,
    manual_step_guide: str | None,
    additional_guidelines: str | None,
    scope: str,
    output_path: Path,
    screenshots_dir: Path | None,
) -> str:
    lines = [
        "You are generating a QA test case Word document describing an "
        "application workflow. Work autonomously end to end and do not ask "
        "the user any clarifying questions - make reasonable assumptions.",
        "",
    ]

    if mode == "video":
        lines += [
            f"Step 1: Read every image file in this folder, in filename order, to "
            f"understand the workflow shown: {frames_dir}",
            "",
        ]
        evidence_dir = frames_dir
        workflow_ref = "frames"
    else:
        lines += [
            "Step 1: Actually PERFORM these manual steps yourself using your "
            "browser automation tool (the playwright MCP browser tools) - do "
            "not just reason about them:",
            "---",
            (manual_step_guide or "").strip(),
            "---",
            "Navigate and interact with the real site exactly as described. "
            "After each meaningful step (page load, click, form submission, "
            "validation, error shown, etc.):",
            "  a) Before capturing the screenshot, visually highlight the "
            "specific element that step is about (the button just clicked, "
            "the field just filled, the error/message just shown) by running "
            "JavaScript via your browser tool's evaluate capability to add a "
            "prominent style to it, e.g. a thick colored outline/border "
            "(such as `el.style.outline = '3px solid red'; "
            "el.style.outlineOffset = '2px';`) or a similar clearly visible "
            "highlight. Do this for every screenshot, not just some.",
            "  b) Then take the screenshot with that highlight applied and "
            f"save it as a PNG file into this folder: {screenshots_dir}. Use "
            "clear, ordered filenames (e.g. step1_navigate.png, "
            "step2_click_login.png, step3_error_message.png) so you can tell "
            "which screenshot belongs to which step afterwards.",
            "",
        ]
        evidence_dir = screenshots_dir
        workflow_ref = "instructions you executed"

    if additional_guidelines and additional_guidelines.strip():
        lines += [
            "Additional guidelines to incorporate throughout (apply these "
            f"regardless of the source above): {additional_guidelines.strip()}",
            "",
        ]

    if template_path is not None:
        lines += [
            f"Step 2: Open the reference Word template at: {template_path}",
            "Replicate its exact structure, column headers, and formatting style. "
            "Only populate/replace the content rows with the new test cases you "
            "generate - do not change the template's layout or headings.",
            "",
        ]
    else:
        lines += [
            "Step 2: No reference template was provided. Create a clean, standard "
            "test case table with these columns: Test Case ID, Title, "
            "Preconditions, Test Steps, Test Data, Expected Result, Priority.",
            "",
        ]

    if jira_id:
        lines += [
            f"Step 3: The relevant JIRA reference is '{jira_id}'. Include it as a "
            "label in the document (e.g. a header/title line and/or an ID prefix "
            "for each test case). Do not attempt to fetch anything from JIRA.",
            "",
        ]

    if scope == "functional_plus_edge":
        step4 = (
            f"Step 4: Write clear, step-by-step functional test cases covering the "
            f"exact workflow shown in the {workflow_ref}, PLUS additional reasonable "
            "edge-case and negative test cases (invalid input, boundary values, "
            "error states) relevant to that workflow."
        )
    else:
        step4 = (
            f"Step 4: Write clear, step-by-step functional test cases that cover "
            f"exactly the workflow shown in the {workflow_ref}. Do not invent "
            "unrelated edge cases."
        )
    lines += [step4, ""]

    lines += [
        "Step 5: For each test case, embed the single most relevant image from "
        f"{evidence_dir} directly inside that test case's Expected Result table "
        "cell (an inline image plus a short text description) - do not add a "
        "separate image column.",
        "Formatting requirements: before inserting, resize each image to a "
        "maximum width of about 2 inches (preserving aspect ratio) so it fits "
        "neatly inside the cell. Make sure the overall table fits within "
        "standard page margins and never overflows off the page - use "
        "reasonable column widths (narrow the Test Case ID/Priority columns, "
        "give more room to Steps/Expected Result), and switch the page to "
        "landscape orientation if that is what it takes to fit the table "
        "and images cleanly.",
        "",
    ]

    lines += [
        f"Step 6: Use your docx skill to save the final result as a new Word "
        f"document at exactly this path: {output_path}",
    ]

    return "\n".join(lines)


def run_claude_streaming(
    prompt: str,
    work_dir: Path,
    add_dirs: list[Path],
    on_tick,
    timeout: int = 1800,
    mcp_config: Path | None = None,
) -> subprocess.CompletedProcess:
    """Like run_claude, but polls the subprocess so the caller can drive a
    progress indicator. on_tick(elapsed_seconds) is called roughly once a
    second while the process is running."""
    candidates = candidate_claude_executables()
    attempts = []
    for claude_exe in candidates:
        cmd = [claude_exe, "-p", prompt, "--dangerously-skip-permissions"]
        for d in add_dirs:
            cmd += ["--add-dir", str(d)]
        if mcp_config is not None:
            cmd += ["--mcp-config", str(mcp_config)]
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(work_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except FileNotFoundError as e:
            attempts.append(f"{claude_exe!r} -> {e}")
            continue

        start = time.time()
        while True:
            try:
                stdout, stderr = proc.communicate(timeout=1)
                break
            except subprocess.TimeoutExpired:
                elapsed = time.time() - start
                if elapsed > timeout:
                    proc.kill()
                    proc.communicate()
                    raise subprocess.TimeoutExpired(cmd, timeout)
                on_tick(elapsed)
        return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)

    msg = "claude CLI could not be launched. Tried:\n" + "\n".join(attempts) if attempts else (
        "claude CLI not found: no candidate paths were resolvable "
        "(checked PATH and %APPDATA%\\npm)."
    )
    log_path = Path(__file__).parent / "claude_debug.log"
    log_path.write_text(msg, encoding="utf-8")
    raise FileNotFoundError(msg)
