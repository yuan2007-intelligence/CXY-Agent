"""推送状态与事件历史的持久化行为。"""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cxy_agent.state import EventHistory, SentState


class TestSentState(unittest.TestCase):
    def test_mark_and_contains(self):
        with tempfile.TemporaryDirectory() as d:
            s = SentState(Path(d) / "sent.json")
            s.mark("abc")
            self.assertTrue(s.contains("abc"))
            self.assertFalse(s.contains("zzz"))
            s.save()
            reloaded = SentState(Path(d) / "sent.json")
            self.assertTrue(reloaded.contains("abc"))

    def test_prune_expires_old_entries(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "sent.json"
            old_ts = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
            path.write_text(json.dumps({"old": old_ts, "fresh": datetime.now(timezone.utc).isoformat()}), "utf-8")
            s = SentState(path, retention_days=30)
            pruned = s.prune()
            self.assertEqual(pruned, 1)
            self.assertFalse(s.contains("old"))
            self.assertTrue(s.contains("fresh"))


class TestEventHistory(unittest.TestCase):
    def test_event_key_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "events.json"
            h = EventHistory(path)
            h.add("标题A", "lighthouse-2026-batch")
            self.assertTrue(h.has_event_key("lighthouse-2026-batch"))
            self.assertFalse(h.has_event_key("other-key"))
            self.assertIn("lighthouse-2026-batch", h.event_keys())
            h.save()
            reloaded = EventHistory(path)
            self.assertTrue(reloaded.has_event_key("lighthouse-2026-batch"))

    def test_matching_title(self):
        with tempfile.TemporaryDirectory() as d:
            h = EventHistory(Path(d) / "events.json")
            h.add("工信部公布新一期智能制造示范工厂名单")
            old = h.matching_title("工信部 公布 新一期 智能制造示范工厂 名单")
            self.assertIsNotNone(old)
            self.assertIsNone(h.matching_title("西门子杯挑战赛开放报名"))

    def test_prune_keeps_recent(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "events.json"
            old_ts = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
            path.write_text(json.dumps([
                {"title": "旧事件", "event_key": "old-key", "ts": old_ts},
                {"title": "新事件", "event_key": "new-key", "ts": datetime.now(timezone.utc).isoformat()},
            ]), "utf-8")
            h = EventHistory(path, retention_days=21)
            h.prune()
            self.assertFalse(h.has_event_key("old-key"))
            self.assertTrue(h.has_event_key("new-key"))


if __name__ == "__main__":
    unittest.main()
