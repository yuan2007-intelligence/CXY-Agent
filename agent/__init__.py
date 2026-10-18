"""CXY-Agent —— 产学研情报采集智能体核心库。

对应仓库根目录 `keyword.md` 配置约定：
智能体每次采集时读取该文件，将关键字注入检索上下文，
实现无人工干预的闭环采集；编辑保存后下次采集自动生效。
"""

__version__ = "0.1.0"

from .keyword_parser import KeywordConfig, load_config, parse_config
from .queries import QueryPlan, build_query_plan
from .scoring import score_item, filter_excluded
from .report import render_report

__all__ = [
    "KeywordConfig",
    "load_config",
    "parse_config",
    "QueryPlan",
    "build_query_plan",
    "score_item",
    "filter_excluded",
    "render_report",
]
