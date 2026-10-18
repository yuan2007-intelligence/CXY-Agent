"""keyword.md 解析器。

约定（见 keyword.md「一、维护指南」）：
- 所有 `##` / `###` 标题和行首 `- ` 列表是解析依赖的结构；
- 一条内可用 `、` 分隔多个同义/近义表达；
- 行尾 ★ 数量表示优先级（最多三颗，不标注默认 ★）；
- `<!-- -->` 之间为注释，忽略；
- 「七、排除词」命中即丢弃；
- 「八、采集偏好」可选：时间范围（近 N 天）、语言。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.request import urlopen

# 原始关键字文件地址（每次采集时拉取最新版，编辑保存后自动生效）
KEYWORD_MD_URL = (
    "https://raw.githubusercontent.com/"
    "yuan2007-intelligence/CXY-Agent/main/keyword.md"
)

_STAR_RE = re.compile(r"([★]+)\s*$")
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_DAYS_RE = re.compile(r"近\s*(\d+)\s*天")


@dataclass
class Keyword:
    """一条关键字（含同义表达）及其优先级。"""

    terms: list[str]
    priority: int = 1  # 1~3，对应 ★~★★★

    @property
    def label(self) -> str:
        return self.terms[0]


@dataclass
class KeywordConfig:
    """keyword.md 的结构化表示。"""

    domains: list[Keyword] = field(default_factory=list)          # 二、领域
    industry_events: list[Keyword] = field(default_factory=list)  # 3.1 事件类型
    industry_entities: list[Keyword] = field(default_factory=list)  # 3.2 产业主体
    academia: list[Keyword] = field(default_factory=list)         # 四、学界
    research: list[Keyword] = field(default_factory=list)         # 五、科研
    policy: list[Keyword] = field(default_factory=list)           # 六、政策
    exclusions: list[str] = field(default_factory=list)           # 七、排除词
    days: int = 7                                                 # 八、时间范围（天）
    language: str = "中文优先"                                     # 八、语言

    def all_tracking_keywords(self) -> list[Keyword]:
        """除排除词外全部追踪关键字（按优先级降序）。"""
        kws = (
            self.domains
            + self.industry_events
            + self.industry_entities
            + self.academia
            + self.research
            + self.policy
        )
        return sorted(kws, key=lambda k: -k.priority)


def _parse_item(line: str) -> Optional[Keyword]:
    """解析一行 `- 词A、词B ★★` → Keyword。"""
    text = line.strip()
    if not text.startswith("- "):
        return None
    text = text[2:].strip()
    priority = 1
    m = _STAR_RE.search(text)
    if m:
        priority = len(m.group(1))
        text = text[: m.start()].strip()
    terms = [t.strip() for t in re.split(r"[、,，;；]", text) if t.strip()]
    if not terms:
        return None
    return Keyword(terms=terms, priority=priority)


def parse_config(md_text: str) -> KeywordConfig:
    """把 keyword.md 全文解析为 KeywordConfig。"""
    cfg = KeywordConfig()
    section = None       # 当前二级标题
    subsection = None    # 当前三级标题
    in_exclusion = False

    for raw in _COMMENT_RE.sub("", md_text).splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("### "):
            subsection = line[4:].strip()
            continue
        if line.startswith("## "):
            section = line[3:].strip()
            subsection = None
            in_exclusion = section.startswith("七、")
            continue

        if section and section.startswith("八、"):
            m = _DAYS_RE.search(line)
            if m:
                cfg.days = int(m.group(1))
            continue

        if in_exclusion:
            kw = _parse_item(line)
            if kw:
                cfg.exclusions.extend(kw.terms)
            continue

        kw = _parse_item(line)
        if not kw:
            continue

        if section and section.startswith("二、"):
            cfg.domains.append(kw)
        elif section and section.startswith("三、"):
            if subsection and "3.1" in subsection:
                cfg.industry_events.append(kw)
            elif subsection and "3.2" in subsection:
                cfg.industry_entities.append(kw)
        elif section and section.startswith("四、"):
            cfg.academia.append(kw)
        elif section and section.startswith("五、"):
            cfg.research.append(kw)
        elif section and section.startswith("六、"):
            cfg.policy.append(kw)

    return cfg


def load_config(path: Optional[str | Path] = None) -> KeywordConfig:
    """加载配置：默认从 GitHub 拉取最新 keyword.md，可传本地路径覆盖。"""
    if path is not None:
        return parse_config(Path(path).read_text(encoding="utf-8"))
    with urlopen(KEYWORD_MD_URL, timeout=30) as resp:  # noqa: S310 - 固定地址
        return parse_config(resp.read().decode("utf-8"))
