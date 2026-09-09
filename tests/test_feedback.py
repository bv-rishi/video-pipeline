from pathlib import Path
import json
import tempfile
import unittest

from video_pipeline.config import Settings
from video_pipeline.feedback import FeedbackError, record_feedback


class FeedbackTests(unittest.TestCase):
    def make_job(self, settings):
        job_id = "example-job-1234"
        job_dir = settings.work_dir / "jobs" / job_id
        job_dir.mkdir(parents=True)
        (job_dir / "job.json").write_text(json.dumps({
            "job_id": job_id, "video_sha256": "video-hash", "script_sha256": "script-hash",
        }))
        (job_dir / "report.json").write_text(json.dumps({
            "issues": [{"issue_id": "ISSUE-001"}],
        }))
        return job_id

    def test_records_scoped_feedback_without_source_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(work_dir=Path(directory))
            settings.ensure_dirs()
            job_id = self.make_job(settings)
            record = record_feedback(settings, job_id=job_id, kind="incorrect", scope="draft-review",
                                     issue_id="ISSUE-001", note="The screen was obscured, not missing.")
            self.assertEqual(record["scope"], "draft-review")
            self.assertNotIn("video_path", record)
            saved = (settings.work_dir / "feedback" / "feedback.jsonl").read_text()
            self.assertIn("obscured", saved)

    def test_existing_issue_is_required_for_incorrect_feedback(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(work_dir=Path(directory))
            settings.ensure_dirs()
            job_id = self.make_job(settings)
            with self.assertRaises(FeedbackError):
                record_feedback(settings, job_id=job_id, kind="incorrect", scope="video",
                                issue_id="ISSUE-999", note="Wrong finding")


if __name__ == "__main__":
    unittest.main()
