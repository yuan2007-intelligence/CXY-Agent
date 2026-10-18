"""config.yaml 与 keyword.md 的一致性守卫：排期、检索式、权重、章节。"""
import unittest
from pathlib import Path

import yaml

from cxy_agent.filter import CATEGORY_HEADER_MARKERS, VALID_CATEGORIES, merge_weights

ROOT = Path(__file__).resolve().parent.parent
CONFIG = yaml.safe_load((ROOT / "config.yaml").read_text("utf-8"))
KEYWORDS_EXISTS = (ROOT / "keyword.md").exists()


class TestConfig(unittest.TestCase):
    def test_schedule_covers_all_categories(self):
        scheduled = set((CONFIG["schedule"]["weekday_category"]).values())
        self.assertEqual(scheduled, VALID_CATEGORIES)

    def test_labels_for_all_categories(self):
        labels = CONFIG.get("category_labels") or {}
        self.assertTrue(set(labels) >= VALID_CATEGORIES)

    def test_queries_defined_for_all_categories(self):
        queries = CONFIG.get("google_news_queries") or {}
        for category in VALID_CATEGORIES:
            self.assertTrue(queries.get(category), f"missing queries for {category}")
            for q in queries[category]:
                self.assertIsInstance(q, str) and self.assertTrue(q.strip())

    def test_scoring_weights_valid(self):
        w = merge_weights((CONFIG.get("scoring") or {}).get("weights"))
        self.assertAlmostEqual(sum(w.values()), 1.0, places=6)
        # 默认与用户指定的 30/25/25/20 一致
        self.assertAlmostEqual(w["relevance"], 0.30, places=6)
        self.assertAlmostEqual(w["innovation"], 0.25, places=6)
        self.assertAlmostEqual(w["evidence"], 0.25, places=6)
        self.assertAlmostEqual(w["actionability"], 0.20, places=6)

    def test_keyword_md_matches_categories(self):
        if not KEYWORDS_EXISTS:
            self.fail("keyword.md 不存在")
        text = (ROOT / "keyword.md").read_text("utf-8")
        for category, markers in CATEGORY_HEADER_MARKERS.items():
            self.assertTrue(
                any(m in text for m in markers),
                f"keyword.md 缺少 {category} 章节标记 {markers}",
            )

    def test_state_and_push_settings_present(self):
        self.assertIn("retention_days", CONFIG["state"])
        self.assertIn("min_score", CONFIG["push"])
        self.assertIn("max_articles", CONFIG["push"])
        self.assertIn("scorer_model", CONFIG["deepseek"])


if __name__ == "__main__":
    unittest.main()
