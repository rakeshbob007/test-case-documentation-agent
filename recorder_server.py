"""Tiny local HTTP server that serves the screen-recorder page and accepts
the recorded video upload, so app.py can pick the file up afterwards.
Streamlit's file_uploader widget can't be filled programmatically, so this
runs as a separate small server the recorder page talks to directly."""

import http.server
import socketserver
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PORT = 8765
RECORDER_HTML = Path(__file__).parent / "recorder.html"
DEFAULT_RECORDINGS_DIR = Path(__file__).parent / ".runs" / "recordings"
RECORDING_PATH = DEFAULT_RECORDINGS_DIR / "latest_recording.webm"
LAST_SAVED_POINTER = DEFAULT_RECORDINGS_DIR / "last_saved_path.txt"


class RecorderHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # keep the terminal quiet

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/recorder"):
            html = RECORDER_HTML.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/upload":
            query = parse_qs(parsed.query)
            save_dir = (query.get("save_dir") or [""])[0].strip()

            length = int(self.headers.get("Content-Length", 0))
            data = self.rfile.read(length)

            target_dir = Path(save_dir) if save_dir and Path(save_dir).is_dir() else DEFAULT_RECORDINGS_DIR
            target_dir.mkdir(parents=True, exist_ok=True)
            filename = f"recording_{time.strftime('%Y%m%d_%H%M%S')}.webm"
            saved_path = target_dir / filename
            saved_path.write_bytes(data)

            DEFAULT_RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
            LAST_SAVED_POINTER.write_text(str(saved_path), encoding="utf-8")

            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(str(saved_path).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


class ReusableServer(socketserver.ThreadingTCPServer):
    # Without this, Windows can refuse to rebind this exact port for a
    # while after a previous process holding it exits (TIME_WAIT), which
    # otherwise crashes app startup with "address already in use".
    allow_reuse_address = True
    daemon_threads = True


_lock = threading.Lock()
_started = False


def ensure_recorder_server_running() -> int:
    """Start the background recorder server once per process (idempotent -
    safe to call on every Streamlit rerun). Returns the port it listens on."""
    global _started
    with _lock:
        if not _started:
            try:
                httpd = ReusableServer(("127.0.0.1", PORT), RecorderHandler)
            except OSError as e:
                # Most likely another instance of this same app already has
                # it open - don't crash the whole page over it.
                log_path = Path(__file__).parent / "claude_debug.log"
                log_path.write_text(
                    f"recorder_server failed to bind port {PORT}: {e}", encoding="utf-8"
                )
                _started = True
                return PORT
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            _started = True
    return PORT
