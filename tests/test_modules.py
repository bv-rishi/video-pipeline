from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from video_pipeline.agent_contract import AgentTask, CommandAgent
from video_pipeline.config import Settings
from video_pipeline.models import ReviewRequest
from video_pipeline.module_registry import list_modules
from video_pipeline.modules.conformer import validate_benchmark_summary
from video_pipeline.modules.draft_review.config import DraftReviewSettings
from video_pipeline.modules.draft_review.engine import run_review
from video_pipeline.modules.draft_review.providers import NoneProvider, make_provider


class ModuleBoundaryTests(unittest.TestCase):
    def test_shared_settings_have_no_model_dependency(self):
        settings = Settings()
        self.assertFalse(hasattr(settings, "glm_model"))
        self.assertFalse(hasattr(settings, "claude_code_model"))

    def test_module_registry_exposes_independent_commands(self):
        modules = {item["name"]: item for item in list_modules()}
        self.assertEqual(modules["draft-review"]["command"], "video-draft-review")
        self.assertEqual(modules["conformer"]["command"], "video-conformer")

    def test_conformer_import_does_not_import_draft_review(self):
        command = [
            sys.executable,
            "-c",
            "import sys; import video_pipeline.modules.conformer; "
            "raise SystemExit('video_pipeline.modules.draft_review' in sys.modules)",
        ]
        result = subprocess.run(command, env={**os.environ, "PYTHONPATH": "src"}, check=False)
        self.assertEqual(result.returncode, 0)

    def test_conformer_summary_contract(self):
        valid = {
            "case_id": "case",
            "retrieval": {},
            "state_contrasts": {},
            "host_audit": {},
            "agent_usage": {"retrieval_run_calls": 0},
        }
        self.assertEqual(validate_benchmark_summary(valid), [])
        self.assertIn("missing required field: host_audit", validate_benchmark_summary({"case_id": "case"}))

    def test_legacy_glm_environment_is_scoped_to_draft_review(self):
        with patch.dict(os.environ, {"VIDEO_PIPELINE_GLM_MODEL": "legacy-model"}, clear=False):
            module_settings = DraftReviewSettings.from_core(Settings())
        self.assertEqual(module_settings.agent.api_model, "legacy-model")
        self.assertFalse(hasattr(Settings(), "glm_model"))

    def test_auto_can_stop_at_no_agent_without_error(self):
        module_settings = DraftReviewSettings()
        with patch("video_pipeline.modules.draft_review.providers.shutil.which", return_value=None):
            provider = make_provider("auto", module_settings)
        self.assertIsInstance(provider, NoneProvider)
        self.assertFalse(provider.semantic_complete)

    def test_generic_command_contract_is_model_agnostic_and_cached(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            command = [
                sys.executable,
                "-c",
                "import json,sys; request=json.load(open(sys.argv[1])); "
                "print(json.dumps({'task': request['task'], 'issues': []}))",
                "{request_file}",
            ]
            agent = CommandAgent(command, model="whatever-the-editor-configured")
            task = AgentTask(
                module="draft-review", task="review-chunk", system_prompt="system",
                prompt="prompt", response_schema={"type": "object"},
            )
            first = agent.run(task, root / "cache.json")
            second = agent.run(task, root / "cache.json")
            self.assertEqual(first.output["task"], "review-chunk")
            self.assertEqual(first.model, "whatever-the-editor-configured")
            self.assertTrue(second.usage["cached"])

    def test_draft_review_none_mode_saves_task_and_needs_attention(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "draft.mp4"
            script = root / "script.txt"
            video.write_bytes(b"fixture")
            script.write_text("Approved words", encoding="utf-8")
            settings = Settings(
                work_dir=root / "work",
                modules={"draft_review": {"agent": {"adapter": "none"}}},
            )
            media = {
                "duration_sec": 10,
                "width": 1920,
                "height": 1080,
                "audio": {"available": True, "integrated_lufs": -16},
                "transcript": [],
                "ocr": [],
            }
            with patch("video_pipeline.modules.draft_review.engine.analyse_media", return_value=(media, [])):
                result, job_dir = run_review(
                    ReviewRequest(video=video, script=script, editor="editor", title="test"),
                    settings,
                    provider_name="auto",
                )
            self.assertEqual(result.status, "needs_attention")
            self.assertEqual(result.provider, "none")
            self.assertTrue((job_dir / "analysis" / "agent-chunk-000.request.json").exists())


if __name__ == "__main__":
    unittest.main()
