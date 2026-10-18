"""情报条目过滤与排序。

评分模型（与 keyword.md 口径一致）：
- 相关性权重 30%：命中关键字按优先级加权求和，归一化；
- 时效性权重 40%：按条目日期距今天数衰减（越新越高）；
- 来源权重 30%：按来源权威度分级打分。

任何条目命中「排除词」直接丢弃。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from .keyword_parser import KeywordConfig

W_RELEVANCE = 0.30
W_RECENCY = 0.40
W_SOURCE = 0.30

# 来源权威度分级（域名片段 → 分数 0~1）
SOURCE_TIERS: list[tuple[str, float]] = [
    ("gov.cn", 1.0), ("edu.cn", 0.95), ("ac.cn", 0.95),
    ("nature.com", 0.95), ("science.org", 0.95), ("cell.com", 0.95),
    ("arxiv.org", 0.90), ("ieee.org", 0.90), ("acm.org", 0.90),
    ("neurips.cc", 0.90), ("openreview.net", 0.90),
    ("news.cn", 0.90), ("people.com.cn", 0.85), ("xinhuanet.com", 0.90),
    ("caixin.com", 0.85), ("36kr.com", 0.75), ("pingwest.com", 0.70),
    ("sina.com.cn", 0.55), ("163.com", 0.55), ("sohu.com", 0.45),
    ("zhihu.com", 0.50), ("weixin.qq.com", 0.50), ("mp.weixin.qq.com", 0.50),
]


@dataclass
class Item:
    """一条候选情报。"""

    title: str
    url: str = ""
    summary: str = ""
    source: str = ""                  # 来源名或域名
    published: Optional[date] = None  # 发布日期（未知则为 None）
    category: str = ""                # 产业 / 学界 / 科研 / 政策
    extra: dict = field(default_factory=dict)


def _hit_terms(text: str, terms: list[str]) -> list[str]:
    low = text.lower()
    return [t for t in terms if t.lower() in low]


def is_excluded(item: Item, cfg: KeywordConfig) -> bool:
    blob = f"{item.title} {item.summary}"
    return bool(_hit_terms(blob, cfg.exclusions))


def filter_excluded(items: list[Item], cfg: KeywordConfig) -> list[Item]:
    return [it for it in items if not is_excluded(it, cfg)]


def relevance_score(item: Item, cfg: KeywordConfig) -> float:
    """0~1。命中关键字优先级加和，封顶 10 分归一。"""
    blob = f"{item.title} {item.summary}"
    score = 0.0
    for kw in cfg.all_tracking_keywords():
        if _hit_terms(blob, kw.terms):
            score += kw.priority
    return min(1.0, score / 10.0)


def recency_score(item: Item, cfg: KeywordConfig, today: Optional[date] = None) -> float:
    """0~1。当天=1，超过配置时间范围线性衰减至 0.1，未知日期给 0.3。"""
    if item.published is None:
        return 0.3
    today = today or datetime.now().date()
    age = (today - item.published).days
    if age < 0:
        age = 0
    if age >= cfg.days:
        return 0.1
    return 1.0 - 0.9 * age / cfg.days


def source_score(item: Item) -> float:
    """0~1。按域名分级；不在名单内的中等来源给 0.6。"""
    blob = f"{item.url} {item.source}".lower()
    for frag, score in SOURCE_TIERS:
        if frag in blob:
            return score
    return 0.6


def score_item(item: Item, cfg: KeywordConfig,
               today: Optional[date] = None) -> float:
    """综合得分 0~1。"""
    return round(
        W_RELEVANCE * relevance_score(item, cfg)
        + W_RECENCY * recency_score(item, cfg, today)
        + W_SOURCE * source_score(item),
        4,
    )


def rank_items(items: list[Item], cfg: KeywordConfig,
               top: int = 20) -> list[Item]:
    """过滤排除词 → 打分 → 按类别配额排序输出。"""
    kept = filter_excluded(items, cfg)
    for it in kept:
        it.extra["score"] = score_item(it, cfg)
    kept.sort(key=lambda it: it.extra["score"], reverse=True)
    return kept[:top]
