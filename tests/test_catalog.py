import unittest
from agent.keyword_parser import parse_config
from cxy_agent.catalog import plan

class CatalogTests(unittest.TestCase):
    def test_current_file_has_all_categories(self):
        cfg, groups = plan()
        self.assertEqual(cfg.days, 30)
        self.assertTrue(all(groups.values()))
        self.assertIn('广告', cfg.exclusions)
        self.assertEqual(len(groups['industry']), 20)

    def test_preferences_are_not_keywords(self):
        cfg = parse_config('### 第一部分：产业\n- 工厂 ★★★\n### 排除词\n- 广告、促销\n### 采集偏好\n- 信息时间范围：近 10 天')
        self.assertEqual(cfg.days, 10)
        self.assertEqual(cfg.industry_events[0].priority, 3)
        self.assertEqual(cfg.exclusions, ['广告', '促销'])
