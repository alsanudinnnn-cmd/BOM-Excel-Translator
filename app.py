"""Local web launcher for the portable Excel Translator application."""

from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.serving import BaseWSGIServer, make_server
from werkzeug.utils import secure_filename

from translator import ALLOWED_EXTENSIONS, estimate_workbook_characters, translate_workbook
from usage_tracker import MONTHLY_LIMIT, get_usage, next_reset_date


RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
APP_MARKER = "excel-translator-local-v1"
DEFAULT_PORT = 51243
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

app = Flask(
    __name__,
    template_folder=str(RESOURCE_DIR / "templates"),
    static_folder=str(RESOURCE_DIR / "assets"),
    static_url_path="/assets",
)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
server: BaseWSGIServer | None = None
last_heartbeat = time.monotonic()

LANGUAGES = (
    ("Arabic", "ar"), ("Chinese — Simplified", "zh-Hans"),
    ("Chinese — Traditional", "zh-Hant"), ("Dutch", "nl"), ("English", "en"),
    ("French", "fr"), ("German", "de"), ("Hindi", "hi"), ("Indonesian", "id"),
    ("Italian", "it"), ("Japanese", "ja"), ("Korean", "ko"), ("Malay", "ms"),
    ("Portuguese", "pt"), ("Russian", "ru"), ("Spanish", "es"), ("Tamil", "ta"),
    ("Thai", "th"), ("Turkish", "tr"), ("Vietnamese", "vi"),
)


def usage_payload() -> dict[str, int | str]:
    used = get_usage()
    return {
        "used": used,
        "limit": MONTHLY_LIMIT,
        "remaining": max(0, MONTHLY_LIMIT - used),
        "reset": next_reset_date().strftime("%d %b %Y").lstrip("0"),
    }


def save_upload(upload) -> Path:
    filename = secure_filename(upload.filename or "")
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("Choose a valid .xlsx or .xls workbook.")
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary:
        upload.save(temporary)
        return Path(temporary.name)


def friendly_error(message: str) -> str:
    lowered = message.lower()
    if "401" in lowered or "credentials" in lowered or "unauthorized" in lowered:
        return "Azure rejected the credentials. Check the key and region in the .env file."
    if "target language" in lowered:
        return "Azure rejected the selected language. Choose another target and try again."
    if "timed out" in lowered or "connection" in lowered:
        return "Could not reach Azure. Check your internet connection and try again."
    return "Check the workbook and Azure settings, then try again."


@app.after_request
def secure_local_response(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'"
    )
    return response


@app.get("/")
def index():
    return render_template(
        "index.html", languages=LANGUAGES, azure_ready=bool(os.getenv("AZURE_TRANSLATOR_KEY"))
    )


@app.get("/api/health")
def health():
    return jsonify({"app": APP_MARKER})


@app.get("/api/usage")
def usage():
    return jsonify(usage_payload())


@app.post("/api/heartbeat")
def heartbeat():
    global last_heartbeat
    last_heartbeat = time.monotonic()
    return ("", 204)


@app.post("/api/estimate")
def estimate():
    upload = request.files.get("workbook")
    if upload is None or not upload.filename:
        return jsonify({"error": "Choose an Excel workbook first."}), 400
    temporary: Path | None = None
    try:
        temporary = save_upload(upload)
        return jsonify({"characters": estimate_workbook_characters(temporary), **usage_payload()})
    except Exception as error:
        return jsonify({"error": str(error)}), 400
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@app.post("/translate")
def translate():
    upload = request.files.get("workbook")
    if upload is None or not upload.filename:
        return jsonify({"error": "Choose an Excel workbook first."}), 400

    target = request.form.get("target", "").strip()
    source = request.form.get("source", "").strip() or None
    valid_codes = {code for _, code in LANGUAGES}
    if target not in valid_codes or (source is not None and source not in valid_codes):
        return jsonify({"error": "Choose valid source and target languages."}), 400

    input_path: Path | None = None
    output_path: Path | None = None
    try:
        input_path = save_upload(upload)
        original_stem = Path(secure_filename(upload.filename)).stem or "workbook"
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as temporary:
            output_path = Path(temporary.name)
        translate_workbook(input_path, target, source, output_path=output_path)
        response = send_file(
            output_path,
            as_attachment=True,
            download_name=f"{original_stem}_{target}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        current = usage_payload()
        response.headers["X-Usage-Used"] = str(current["used"])
        response.headers["X-Usage-Remaining"] = str(current["remaining"])
        response.call_on_close(lambda: output_path.unlink(missing_ok=True))
        return response
    except Exception as error:
        if output_path is not None:
            output_path.unlink(missing_ok=True)
        return jsonify({"error": friendly_error(str(error)), "detail": str(error)}), 500
    finally:
        if input_path is not None:
            input_path.unlink(missing_ok=True)


@app.post("/api/shutdown")
def shutdown():
    if server is not None:
        threading.Timer(0.25, server.shutdown).start()
    return jsonify({"closing": True})


@app.errorhandler(413)
def upload_too_large(_error):
    return jsonify({"error": "Workbook is larger than the 50 MB limit."}), 413


def existing_server_url() -> str | None:
    url = f"http://127.0.0.1:{DEFAULT_PORT}"
    try:
        with urllib.request.urlopen(f"{url}/api/health", timeout=0.8) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return url if payload.get("app") == APP_MARKER else None
    except Exception:
        return None


def idle_watchdog() -> None:
    while server is not None:
        time.sleep(30)
        if time.monotonic() - last_heartbeat > 300:
            server.shutdown()
            return


def run() -> None:
    global server, last_heartbeat
    existing = existing_server_url()
    if existing:
        if not os.getenv("EXCEL_TRANSLATOR_NO_BROWSER"):
            webbrowser.open(existing)
        return

    try:
        server = make_server("127.0.0.1", DEFAULT_PORT, app, threaded=True)
    except OSError:
        with socket.socket() as available:
            available.bind(("127.0.0.1", 0))
            port = available.getsockname()[1]
        server = make_server("127.0.0.1", port, app, threaded=True)
    port = server.server_port
    last_heartbeat = time.monotonic()
    threading.Thread(target=idle_watchdog, daemon=True).start()
    if not os.getenv("EXCEL_TRANSLATOR_NO_BROWSER"):
        threading.Timer(0.8, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    server.serve_forever()


if __name__ == "__main__":
    run()
