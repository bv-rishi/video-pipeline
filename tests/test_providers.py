from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from video_pipeline.modules.draft_review.config import DraftReviewSettings, ReviewAgentSettings
from video_pipeline.modules.draft_review.providers import (
    ClaudeCodeProvider,
    OpenAICompatibleProvider,
    ProviderError,
    make_provider,
    parse_issues,
)


class ProviderTests(unittest.TestCase):
    def test_parses_fenced_json(self):
        payload = '''```json
{"issues":[{"timestamp_sec":32,"title":"Zoom in","problem":"Text is small","fix":"Crop closer","severity":"required","category":"visual","confidence":0.9,"evidence_frame":"frame_000017.jpg"}]}
```'''
        issues = parse_issues(payload)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].timestamp_sec, 32)
        self.assertEqual(issues[0].severity, "required")

    def test_invalid_json_raises(self):
        with self.assertRaises(ProviderError):
            parse_issues("not json")

    def test_openai_compatible_payload_and_cache(self):
        received = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                return

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                received.append(body)
                answer = json.dumps({"issues": [{
                    "timestamp_sec": 12, "title": "Show the setting", "problem": "The setting is hidden",
                    "fix": "Move the presenter", "severity": "required", "category": "visual",
                    "confidence": 0.9, "evidence_frame": "frame.jpg",
                }]})
                payload = json.dumps({"model": "compatible-test", "choices": [{"message": {"content": answer}}],
                                      "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                image = root / "frame.jpg"
                image.write_bytes(b"safe fixture")
                settings = DraftReviewSettings(agent=ReviewAgentSettings(
                    api_base_url=f"http://127.0.0.1:{server.server_port}/v4",
                    api_key="test-key", api_model="compatible-test", max_retries=0,
                ))
                provider = OpenAICompatibleProvider(settings)
                issues, usage = provider.review("system", "prompt", [image], root / "cache.json")
                cached_issues, cached_usage = provider.review("system", "prompt", [image], root / "cache.json")
                self.assertEqual(len(issues), 1)
                self.assertEqual(len(cached_issues), 1)
                self.assertEqual(usage["total_tokens"], 15)
                self.assertTrue(cached_usage["cached"])
                self.assertEqual(len(received), 1)
                content = received[0]["messages"][1]["content"]
                self.assertEqual(content[1]["type"], "image_url")
        finally:
            server.shutdown()
            server.server_close()

    def test_claude_code_uses_existing_route_with_read_only_images(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "frame 001.jpg"
            image.write_bytes(b"safe fixture")
            response = {
                "is_error": False,
                "structured_output": {"issues": [{
                    "timestamp_sec": 18,
                    "end_sec": None,
                    "title": "Zoom into the setting",
                    "problem": "The setting is too small to read.",
                    "fix": "Crop closer and highlight it.",
                    "severity": "required",
                    "category": "visual",
                    "confidence": 0.92,
                    "evidence_frame": image.name,
                }]},
                "usage": {"input_tokens": 20, "output_tokens": 10},
            }
            completed = __import__("subprocess").CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(response), stderr=""
            )
            settings = DraftReviewSettings(agent=ReviewAgentSettings(
                claude_code_command="claude",
                claude_code_model="sonnet",
                claude_code_max_budget_usd=0.05,
            ))
            with patch("video_pipeline.modules.draft_review.providers.shutil.which", return_value="/usr/local/bin/claude"), \
                    patch("video_pipeline.modules.draft_review.providers.subprocess.run", return_value=completed) as run:
                provider = ClaudeCodeProvider(settings)
                issues, usage = provider.review("system", "prompt", [image], root / "cache.json")

            self.assertEqual(len(issues), 1)
            self.assertEqual(usage["total_tokens"], 30)
            args = run.call_args.args[0]
            self.assertIn("--no-session-persistence", args)
            self.assertIn("--max-budget-usd", args)
            self.assertEqual(args[args.index("--tools") + 1], "Read")
            self.assertEqual(args[args.index("--allowedTools") + 1], "Read")
            self.assertIn(str(image.resolve()), run.call_args.kwargs["input"])
            self.assertNotIn(str(image.resolve()), " ".join(args))

    def test_claude_code_text_only_disables_all_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            completed = __import__("subprocess").CompletedProcess(
                args=[], returncode=0, stdout=json.dumps({"structured_output": {"issues": []}}), stderr=""
            )
            settings = DraftReviewSettings()
            with patch("video_pipeline.modules.draft_review.providers.shutil.which", return_value="/usr/local/bin/claude"), \
                    patch("video_pipeline.modules.draft_review.providers.subprocess.run", return_value=completed) as run:
                provider = ClaudeCodeProvider(settings, text_only=True)
                provider.review("system", "prompt", [], root / "cache.json")
            args = run.call_args.args[0]
            self.assertEqual(args[args.index("--tools") + 1], "")
            self.assertNotIn("--allowedTools", args)

    def test_auto_prefers_existing_claude_code_setup(self):
        settings = DraftReviewSettings(agent=ReviewAgentSettings(api_key="also-configured"))
        with patch("video_pipeline.modules.draft_review.providers.shutil.which", return_value="/usr/local/bin/claude"):
            provider = make_provider("auto", settings)
        self.assertIsInstance(provider, ClaudeCodeProvider)


if __name__ == "__main__":
    unittest.main()
