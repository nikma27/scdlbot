import os
import pickle
import tempfile
import unittest
from pathlib import Path

from scdlbot import persistence_hygiene as ph


class PersistenceHygieneTests(unittest.TestCase):
    def test_migrate_persistence_state_normalizes_and_sets_version(self):
        state, summary = ph.migrate_persistence_state({"chat_data": {"1": {"settings": {"mode": "dl"}}}})
        self.assertIn("bot_data", state)
        self.assertEqual(state["bot_data"][ph.PERSISTENCE_VERSION_KEY], ph.CURRENT_PERSISTENCE_VERSION)
        self.assertEqual(summary["old_version"], 1)
        self.assertEqual(summary["new_version"], ph.CURRENT_PERSISTENCE_VERSION)

    def test_cleanup_chat_data_ephemeral(self):
        now_ts = 10_000
        chat_data = {
            "settings": {"mode": "dl"},
            "search_choice:alive": {"created_at": now_ts - 10},
            "search_choice:old": {"created_at": now_ts - 5000},
            "12345": {"urls": {"x": "y"}, "created_at": now_ts - 5000, "__ephemeral__": True},
            "67890": {"urls": {"x": "y"}, "created_at": now_ts - 10, "__ephemeral__": True},
        }
        summary = ph.cleanup_chat_data_ephemeral(
            chat_data,
            now_ts=now_ts,
            search_choice_ttl_seconds=900,
            ephemeral_request_ttl_seconds=3600,
            dry_run=False,
        )
        self.assertEqual(summary["search_choice_removed"], 1)
        self.assertEqual(summary["ephemeral_request_removed"], 1)
        self.assertIn("search_choice:alive", chat_data)
        self.assertNotIn("search_choice:old", chat_data)
        self.assertIn("67890", chat_data)
        self.assertNotIn("12345", chat_data)

    def test_cleanup_persistence_state_aggregates_across_chats(self):
        now_ts = 10_000
        state = {
            "chat_data": {
                "1": {"search_choice:old": {"created_at": now_ts - 5000}},
                "2": {"555": {"urls": {"a": "b"}, "created_at": now_ts - 5000}},
            },
            "bot_data": {},
            "user_data": {},
        }
        summary = ph.cleanup_persistence_state(
            state,
            now_ts=now_ts,
            search_choice_ttl_seconds=900,
            ephemeral_request_ttl_seconds=3600,
            dry_run=False,
        )
        self.assertEqual(summary["search_choice_removed"], 1)
        self.assertEqual(summary["ephemeral_request_removed"], 1)
        self.assertEqual(summary["chats_changed"], 2)

    def test_inspect_persistence_state(self):
        now_ts = 10_000
        summary = ph.inspect_persistence_state(
            {
                "bot_data": {ph.PERSISTENCE_VERSION_KEY: 1},
                "chat_data": {"1": {"search_choice:old": {"created_at": now_ts - 10000}}},
                "user_data": {"2": {"x": 1}},
            },
            now_ts=now_ts,
            search_choice_ttl_seconds=900,
            ephemeral_request_ttl_seconds=3600,
        )
        self.assertEqual(summary["version"], 1)
        self.assertEqual(summary["users_total"], 1)
        self.assertEqual(summary["search_choice_total"], 1)
        self.assertEqual(summary["search_choice_expired"], 1)

    def test_prepare_persistence_file_not_found(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = str(Path(tmp_dir) / "missing.pickle")
            summary = ph.prepare_persistence_file(target, now_ts=1)
            self.assertEqual(summary["status"], "not_found")
            self.assertFalse(summary["exists"])

    def test_prepare_persistence_file_cleanup_and_save(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "state.pickle"
            raw_state = {
                "bot_data": {},
                "chat_data": {"1": {"search_choice:old": {"created_at": 0}}},
                "user_data": {},
                "conversations": {},
                "callback_data": {},
            }
            with open(target, "wb") as handle:
                pickle.dump(raw_state, handle)
            summary = ph.prepare_persistence_file(
                str(target),
                now_ts=10_000,
                search_choice_ttl_seconds=900,
                ephemeral_request_ttl_seconds=3600,
            )
            self.assertEqual(summary["status"], "cleaned_and_saved")
            self.assertTrue(Path(summary["backup_path"]).exists())
            loaded = ph.load_pickle_state(str(target))
            self.assertEqual(loaded["chat_data"]["1"], {})
            self.assertEqual(loaded["bot_data"][ph.PERSISTENCE_VERSION_KEY], 1)

    def test_prepare_persistence_file_corrupt_backup(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "broken.pickle"
            target.write_bytes(b"not-a-pickle")
            summary = ph.prepare_persistence_file(str(target), now_ts=10)
            self.assertEqual(summary["status"], "corrupt_backup_created")
            self.assertTrue(summary["backup_path"])
            self.assertFalse(os.path.exists(str(target)))
            self.assertTrue(os.path.exists(summary["backup_path"]))


if __name__ == "__main__":
    unittest.main()
