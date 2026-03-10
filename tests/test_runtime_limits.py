import unittest

from scdlbot.runtime_limits import RuntimeAdmission


class RuntimeAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.admission = RuntimeAdmission()

    def _decision(self, **kwargs):
        defaults = {
            "request_type": "search",
            "user_id": 1,
            "chat_id": 10,
            "query_preview": "artist track",
            "url_preview": "",
            "is_owner": False,
            "max_active_jobs_per_user": 2,
            "max_active_jobs_per_chat": 4,
            "max_global_active_jobs": 8,
            "user_request_cooldown_seconds": 0,
            "chat_request_cooldown_seconds": 0,
            "burst_request_limit": 5,
            "burst_window_seconds": 20,
        }
        defaults.update(kwargs)
        return self.admission.check_request_admission(**defaults)

    def test_register_and_finish_job(self):
        job_id = self.admission.register_job(
            job_type="search",
            user_id=1,
            chat_id=10,
            request_type="search",
            query_preview="x",
        )
        self.assertIsNotNone(job_id)
        self.assertEqual(self.admission.count_jobs(), 1)
        self.admission.finish_job(job_id)
        self.assertEqual(self.admission.count_jobs(), 0)

    def test_rejects_when_shutdown_requested(self):
        self.assertTrue(self.admission.request_shutdown(reason="test", actor="owner"))
        decision = self._decision()
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason_code, "shutdown")

    def test_enforces_global_limit(self):
        for index in range(2):
            self.admission.register_job(
                job_type="download",
                user_id=index + 1,
                chat_id=10,
                request_type="dl",
                url_preview="u",
            )
        decision = self._decision(max_global_active_jobs=2)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason_code, "global_limit")

    def test_enforces_user_limit(self):
        for _ in range(2):
            self.admission.register_job(
                job_type="search",
                user_id=1,
                chat_id=10,
                request_type="search",
                query_preview="q",
            )
        decision = self._decision(max_active_jobs_per_user=2)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason_code, "user_limit")


if __name__ == "__main__":
    unittest.main()
