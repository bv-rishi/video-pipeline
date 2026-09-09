import unittest

from video_pipeline.relay import chat_text


class RelayTests(unittest.TestCase):
    def setUp(self):
        self.config = {"reviewer_user_id": "100", "reviewer_label": "Reviewer", "editors": {"editor-one": "200"}}

    def test_review_message_uses_real_mentions_and_counts(self):
        event = {"event": "review_complete", "editor": "editor-one", "batch_id": "batch-1",
                 "checked": 5, "total": 5, "failed": 0, "ready": 0}
        message = chat_text(event, self.config)
        self.assertIn("<users/100> <users/200>", message)
        self.assertIn("5 of 5", message)

    def test_failure_message_does_not_claim_ready(self):
        event = {"event": "review_complete", "editor": "editor-one", "batch_id": "batch-1",
                 "checked": 4, "total": 5, "failed": 1, "ready": 0}
        message = chat_text(event, self.config)
        self.assertIn("attention needed", message)
        self.assertIn("No failed video is marked ready", message)

    def test_ready_message_is_editor_confirmation(self):
        event = {"event": "ready_for_reviewer", "editor": "editor-one", "batch_id": "batch-1",
                 "checked": 5, "total": 5, "failed": 0, "ready": 5}
        message = chat_text(event, self.config)
        self.assertIn("5 of 5", message)
        self.assertIn("editor confirmed", message)
        self.assertIn("Reviewer", message)


if __name__ == "__main__":
    unittest.main()
