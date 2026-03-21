import subprocess
import json
import os
import sys
import queue
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import shutil

import pyaudio

# ── Config ──────────────────────────────────────────────────────
DEFAULT_LANG = "en"
DEFAULT_PORT = 5001
DEFAULT_SENTENCE_SILENCE = 0.0  # seconds pause between sentences (set to 0 to disable)

PIPER_DIR = os.path.dirname(shutil.which("piper"))

# lang code -> model filename (add more as you download them)
MODELS = {
    "ka":         "ka_GE-natia-medium.onnx",
    "en":         "cori-high.onnx",
    "jenny":      "en_GB-jenny_dioco-medium.onnx",
    "amy":        "en_US-amy-medium.onnx",
    "cori":       "cori-high.onnx",
}
# ────────────────────────────────────────────────────────────────

_pa = pyaudio.PyAudio()
_sample_rate_cache: dict[str, int] = {}


def get_sample_rate(config_path: str) -> int:
    if config_path not in _sample_rate_cache:
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                _sample_rate_cache[config_path] = json.load(f)["audio"]["sample_rate"]
        except (FileNotFoundError, KeyError):
            _sample_rate_cache[config_path] = 22050  # piper default
    return _sample_rate_cache[config_path]


def resolve_model(lang: str = None, model: str = None) -> tuple[str, str]:
    """Return (model_path, error_message). One of them will be None."""
    if model:
        model_path = model
    else:
        lang = lang or DEFAULT_LANG
        if lang not in MODELS:
            return None, f"Unknown language '{lang}'. Available: {', '.join(MODELS)}"
        model_path = MODELS[lang]

    if not os.path.exists(os.path.join(PIPER_DIR, model_path)):
        return None, f"Model not found: {model_path}"

    return model_path, None


def speak(text: str, lang: str = None, model: str = None) -> str | None:
    """Speak text. Returns error string on failure, None on success."""
    model_path, err = resolve_model(lang, model)
    if err:
        return err

    sample_rate = get_sample_rate(os.path.join(PIPER_DIR, model_path + ".json"))

    try:
        proc = subprocess.Popen(
            ["piper", "--model", model_path, "--output_raw",
             "--sentence-silence", str(DEFAULT_SENTENCE_SILENCE)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=PIPER_DIR,
        )
    except FileNotFoundError:
        return "Piper not found. Make sure piper.exe is in PATH."

    proc.stdin.write(text.encode("utf-8"))
    proc.stdin.close()

    stream = _pa.open(format=pyaudio.paInt16, channels=1, rate=sample_rate, output=True)
    try:
        while chunk := proc.stdout.read(4096):
            stream.write(chunk)
    finally:
        stream.stop_stream()
        stream.close()
        proc.wait()

    return None


# ── HTTP Server ──────────────────────────────────────────────────

_speak_queue: queue.Queue = queue.Queue()


def _worker():
    while True:
        text, lang, model, result_q = _speak_queue.get()
        result_q.put(speak(text, lang, model))


class SpeakHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_POST(self):
        if self.path != "/speak":
            self._respond(404, "Not found")
            return

        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            self._respond(400, "Invalid JSON")
            return

        text = body.get("text", "").strip()
        print(f"[speak] {text!r}")
        if not text:
            self._respond(400, "'text' is required")
            return

        lang = body.get("lang")
        model = body.get("model")

        _, err = resolve_model(lang, model)
        if err:
            self._respond(400, err)
            return

        result_q: queue.Queue = queue.Queue(1)
        _speak_queue.put((text, lang, model, result_q))
        err = result_q.get()

        self._respond(500 if err else 200, err or "OK")

    def _respond(self, code, message):
        body = message.encode()
        try:
            self.send_response(code)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)
        except (ConnectionAbortedError, BrokenPipeError):
            pass


def run_server(port: int):
    threading.Thread(target=_worker, daemon=True).start()
    server = HTTPServer(("", port), SpeakHandler)
    print(f"[server] Listening on http://localhost:{port}/speak")
    print(f"[server] Default lang: {DEFAULT_LANG} ({MODELS[DEFAULT_LANG]})")
    print(f"[server] POST {{\"text\": \"Hello\", \"lang\": \"en\"}}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[server] Stopped.")


# ── Entry point ──────────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]

    if args and args[0] == "--server":
        port = DEFAULT_PORT
        if "--port" in args:
            idx = args.index("--port")
            if idx + 1 >= len(args):
                print("Error: --port requires a value")
                sys.exit(1)
            port = int(args[idx + 1])
        run_server(port)
    elif len(args) >= 2:
        err = speak(" ".join(args[1:]), lang=args[0])
        if err:
            print(err)
            sys.exit(1)
    else:
        print("Usage:")
        print("  python speak.py <lang> <text>          # speak directly")
        print("  python speak.py --server               # start HTTP server")
        print("  python speak.py --server --port 5001")
        print(f"Languages: {', '.join(MODELS)}")
        sys.exit(1)
