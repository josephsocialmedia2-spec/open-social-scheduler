from __future__ import annotations

import unittest

from publisher.persist_final_queue_github import (
    changed_job_ids,
    changed_top_level_keys,
    merge_queue,
)


class QueuePersistenceTests(unittest.TestCase):
    def test_merge_preserves_concurrently_added_job(self):
        before = {
            "version": 3,
            "pipeline": "f1-final-assets",
            "updated_at": "before",
            "jobs": [
                {"id": "COMM-A", "status": "READY", "buffer_posts": []},
            ],
        }
        after = {
            "version": 3,
            "pipeline": "f1-final-assets",
            "updated_at": "after",
            "jobs": [
                {
                    "id": "COMM-A",
                    "status": "SCHEDULED",
                    "buffer_posts": [{"post_id": "buffer-123", "service": "facebook"}],
                },
            ],
        }
        remote = {
            "version": 3,
            "pipeline": "f1-final-assets",
            "updated_at": "remote-newer",
            "jobs": [
                {"id": "COMM-A", "status": "READY", "buffer_posts": []},
                {"id": "COMM-B", "status": "READY", "buffer_posts": []},
            ],
        }

        ids = changed_job_ids(before, after)
        keys = changed_top_level_keys(before, after)
        merged = merge_queue(remote, after, ids, keys)
        jobs = {job["id"]: job for job in merged["jobs"]}

        self.assertEqual(ids, {"COMM-A"})
        self.assertEqual(jobs["COMM-A"]["status"], "SCHEDULED")
        self.assertEqual(jobs["COMM-A"]["buffer_posts"][0]["post_id"], "buffer-123")
        self.assertEqual(jobs["COMM-B"]["status"], "READY")
        self.assertEqual(merged["updated_at"], "after")

    def test_unchanged_remote_jobs_are_not_overwritten(self):
        before = {"jobs": [{"id": "A", "status": "READY"}, {"id": "B", "status": "READY"}]}
        after = {"jobs": [{"id": "A", "status": "PUBLISHED"}, {"id": "B", "status": "READY"}]}
        remote = {
            "jobs": [
                {"id": "A", "status": "READY"},
                {"id": "B", "status": "READY", "new_remote_field": "keep-me"},
            ]
        }
        merged = merge_queue(
            remote,
            after,
            changed_job_ids(before, after),
            changed_top_level_keys(before, after),
        )
        jobs = {job["id"]: job for job in merged["jobs"]}
        self.assertEqual(jobs["A"]["status"], "PUBLISHED")
        self.assertEqual(jobs["B"]["new_remote_field"], "keep-me")


if __name__ == "__main__":
    unittest.main()
