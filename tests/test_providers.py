from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest

from video_pipeline.config import Settings
from video_pipeline.providers import OpenAICompatibleProvider, ProviderError, parse_issues


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

    def test_openai_compatible_glm_payload_and_cache(self):
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
                payload = json.dumps({"model": "glm-test", "choices": [{"message": {"content": answer}}],
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
                settings = Settings(glm_base_url=f"http://127.0.0.1:{server.server_port}/v4",
                                    glm_api_key="test-key", glm_model="glm-test", glm_max_retries=0)
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


if __name__ == "__main__":
    unittest.main()
