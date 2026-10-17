"""检索查询生成：把 KeywordConfig 展开为可执行的检索计划。

策略：
- 每条查询 = 「领域/主体词」×「事件/成果类型词」，保证召回内容有信息增量；
- 纯领域词（无事件词搭配时）单独成查询，用于捕捉突破类新闻；
- 按优先级配额取样，控制单次采集的查询总量（查询即成本）；
- 每条查询携带类别与时间范围，供采集层使用。
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

from .keyword_parser import KeywordConfig

# 单次采集各类别的查询配额（可按额度调整）
CATEGORY_QUOTA = {
    "产业": 6,
    "学界": 3,
    "科研": 4,
    "政策": 3,
}


@dataclass
class Query:
    category: str          # 产业 / 学界 / 科研 / 政策
    text: str              # 注入检索上下文的查询串
    priority: int          # 1~3
    days: int              # 时间范围（天）

    @property
    def priority_stars(self) -> str:
        return "★" * self.priority


@dataclass
class QueryPlan:
    queries: list[Query] = field(default_factory=list)

    def by_category(self, category: str) -> list[Query]:
        return [q for q in self.queries if q.category == category]

    @property
    def total(self) -> int:
        return len(self.queries)


def _pick(keywords, quota: int) -> list:
    """按优先级降序取样，最多 quota 条。"""
    ordered = sorted(keywords, key=lambda k: -k.priority)
    return ordered[:quota]


def build_query_plan(cfg: KeywordConfig) -> QueryPlan:
    plan = QueryPlan()

    # —— 产业：主体/领域词 × 事件类型词 ——
    # 每个锚点词最多搭配 2 个事件词，避免高优先级词独占配额
    anchors = _pick(cfg.industry_entities + cfg.domains, 6)
    events = _pick(cfg.industry_events, 6)
    industry: list[Query] = []
    for a in anchors:
        for e in events[:2]:
            industry.append(Query("产业", f"{' '.join(a.terms)} {' '.join(e.terms)}",
                                  min(3, a.priority + e.priority - 1), cfg.days))
    plan.queries += _pick_by_priority(industry, CATEGORY_QUOTA["产业"])

    # —— 学界 / 科研 / 政策：直接取优先级最高的关键字 ——
    for category, source in (("学界", cfg.academia),
                             ("科研", cfg.research),
                             ("政策", cfg.policy)):
        for kw in _pick(source, CATEGORY_QUOTA[category]):
            plan.queries.append(Query(category, " ".join(kw.terms),
                                      kw.priority, cfg.days))
    return plan


def _pick_by_priority(queries: list[Query], quota: int) -> list[Query]:
    """产业组合查询可能爆量：先按组合优先级去重（同文本只留最高优先级），再配额。"""
    best: dict[str, Query] = {}
    for q in queries:
        if q.text not in best or q.priority > best[q.text].priority:
            best[q.text] = q
    ordered = sorted(best.values(), key=lambda q: (-q.priority, q.text))
    return ordered[:quota]
