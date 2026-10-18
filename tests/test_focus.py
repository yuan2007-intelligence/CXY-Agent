"""focus_keywords_md：按板块裁剪 keyword.md 章节的解析逻辑。"""
import unittest
from pathlib import Path

from cxy_agent.filter import (
    CATEGORY_HEADER_MARKERS,
    SKIPPED_SECTION_MARKERS,
    focus_keywords_md,
)

ROOT = Path(__file__).resolve().parent.parent
KEYWORDS = (ROOT / "keyword.md").read_text("utf-8")


class TestFocus(unittest.TestCase):
    def test_each_category_matches_its_chapter(self):
        pairs = {
            "industry": ("第一章", "排除词"),
            "research": ("第二章", "排除词"),
            "academia": ("第三章", "排除词"),
        }
        for category, (chapter, shared) in pairs.items():
            focused = focus_keywords_md(KEYWORDS, category)
            self.assertIn(chapter, focused, category)
            # 通用小节(排除词)必须一起进入上下文
            self.assertIn(shared, focused, category)
            # 其他章节不得进入
            for other_chapter in ("第一章", "第二章", "第三章"):
                if other_chapter != chapter:
                    self.assertNotIn(f"## {other_chapter}", focused, category)

    def test_editing_notes_are_excluded(self):
        focused = focus_keywords_md(KEYWORDS, "industry")
        for marker in SKIPPED_SECTION_MARKERS:
            self.assertNotIn(f"## {marker}", focused)

    def test_maintenance_guide_never_in_context(self):
        for category in CATEGORY_HEADER_MARKERS:
            focused = focus_keywords_md(KEYWORDS, category)
            self.assertNotIn("维护指南", focused)

    def test_fallback_returns_full_text_when_no_match(self):
        self.assertEqual(focus_keywords_md(KEYWORDS, "nonexistent"), KEYWORDS)


if __name__ == "__main__":
    unittest.main()
