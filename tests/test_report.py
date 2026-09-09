from pathlib import Path
import tempfile
import unittest

from video_pipeline.models import Issue, ReviewResult
from video_pipeline.report import write_reports


class ReportTests(unittest.TestCase):
    def test_writes_local_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            result = ReviewResult(
                job_id="job", title="Example <Tutorial>", editor="editor-two",
                video_path="/private/video.mp4", script_path="/private/script.txt",
                video_sha256="a", script_sha256="b", status="review_complete",
                issues=[Issue(47, "Zoom in", "The text is small", "Crop closer", evidence_frame="frame_000024.jpg")],
                created_at="now", completed_at="now",
            )
            write_reports(result, target)
            self.assertTrue((target / "report.json").exists())
            page = (target / "report.html").read_text()
            self.assertIn("Example &lt;Tutorial&gt;", page)
            self.assertIn("frame_000024.jpg", page)


if __name__ == "__main__":
    unittest.main()
