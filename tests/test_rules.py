import unittest

from video_pipeline.modules.draft_review.rules import deduplicate_issues, deterministic_issues
from video_pipeline.models import Issue


class RuleTests(unittest.TestCase):
    def test_privacy_and_resolution_are_found(self):
        media = {
            "width": 1280, "height": 720,
            "audio": {"available": True, "integrated_lufs": -29.0},
            "transcript": [],
            "ocr": [{"time_sec": 12, "frame": "frame_000007.jpg", "text": "Account demo@example.com"}],
        }
        issues = deterministic_issues(media, "")
        titles = {item.title for item in issues}
        self.assertIn("Possible account information is visible", titles)
        self.assertIn("Confirm the final export resolution", titles)
        self.assertIn("Dialogue may be too quiet", titles)

    def test_duplicate_issues_are_collapsed(self):
        issues = [
            Issue(10, "Zoom into menu", "The menu is too small", "Zoom", confidence=0.5),
            Issue(12, "Zoom into the menu", "The menu is too small", "Zoom", confidence=0.9),
        ]
        result = deduplicate_issues(issues)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].confidence, 0.9)
        self.assertEqual(result[0].issue_id, "ISSUE-001")

    def test_repeated_phrase_is_required(self):
        media = {
            "height": 1080,
            "audio": {"available": False},
            "ocr": [],
            "transcript": [{"start_sec": 4, "end_sec": 8, "text": "this is the confusing part this is the confusing part"}],
        }
        issues = deterministic_issues(media, "")
        repetition = next(item for item in issues if item.title == "Possible repeated take")
        self.assertEqual(repetition.severity, "required")


if __name__ == "__main__":
    unittest.main()
