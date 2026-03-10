import os
import tempfile
import unittest
from pathlib import Path

from scdlbot.config_validation import redact_value, sanitize_mapping_for_log, validate_runtime_config


class ConfigValidationTests(unittest.TestCase):
    def test_redacts_sensitive_keys(self):
        self.assertEqual(redact_value("TG_BOT_TOKEN", "123:abc"), "[redacted]")
        self.assertEqual(redact_value("WEBHOOK_SECRET_TOKEN", "secret"), "[redacted]")

    def test_sanitizes_urls(self):
        value = redact_value("WEBHOOK_APP_URL_ROOT", "https://example.com/a?token=secret#x")
        self.assertEqual(value, "https://example.com/a")

    def test_sanitize_mapping_for_log(self):
        data = sanitize_mapping_for_log(
            {
                "TG_BOT_TOKEN": "123",
                "DL_DIR": "/tmp/scdlbot",
                "WEBHOOK_APP_URL_ROOT": "https://example.com/path?q=1",
            }
        )
        self.assertEqual(data["TG_BOT_TOKEN"], "[redacted]")
        self.assertEqual(data["DL_DIR"], "/tmp/scdlbot")
        self.assertEqual(data["WEBHOOK_APP_URL_ROOT"], "https://example.com/path")

    def test_validate_runtime_config_ok(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            chat_storage = Path(temp_dir) / "state" / "chat.pickle"
            parsed = {
                "TG_BOT_TOKEN": "token",
                "TG_BOT_API": "https://api.telegram.org",
                "TG_BOT_API_LOCAL_MODE": False,
                "CHAT_STORAGE": str(chat_storage),
                "DL_DIR": str(Path(temp_dir) / "dl"),
                "WORKERS": 2,
                "EXECUTOR_KIND": "thread",
                "DL_TIMEOUT": 300,
                "CHECK_URL_TIMEOUT": 30,
                "COMMON_CONNECTION_TIMEOUT": 10,
                "METRICS_PORT": 8000,
                "HEALTHCHECK_ENABLE": True,
                "HEALTHCHECK_PORT": 8080,
                "WEBHOOK_ENABLE": False,
                "WEBHOOK_APP_URL_ROOT": "",
                "WEBHOOK_APP_URL_PATH": "",
                "WEBHOOK_PORT": 5000,
                "COOKIES_FILE": "",
                "MAX_ACTIVE_JOBS_PER_CHAT": 4,
                "MAX_GLOBAL_ACTIVE_JOBS": 8,
            }
            result = validate_runtime_config(parsed, env={"TG_BOT_TOKEN": "token"})
            self.assertTrue(result.ok)
            self.assertEqual(result.errors, [])

    def test_validate_runtime_config_fails_on_missing_token(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            parsed = {
                "TG_BOT_TOKEN": "",
                "TG_BOT_API": "https://api.telegram.org",
                "TG_BOT_API_LOCAL_MODE": False,
                "CHAT_STORAGE": str(Path(temp_dir) / "state.pickle"),
                "DL_DIR": str(Path(temp_dir) / "dl"),
                "WORKERS": 2,
                "EXECUTOR_KIND": "thread",
                "DL_TIMEOUT": 300,
                "CHECK_URL_TIMEOUT": 30,
                "COMMON_CONNECTION_TIMEOUT": 10,
                "METRICS_PORT": 8000,
                "HEALTHCHECK_ENABLE": False,
                "HEALTHCHECK_PORT": 8080,
                "WEBHOOK_ENABLE": False,
                "WEBHOOK_APP_URL_ROOT": "",
                "WEBHOOK_APP_URL_PATH": "",
                "WEBHOOK_PORT": 5000,
                "COOKIES_FILE": "",
                "MAX_ACTIVE_JOBS_PER_CHAT": 4,
                "MAX_GLOBAL_ACTIVE_JOBS": 8,
            }
            result = validate_runtime_config(parsed, env={})
            self.assertFalse(result.ok)
            self.assertTrue(any("TG_BOT_TOKEN" in error for error in result.errors))


if __name__ == "__main__":
    unittest.main()
