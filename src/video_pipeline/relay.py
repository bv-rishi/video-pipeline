from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import sqlite3
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .util import utc_now


def chat_text(event: dict[str, Any], config: dict[str, Any]) -> str:
    reviewer = config.get("reviewer_user_id")
    editor_id = config.get("editors", {}).get(str(event.get("editor", "")).lower())
    if not reviewer or not editor_id:
        raise ValueError("Reviewer or editor Chat user ID is not configured")
    mentions = f"<users/{reviewer}> <users/{editor_id}>"
    reviewer_label = str(config.get("reviewer_label", "the final reviewer"))
    if event.get("event") == "ready_for_reviewer":
        return (f"{mentions} — {event.get('ready', 0)} of {event.get('total', 0)} videos in "
                f"batch {event.get('batch_id')} are ready for {reviewer_label}. The editor confirmed the review changes were completed.")
    checked = int(event.get("checked", 0))
    total = int(event.get("total", 0))
    failed = int(event.get("failed", 0))
    if failed:
        return (f"{mentions} — Batch {event.get('batch_id')} finished with attention needed: "
                f"{checked} of {total} checked, {failed} failed. No failed video is marked ready.")
    return (f"{mentions} — Review completed for {checked} of {total} videos in batch "
            f"{event.get('batch_id')}. The editor can now make the requested changes.")


def post_chat(webhook: str, text: str) -> None:
    request = Request(webhook, data=json.dumps({"text": text}).encode("utf-8"), method="POST",
                      headers={"Content-Type": "application/json; charset=UTF-8"})
    with urlopen(request, timeout=20) as response:
        response.read()


def make_handler(db_path: Path, config: dict[str, Any], tokens: dict[str, str], webhook: str):
    class RelayHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def _reply(self, code: int, payload: dict[str, Any]) -> None:
            data = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            if self.path == "/health":
                self._reply(200, {"status": "ok"})
            else:
                self._reply(404, {"error": "not found"})

        def do_POST(self) -> None:
            if self.path != "/events":
                self._reply(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 32_768:
                    raise ValueError("invalid content length")
                event = json.loads(self.rfile.read(length))
                allowed = {"event_id", "event", "batch_id", "editor", "total", "checked", "failed", "ready", "sent_at"}
                event = {key: event[key] for key in allowed if key in event}
                required = {"event_id", "event", "batch_id", "editor", "total", "checked", "failed", "ready"}
                if not required.issubset(event):
                    raise ValueError("missing event fields")
                if event["event"] not in {"review_complete", "ready_for_reviewer"}:
                    raise ValueError("invalid event type")
                supplied = self.headers.get("Authorization", "").removeprefix("Bearer ")
                expected = tokens.get(str(event["editor"]).lower(), tokens.get("*", ""))
                if not expected or not secrets.compare_digest(supplied, expected):
                    self._reply(401, {"error": "unauthorized"})
                    return
                with sqlite3.connect(db_path) as connection:
                    connection.execute("CREATE TABLE IF NOT EXISTS events (event_id TEXT PRIMARY KEY, payload TEXT, received_at TEXT, delivered_at TEXT)")
                    connection.execute("INSERT OR IGNORE INTO events(event_id,payload,received_at) VALUES(?,?,?)",
                                       (event["event_id"], json.dumps(event), utc_now()))
                    row = connection.execute("SELECT delivered_at FROM events WHERE event_id=?",
                                             (event["event_id"],)).fetchone()
                    connection.commit()
                    if row and row[0]:
                        self._reply(200, {"status": "duplicate", "event_id": event["event_id"]})
                        return
                message = chat_text(event, config)
                post_chat(webhook, message)
                with sqlite3.connect(db_path) as connection:
                    connection.execute("UPDATE events SET delivered_at=? WHERE event_id=?", (utc_now(), event["event_id"]))
                    connection.commit()
                self._reply(200, {"status": "delivered", "event_id": event["event_id"]})
            except (ValueError, json.JSONDecodeError) as error:
                self._reply(400, {"error": str(error)})
            except (HTTPError, URLError, TimeoutError) as error:
                self._reply(502, {"error": f"Google Chat delivery failed: {error}"})

    return RelayHandler


def serve(host: str, port: int, db_path: Path, config_path: Path) -> None:
    token = os.environ.get("VIDEO_PIPELINE_RELAY_TOKEN", "")
    token_json = os.environ.get("VIDEO_PIPELINE_RELAY_TOKENS_JSON", "")
    webhook = os.environ.get("VIDEO_PIPELINE_CHAT_WEBHOOK_URL", "")
    if not (token or token_json) or not webhook:
        raise RuntimeError("Relay editor tokens and VIDEO_PIPELINE_CHAT_WEBHOOK_URL are required")
    tokens = json.loads(token_json) if token_json else {"*": token}
    if not isinstance(tokens, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in tokens.items()):
        raise RuntimeError("VIDEO_PIPELINE_RELAY_TOKENS_JSON must be a JSON object of editor names to tokens")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((host, port), make_handler(db_path, config, tokens, webhook))
    print(f"Notification relay listening on http://{host}:{port}")
    server.serve_forever()
