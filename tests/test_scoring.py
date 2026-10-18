"""四维加权评分：权重合并、公式生成、总分计算。"""
import unittest

from cxy_agent.filter import (
    DEFAULT_WEIGHTS,
    compute_final_score,
    merge_weights,
    weights_formula,
)


class TestWeights(unittest.TestCase):
    def test_defaults_sum_to_one(self):
        self.assertAlmostEqual(sum(DEFAULT_WEIGHTS.values()), 1.0, places=6)

    def test_config_weights_override(self):
        w = merge_weights({"relevance": 0.4, "innovation": 0.2, "evidence": 0.2, "actionability": 0.2})
        self.assertAlmostEqual(w["relevance"], 0.4, places=6)

    def test_partial_config_fills_defaults(self):
        # 未覆盖的维度沿用默认值，整体归一化到和为 1，相对比例保持不变
        w = merge_weights({"relevance": 0.5})
        self.assertAlmostEqual(sum(w.values()), 1.0, places=6)
        self.assertAlmostEqual(w["relevance"] / w["innovation"], 0.5 / 0.25, places=6)

    def test_weights_auto_normalized(self):
        w = merge_weights({"relevance": 1.0, "innovation": 1.0, "evidence": 1.0, "actionability": 1.0})
        self.assertAlmostEqual(sum(w.values()), 1.0, places=6)
        self.assertAlmostEqual(w["relevance"], 0.25, places=6)

    def test_invalid_values_ignored(self):
        w = merge_weights({"relevance": "abc", "innovation": 2.0})
        self.assertEqual(w["relevance"], DEFAULT_WEIGHTS["relevance"])
        self.assertAlmostEqual(sum(w.values()), 1.0, places=6)


class TestFinalScore(unittest.TestCase):
    def test_user_specified_weights(self):
        # 相关10 创新0 证据0 可行动0 → 0.30*10 = 3.0
        self.assertEqual(compute_final_score(10, 0, 0, 0), 3.0)
        # 全 8 分 → 8.0
        self.assertEqual(compute_final_score(8, 8, 8, 8), 8.0)
        # 可行动性单独满分 → 2.0
        self.assertEqual(compute_final_score(0, 0, 0, 10), 2.0)

    def test_clamps_out_of_range_metrics(self):
        # 超界值按 0-10 钳制：12→10、-5→0
        # 0.30*10(相关) + 0.25*0(创新) + 0.25*10(证据) + 0.20*10(可行动) = 7.5
        self.assertEqual(compute_final_score(12, -5, 10, 10), 7.5)

    def test_formula_string(self):
        f = weights_formula(merge_weights(None))
        self.assertIn("0.30*relevance", f)
        self.assertIn("0.25*innovation", f)
        self.assertIn("0.25*evidence", f)
        self.assertIn("0.20*actionability", f)


if __name__ == "__main__":
    unittest.main()
