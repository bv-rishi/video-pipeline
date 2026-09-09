from pathlib import Path
import json
import tempfile
import unittest

from video_pipeline.config import Settings
from video_pipeline.tracker import BatchError, mark_ready


class TrackerTests(unittest.TestCase):
    def test_editor_can_mark_fully_checked_batch_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(work_dir=Path(directory))
            settings.ensure_dirs()
            path = settings.work_dir / "batches" / "editor-one-test.json"
            path.write_text(json.dumps({
                "batch_id": "editor-one-test", "editor": "editor-one", "total": 2,
                "completed": 2, "failed": 0, "ready": 0,
                "jobs": [{"status": "review_complete"}, {"status": "review_complete"}],
            }))
            state, _ = mark_ready("editor-one-test", settings)
            self.assertEqual(state["status"], "ready_for_reviewer")
            self.assertEqual(state["completed"], 2)
            self.assertEqual(state["ready"], 2)

    def test_incomplete_batch_cannot_be_marked_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(work_dir=Path(directory))
            settings.ensure_dirs()
            path = settings.work_dir / "batches" / "editor-two-test.json"
            path.write_text(json.dumps({
                "batch_id": "editor-two-test", "editor": "editor-two", "total": 2,
                "completed": 1, "failed": 1, "ready": 0,
                "jobs": [{"status": "review_complete"}, {"status": "failed"}],
            }))
            with self.assertRaises(BatchError):
                mark_ready("editor-two-test", settings)


if __name__ == "__main__":
    unittest.main()
