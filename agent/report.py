"""情报日报渲染：把排序后的条目生成 Markdown 报告。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from .keyword_parser import KeywordConfig
from .scoring import Item

CATEGORY_ORDER = ["产业", "学界", "科研", "政策"]


def _stars(priority: int) -> str:
    return "★" * priority + "☆" * (3 - priority)


def render_report(items: list[Item], cfg: KeywordConfig,
                  run_at: Optional[datetime] = None) -> str:
    """生成一份中文 Markdown 情报日报。"""
    run_at = run_at or datetime.now()
    lines: list[str] = []
    lines.append(f"# 产学研情报日报 · {run_at:%Y-%m-%d}")
    lines.append("")
    lines.append(
        f"> 采集范围：近 {cfg.days} 天 · 语言：{cfg.language} · "
        f"共收录 {len(items)} 条（已按排除词过滤）"
    )
    lines.append("")

    for cat in CATEGORY_ORDER:
        group = [it for it in items if it.category == cat]
        lines.append(f"## {cat}动态（{len(group)} 条）")
        lines.append("")
        if not group:
            lines.append("本期无收录。")
            lines.append("")
            continue
        for it in group:
            score = it.extra.get("score", 0.0)
            date_str = it.published.strftime("%m-%d") if it.published else "日期待确认"
            src = it.source or it.url
            lines.append(f"### [{_stars(3 if score >= 0.75 else 2 if score >= 0.6 else 1)}] {it.title}")
            lines.append("")
            lines.append(f"- 日期：{date_str}　来源：{src}　评分：{score:.2f}")
            if it.summary:
                lines.append(f"- 摘要：{it.summary.strip()}")
            if it.url:
                lines.append(f"- 链接：{it.url}")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        f"由 CXY-Agent 数智学研智能体生成于 {run_at:%Y-%m-%d %H:%M} · "
        "关键字配置见仓库 keyword.md"
    )
    return "\n".join(lines)
