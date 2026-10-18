"""标题相似度与正文指纹去重逻辑。"""
import unittest

from cxy_agent.sources import (
    Article,
    _body_similar,
    _is_similar,
    _normalize_title,
    dedupe,
    dedupe_by_content,
)


def make(title, url, content="", tier="trusted"):
    return Article(title=title, url=url, summary="", source="test", source_tier=tier, content=content)


class TestTitleSimilarity(unittest.TestCase):
    def test_exact_normalized_match(self):
        a = _normalize_title("灯塔工厂名单更新！")
        b = _normalize_title("灯塔工厂 名单 更新")
        self.assertTrue(_is_similar(a, b, "灯塔工厂名单更新！", "灯塔工厂 名单 更新", 0.65))

    def test_cross_language_specific_terms_merge(self):
        # 双方标题各含 ≥2 个同一组英文标识符(optimus/gen3) → 应判同事件
        a = _normalize_title("特斯拉Optimus Gen3进厂实训")
        b = _normalize_title("Tesla Optimus Gen3 factory training")
        self.assertTrue(_is_similar(a, b, "特斯拉Optimus Gen3进厂实训", "Tesla Optimus Gen3 factory training", 0.65))

    def test_pure_chinese_vs_english_titles_not_merged(self):
        # 纯中文标题无拉丁术语可对齐，序列相似度也不够 → 不判同事件（宁可漏合不误合）
        a = _normalize_title("西门子发布工业大模型平台")
        b = _normalize_title("Siemens launches industrial LLM platform")
        self.assertFalse(_is_similar(a, b, "西门子发布工业大模型平台", "Siemens launches industrial LLM platform", 0.65))

    def test_generic_only_overlap_does_not_merge(self):
        a = _normalize_title("某公司发布工业大模型")
        b = _normalize_title("另一家公司推出AI质检系统")
        self.assertFalse(_is_similar(a, b, "某公司发布工业大模型", "另一家公司推出AI质检系统", 0.65))


class TestBodySimilarity(unittest.TestCase):
    def test_identical_bodies(self):
        body = "工信部公布新一期智能制造示范工厂名单，共一百零一家企业入选，覆盖汽车、装备、电子等行业。" * 3
        self.assertTrue(_body_similar(body, body, 0.90))

    def test_different_bodies(self):
        a = "灯塔工厂是世界经济论坛评选的全球智能制造标杆。" * 3
        b = "西门子杯中国智能制造挑战赛面向全国高校学生开放报名。" * 3
        self.assertFalse(_body_similar(a, b, 0.90))

    def test_short_bodies_never_match(self):
        self.assertFalse(_body_similar("太短", "太短", 0.90))


class TestListDedupe(unittest.TestCase):
    def test_uid_dedupe_keeps_first(self):
        a1 = make("t", "https://a.com/x")
        a2 = make("t", "https://a.com/x?utm_source=rss")
        self.assertEqual(a1.uid, a2.uid)
        self.assertEqual(len(dedupe([a1, a2])), 1)

    def test_content_dedupe_prefers_higher_tier(self):
        low = make("转载标题A", "https://news.example.com/1", content="正文" * 200, tier="discovery")
        high = make("原标题B", "https://gov.example.cn/2", content="正文" * 200, tier="primary")
        kept = dedupe_by_content([low, high])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].source_tier, "primary")

    def test_body_only_dedupe_different_titles(self):
        a = make("标题甲", "https://a.com/1", content="完全相同的正文内容。" * 100)
        b = make("标题乙", "https://b.com/2", content="完全相同的正文内容。" * 100)
        kept = dedupe_by_content([a, b], threshold=1.1, body_threshold=0.90)
        self.assertEqual(len(kept), 1)


if __name__ == "__main__":
    unittest.main()
