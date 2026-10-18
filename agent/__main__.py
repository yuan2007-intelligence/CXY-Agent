"""命令行入口。

用法：
    python -m agent plan [keyword.md]     # 打印本次采集的检索计划
    python -m agent summary [keyword.md]  # 打印配置解析摘要（自检用）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .keyword_parser import load_config
from .queries import build_query_plan


def _print_plan(cfg_path: str | None) -> None:
    cfg = load_config(cfg_path)
    plan = build_query_plan(cfg)
    print(f"# 检索计划：共 {plan.total} 条查询（时间范围：近 {cfg.days} 天）\n")
    for cat in ("产业", "学界", "科研", "政策"):
        qs = plan.by_category(cat)
        print(f"## {cat}（{len(qs)} 条）")
        for q in qs:
            print(f"- {q.priority_stars} [{q.days}天内] {q.text}")
        print()


def _print_summary(cfg_path: str | None) -> None:
    cfg = load_config(cfg_path)
    print(json.dumps({
        "domains": len(cfg.domains),
        "industry_events": len(cfg.industry_events),
        "industry_entities": len(cfg.industry_entities),
        "academia": len(cfg.academia),
        "research": len(cfg.research),
        "policy": len(cfg.policy),
        "exclusions": cfg.exclusions,
        "days": cfg.days,
        "language": cfg.language,
    }, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    cmd = argv[0] if argv else "plan"
    cfg_path = argv[1] if len(argv) > 1 else None
    if cmd == "plan":
        _print_plan(cfg_path)
    elif cmd == "summary":
        _print_summary(cfg_path)
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
