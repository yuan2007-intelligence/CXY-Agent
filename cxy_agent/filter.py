"""DeepSeek API 过滤层：用 keyword.md 做相关性打分与四维价值终评，top N 写中文摘要。

使用 DeepSeek API（OpenAI 兼容格式）。四维评分权重从 config.yaml 的
scoring.weights 读取（默认：相关性 30%、创新性 25%、证据强度 25%、可行动性 20%）。
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

import openai

from .sources import Article

log = logging.getLogger(__name__)

VALID_CATEGORIES = {"industry", "research", "academia"}

CATEGORY_FOCUS_LABELS = {
    "industry": "产·产业与实践(灯塔工厂/工业互联网/智能制造政策名单/标杆企业与展会)",
    "research": "研·技术与科研(工业大模型/AI质检/预测性维护/机器人/工业软件/论文与成果转化)",
    "academia": "学·学习与成长(专业培养/产教融合/竞赛实训/岗位招聘/学习资源)",
}

# keyword.md 三个章节标题里稳定的定位词（用户改章节副标题也不影响解析）。
# 注意：keyword.md 由用户手工维护（AI 不得编辑），章节是 ### 层级的
# 「第N部分：主题词」结构，定位词必须与用户文件保持一致。
CATEGORY_HEADER_MARKERS = {
    "industry": ("第一部分", "产业与实践"),
    "research": ("第二部分", "科研与技术进展"),
    "academia": ("第三部分", "大学阶段学习"),
}
# 对所有板块都适用的通用小节：拼在每个板块小节之后一起喂给模型。
SHARED_SECTION_MARKERS = ("排除词", "采集偏好")
# 维护指南/组合检索示例是给人看的编辑说明，不进模型上下文。
SKIPPED_SECTION_MARKERS = ("维护指南", "组合检索示例")

# 四维评分默认权重（与 README「智能体核心机制」一致；config.yaml scoring.weights 可覆盖）
DEFAULT_WEIGHTS = {
    "relevance": 0.30,      # 相关性
    "innovation": 0.25,     # 创新性
    "evidence": 0.25,       # 证据强度
    "actionability": 0.20,  # 可行动性
}
WEIGHT_LABELS = {
    "relevance": "相关性",
    "innovation": "创新性",
    "evidence": "证据强度",
    "actionability": "可行动性",
}


@dataclass
class ScoredArticle:
    article: Article
    score: float
    reason: str
    categories: list[str] = field(default_factory=list)
    summary: str = ""
    relevance: float = 0.0
    innovation: float = 0.0
    evidence: float = 0.0
    actionability: float = 0.0
    event_key: str = ""
    related_articles: list[Article] = field(default_factory=list)


def merge_weights(weights: dict | None) -> dict[str, float]:
    """合并默认权重与配置权重，保证四维齐全、和为 1（偏差时按比例归一）。"""
    merged = dict(DEFAULT_WEIGHTS)
    for key in merged:
        try:
            value = float((weights or {}).get(key, merged[key]))
        except (TypeError, ValueError):
            continue
        if 0.0 <= value <= 1.0:
            merged[key] = value
    total = sum(merged.values())
    if total <= 0:
        return dict(DEFAULT_WEIGHTS)
    return {k: v / total for k, v in merged.items()}


def weights_formula(weights: dict[str, float]) -> str:
    """生成给模型看的总分公式字符串，如 0.30*relevance + 0.25*innovation + ..."""
    return " + ".join(f"{w:.2f}*{k}" for k, w in weights.items())


def compute_final_score(
    relevance: float, innovation: float, evidence: float, actionability: float,
    weights: dict | None = None,
) -> float:
    """按四维权重在本地重算总分（不信任模型给的总分）。各维度先钳到 0-10。"""
    w = merge_weights(weights)

    def clamp(v: float) -> float:
        return max(0.0, min(10.0, float(v)))

    return round(
        w["relevance"] * clamp(relevance)
        + w["innovation"] * clamp(innovation)
        + w["evidence"] * clamp(evidence)
        + w["actionability"] * clamp(actionability), 1,
    )


SCORER_SYSTEM = """你是一个新闻相关性评分 + 板块分类助手。评估对象是「智能制造领域（用人工智能赋能新型制造业）的产学研动态」，读者是高校师生：他们要从产业进展、企业项目、技术研究成果中建立岗位认知、工程能力和创新意识。

你将收到一份用户的关注主题说明(keyword.md)，然后是一批待评分的新闻。

主题说明里定义了以下板块,scorer 必须用这些英文 key:
- industry → 产·产业与实践(灯塔工厂/黑灯工厂/工业互联网平台/智能制造政策与名单/标杆企业与展会)
- research → 研·技术与科研(工业大模型/工业智能体/AI质检/预测性维护/数字孪生/机器人/工业软件/论文与成果转化)
- academia → 学·学习与成长(专业与培养动态/产教融合/竞赛与实训/岗位招聘/学习资源与信息源)

任务:
1. 按 keyword.md 描述的关注角度和过滤规则,给每条新闻打 0-10 分相关性:
   - 0-3: 完全无关或属于排除词要排除的内容
   - 4-5: 沾边但价值不高(如标题党、纯软文、旧闻转载)
   - 6-7: 相关且有信息量(如标杆工厂落地案例、技术突破、竞赛/招聘通知、有数据支撑的分析)
   - 8-10: 高度相关、信息密度高、对师生研究/学习目标有直接价值
2. 给每条新闻标记 categories(由上述板块 key 组成的数组,可为空):
   - score >= 4 必须至少标一个板块
   - 跨板块新闻给多个(如"工业大模型在企业质检产线落地" → ["research", "industry"])
   - score < 4 可以给空数组 []

严格按用户的排除词执行——命中排除项的一律给 0-3 分。

返回 JSON 数组,每条对应一篇新闻,顺序与输入一致。每条格式:
{"id": <输入序号>, "score": <0-10 数字,可带一位小数>, "categories": ["industry"|"research"|"academia", ...], "reason": "<不超过30字的中文打分理由>"}

只返回 JSON,不要 markdown 包装,不要任何其他文字。"""


DEDUP_SYSTEM = """你是新闻去重助手。你会收到一批已筛选的新闻,每条含 id、标题、来源、摘要片段。

任务:把【报道同一件事/同一事件】的新闻归为一组。判断依据是**事件本身**(同一份名单发布、同一座工厂入选/投产、同一个产品发布、同一场赛事报名、同一家公司的同一动作),而不是话题相近。

严格要求:
- 只有确实是"同一件事"才合并:必须是**同一主体**(同一家公司/机构/学校/赛事)的**同一个动作或发布**。
- 话题相关但不是同一事件的,**不要**合并。例如:
  · 都谈人形机器人,但一家进厂装配、另一家发布新品 → 不合并;
  · "灯塔工厂名单更新" 与 "某工厂智能改造开工" → 主体与事件不同,不合并;
  · 同一届西门子杯的报名通知与获奖名单,若无新进展 → 合并。
- 同一事件即使标题措辞、语言、来源不同,也要合并。
- 拿不准时不要合并:漏合并只多一条,错合并会丢掉一条有价值的情报。

返回 JSON:{"groups": [[id, id, ...], ...]}
- 每个子数组是一组报道同一事件的 id(至少 2 个)。
- 独立新闻不要列出;没有任何重复时返回 {"groups": []}。

只返回 JSON,不要 markdown 包装,不要任何其他文字。"""


SUMMARIZER_SYSTEM = """你是面向智能制造专业大学生的中文情报摘要助手。你将收到一份用户关注主题说明(keyword.md),然后是若干已被判定为高价值的产学研动态。

请为每条动态写一段 80-150 字的中文摘要,要求:
- 突出具体主体、数据、动作与时间(哪家公司/学校/机构、做了什么、证据是什么)
- 点明该动态与产业实践、技术前沿或学习就业的关联(如:可作为教学案例/岗位技能信号/竞赛参考),没有明确关联就不要硬编
- 不要堆砌形容词,不要复述标题
- 如果原文是英文,直接译写要点;不要保留英文术语除非是专有名词

返回 JSON 数组,每条格式:
{"id": <输入序号>, "summary": "<中文摘要>"}

只返回 JSON,不要 markdown 包装。"""

TREND_SYSTEM = """你是面向高校产学研情报的周度编辑。根据已去重的高价值事件卡片，输出 JSON：
{"trends":["不超过45字的趋势判断",...],"watchlist":["不超过40字的后续观察点",...]}
要求：trends 最多 3 条，watchlist 最多 2 条（如：名单即将公布、报名即将开启、政策细则将出台）；只基于输入事实，不预测、不编造；若信息不足则返回空数组。"""


def research_value_system(weights: dict[str, float]) -> str:
    """按当前权重生成终评 system prompt（公式随配置变化）。"""
    w = merge_weights(weights)
    formula = weights_formula(w)
    return f"""你是产学研情报研究价值终评助手。输入新闻已通过标题/摘要粗筛，现提供尽可能完整的正文。

评估对象是「智能制造领域（用人工智能赋能新型制造业）的产学研动态」，读者是高校师生：他们要从产业进展、企业项目、技术研究成果中建立岗位认知、工程能力和创新意识。

任务：只评估今日指定板块，并为每条新闻输出 0-10 分的四项指标：
- relevance：与该板块及智能制造产学研主题的直接相关程度；
- innovation：是否为新事件/新进展/新突破（转载、旧闻回顾、泛泛评论低分）；
- evidence：是否包含可核验的原始出处、机构、时间、具体政策/产品/数据；
- actionability：是否能支持师生的研究、学习或行动（如竞赛报名、岗位投递、技术跟进、案例教学、实验室选题）。

总 score 必须严格按下式计算并四舍五入到一位小数：
{formula}。
（relevance=相关性、innovation=创新性、evidence=证据强度、actionability=可行动性）

同时输出 event_key：使用小写英文、数字和连字符，稳定表示一个具体事件，不得使用泛泛主题。
例如 lighthouse-factories-2026-batch、siemens-cup-2026-registration、pangu-steel-model-deployment；不同媒体报道同一事件必须给同一 key。
若正文抓取失败，只能依据 preview，evidence 不得高于 5。
来源等级含义：primary=官方机构、标准组织、公司/学校原始发布；trusted=可信媒体或研究机构；discovery=聚合发现线索。primary 可提高证据判断，但不能替代正文事实；discovery 没有原始出处时 evidence 不得高于 5。

返回 JSON 数组，顺序与输入一致：
{{"id": 0, "relevance": 0, "innovation": 0, "evidence": 0, "actionability": 0, "score": 0, "event_key": "...", "reason": "不超过30字中文理由"}}
只返回 JSON，不要 markdown 或解释。"""


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def _split_keyword_sections(keywords_md: str) -> tuple[str, list[str]]:
    """把 keyword.md 切成 (前言, 小节列表)。

    章节可能在 ## 或 ### 层级（keyword.md 由用户手工维护，结构可能调整），
    两种层级都兼容：先按 ## 切，含 ### 小节的块再二次切分，保证不论
    章节是哪级标题，都能按小节标题做板块匹配。
    """
    top = re.split(r"(?=^## )", keywords_md, flags=re.M)
    preamble = top[0]
    sections: list[str] = []
    for block in top[1:]:
        sections.extend(re.split(r"(?=^### )", block, flags=re.M))
    return preamble, sections


def focus_keywords_md(keywords_md: str, category: str) -> str:
    """按当日板块从 keyword.md 中裁出对应章节 + 通用小节。

    keyword.md 按「第N部分」组织产/研/学三块关键词（### 层级，挂在
    「产学研情报采集关键字」总标题下），另有 排除词 与 采集偏好 两个
    通用小节拼在每个板块小节之后一起喂给模型；项目介绍等其余小节是
    给人看的说明，不进模型上下文。
    只把当日章节与通用小节喂给模型，避免其余章节稀释注意力、浪费 token；
    解析不到匹配章节时原样返回全文兜底，绝不因为裁剪逻辑让模型收不到规则。
    """
    preamble, sections = _split_keyword_sections(keywords_md)

    markers = CATEGORY_HEADER_MARKERS.get(category, ())
    matched: list[str] = []
    shared: list[str] = []
    for sec in sections:
        header = _norm(sec.splitlines()[0]) if sec.strip() else ""
        if any(m in header for m in markers):
            matched.append(sec)
        elif any(m in header for m in SHARED_SECTION_MARKERS):
            shared.append(sec)
        # SKIPPED_SECTION_MARKERS 的小节直接丢弃，其余未知小节同样不进上下文

    if not matched:
        return keywords_md
    return preamble + "".join(matched) + "".join(shared)


def _article_to_dict(
    idx: int, a: Article, include_content: bool = False, content_limit: int = 6000,
) -> dict:
    result = {
        "id": idx,
        "title": a.title,
        "source": a.source,
        "source_tier": a.source_tier,
        "url": a.url,
        "preview": a.summary[:400] if a.summary else "",
    }
    if include_content:
        result["content"] = a.content[:content_limit] if a.content else ""
    return result


def _extract_json_array(text: str) -> list:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def score_articles(
    client: openai.OpenAI,
    articles: list[Article],
    keywords_md: str,
    model: str,
    batch_size: int = 20,
    active_category: str | None = None,
) -> list[ScoredArticle]:
    """第一阶段：仅用标题/RSS 摘要粗筛相关性与板块。"""
    if not articles:
        return []

    focus_directive = ""
    if active_category in VALID_CATEGORIES:
        focus_label = CATEGORY_FOCUS_LABELS[active_category]
        focus_directive = (
            f"\n\n【今日聚焦】今天只关心 **{active_category}** 板块 ({focus_label})。"
            f"严格要求:\n"
            f"- 不属于该板块的新闻一律 0-3 分,无论它本身多么相关。\n"
            f'- categories 字段只允许出现 ["{active_category}"] 或空数组 [],不要写其他板块。\n'
            f"- 跨板块的新闻只要主要价值不在 {active_category},也按上面规则给 0-3 分。"
        )

    system_msg = (
        SCORER_SYSTEM + focus_directive
        + f"\n\n以下是用户的关注主题说明:\n\n<keywords>\n{keywords_md}\n</keywords>"
    )
    scored: list[ScoredArticle] = []

    for batch_start in range(0, len(articles), batch_size):
        batch = articles[batch_start : batch_start + batch_size]
        articles_json = json.dumps(
            [_article_to_dict(i, a) for i, a in enumerate(batch)],
            ensure_ascii=False,
            indent=2,
        )

        user_msg = f"以下是本批 {len(batch)} 条新闻(JSON 数组):\n\n{articles_json}\n\n请输出 JSON 数组评分结果。"

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=4000,
                temperature=0.1,
            )
            text = response.choices[0].message.content or ""
        except Exception as e:
            log.error("scorer API error on batch starting %d: %s", batch_start, e)
            for a in batch:
                # 评分失败不能给可入选的默认分，否则会把网络/API 故障
                # 伪装成“相关资讯”。后续流程会自然丢弃 score=0 的条目。
                scored.append(ScoredArticle(article=a, score=0.0, reason="评分失败"))
            continue

        usage = getattr(response, "usage", None)
        log.info(
            "scorer batch %d: input=%d output=%d",
            batch_start // batch_size,
            usage.prompt_tokens if usage else 0,
            usage.completion_tokens if usage else 0,
        )

        try:
            result = _extract_json_array(text)
        except (json.JSONDecodeError, ValueError) as e:
            log.error("scorer returned non-JSON, raw=%r, err=%s", text[:200], e)
            for a in batch:
                scored.append(ScoredArticle(article=a, score=0.0, reason="解析失败"))
            continue

        if not isinstance(result, list):
            log.error("scorer result is not a JSON array: %r", type(result).__name__)
            for a in batch:
                scored.append(ScoredArticle(article=a, score=0.0, reason="结果格式错误"))
            continue
        by_id = {item.get("id"): item for item in result if isinstance(item, dict)}
        for idx, a in enumerate(batch):
            item = by_id.get(idx, {})
            try:
                score = float(item.get("score", 0.0))
            except (TypeError, ValueError):
                score = 0.0
            raw_cats = item.get("categories") or []
            if not isinstance(raw_cats, list):
                raw_cats = []
            seen: set[str] = set()
            cats: list[str] = []
            for c in raw_cats:
                if isinstance(c, str) and c in VALID_CATEGORIES and c not in seen:
                    seen.add(c)
                    cats.append(c)
            if active_category in VALID_CATEGORIES:
                cats = [c for c in cats if c == active_category]
            # 模型声称高分但没有给出当前板块，视为无效结果。这样可以
            # 防止格式漂移或分类缺失绕过 candidates 的 category gate。
            if score >= 4.0 and not cats:
                score = 0.0
            scored.append(ScoredArticle(
                article=a,
                score=max(0.0, min(10.0, score)),
                reason=str(item.get("reason", ""))[:50],
                categories=cats,
            ))

    return scored


def assess_research_value(
    client: openai.OpenAI,
    scored: list[ScoredArticle],
    keywords_md: str,
    model: str,
    active_category: str,
    batch_size: int = 10,
    known_event_keys: list[str] | None = None,
    weights: dict | None = None,
) -> list[ScoredArticle]:
    """第二阶段：基于正文做四维价值终评，并为事件级聚合生成稳定事件键。

    known_event_keys 为近期已推送事件的 key：同一事件复用旧 key，调用方据此跨次去重。
    weights 为四维权重配置（缺省 30/25/25/20）。
    """
    if not scored:
        return scored
    w = merge_weights(weights)
    focus = CATEGORY_FOCUS_LABELS[active_category]
    system_msg = (
        research_value_system(w)
        + f"\n\n【今日板块】{active_category}: {focus}。不属于此板块的条目各项应低分。"
        + f"\n\n用户关注主题：\n<keywords>\n{keywords_md}\n</keywords>"
    )
    if known_event_keys:
        system_msg += (
            "\n\n【近期已推送事件】以下 event_key 对应读者已经读过的事件："
            "若某条新闻报道的是其中同一事件且没有实质性新进展(仅转载、复述、评论)，"
            "必须原样复用该 event_key，并把 innovation 打到 3 分以下；"
            "若有实质性新进展(如名单发布→工厂投产、报名→开赛、试点→全国推广)，使用新的 event_key。\n"
            + "\n".join(known_event_keys)
        )
    for batch_start in range(0, len(scored), batch_size):
        batch = scored[batch_start : batch_start + batch_size]
        articles_json = json.dumps(
            [_article_to_dict(i, s.article, include_content=True) for i, s in enumerate(batch)],
            ensure_ascii=False,
        )
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": f"请终评以下 {len(batch)} 条新闻：\n{articles_json}"},
                ],
                max_tokens=4000,
                temperature=0.0,
            )
            result = _extract_json_array(response.choices[0].message.content or "")
        except Exception as e:
            log.error("research-value API error on batch starting %d: %s", batch_start, e)
            for item in batch:
                item.relevance = item.innovation = item.evidence = item.actionability = 0.0
                item.score = 0.0
                item.event_key = ""
                item.reason = "终评失败"
            continue
        if not isinstance(result, list):
            log.error("research-value result is not a JSON array: %r", type(result).__name__)
            result = []
        by_id = {item.get("id"): item for item in result if isinstance(item, dict)}
        for idx, item in enumerate(batch):
            value = by_id.get(idx)
            if not value:
                item.relevance = item.innovation = item.evidence = item.actionability = 0.0
                item.score = 0.0
                item.event_key = ""
                item.reason = "终评缺失"
                continue

            def metric(name: str) -> float:
                try:
                    return max(0.0, min(10.0, float(value.get(name, 0))))
                except (TypeError, ValueError):
                    return 0.0

            item.relevance = metric("relevance")
            item.innovation = metric("innovation")
            item.evidence = metric("evidence")
            item.actionability = metric("actionability")
            # 这是模型无法可靠推断的事实属性，必须由程序硬限制：没有
            # 抓到正文时只能基于 preview；聚合发现源也不能被当作一手证据。
            if not item.article.content:
                item.evidence = min(item.evidence, 5.0)
            if item.article.source_tier == "discovery":
                item.evidence = min(item.evidence, 5.0)
            # 总分在本地按配置权重重算，避免模型给出的总分与权重不一致。
            item.score = compute_final_score(
                item.relevance, item.innovation, item.evidence, item.actionability, w,
            )
            event_key = str(value.get("event_key", "")).lower().strip()
            item.event_key = re.sub(r"[^a-z0-9-]+", "-", event_key).strip("-")[:100]
            item.reason = str(value.get("reason", item.reason))[:50]
    return scored


def group_by_event(scored: list[ScoredArticle]) -> list[ScoredArticle]:
    """相同 event_key 合并成事件卡片，保留价值最高的主报道。"""
    groups: dict[str, list[ScoredArticle]] = {}
    for item in scored:
        key = item.event_key or f"article-{item.article.uid}"
        groups.setdefault(key, []).append(item)
    grouped: list[ScoredArticle] = []
    for key, items in groups.items():
        primary = max(items, key=lambda s: (s.score, s.evidence, len(s.article.content)))
        primary.event_key = key
        primary.related_articles = [s.article for s in items if s is not primary]
        grouped.append(primary)
    return sorted(grouped, key=lambda s: s.score, reverse=True)


def dedupe_semantic(
    client: openai.OpenAI,
    scored: list[ScoredArticle],
    model: str,
) -> list[ScoredArticle]:
    """语义去重:让模型把"报道同一事件"的文章归组,每组只保留得分最高的一条。

    用于 Google News 这类来源——其 RSS 只给标题没有正文,标题相似度/正文指纹都抓不到
    "同一事件、不同标题"的重复。不补位:去掉的名额不再用其他文章填补。
    失败时(API/解析错误)原样返回,绝不误删。
    """
    if len(scored) < 2:
        return scored

    articles_json = json.dumps(
        [_article_to_dict(i, s.article, include_content=True, content_limit=3000) for i, s in enumerate(scored)],
        ensure_ascii=False,
        indent=2,
    )
    user_msg = f"以下是本批 {len(scored)} 条新闻(JSON 数组):\n\n{articles_json}\n\n请输出去重分组 JSON。"

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": DEDUP_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=1000,
            temperature=0.0,
        )
        text = response.choices[0].message.content or ""
    except Exception as e:
        log.error("dedup API error: %s", e)
        return scored

    try:
        parsed = _extract_json_array(text) if text.strip().startswith("[") else json.loads(
            re.sub(r"\s*```$", "", re.sub(r"^```(?:json)?\s*", "", text.strip()))
        )
    except (json.JSONDecodeError, ValueError) as e:
        log.error("dedup returned non-JSON, raw=%r, err=%s", text[:200], e)
        return scored

    groups = parsed.get("groups") if isinstance(parsed, dict) else parsed
    if not isinstance(groups, list):
        return scored

    drop: set[int] = set()
    for group in groups:
        if not isinstance(group, list):
            continue
        ids = [i for i in group if isinstance(i, int) and 0 <= i < len(scored) and i not in drop]
        if len(ids) < 2:
            continue
        # 保留得分最高的一条(并列时保留摘要片段更长的)
        keep = max(ids, key=lambda i: (scored[i].score, len(scored[i].article.summary)))
        for i in ids:
            if i != keep:
                drop.add(i)
                # event_key 未对齐时仍保留被合并报道，作为事件卡片的参考来源。
                refs = [scored[i].article, *scored[i].related_articles]
                existing = {a.uid for a in scored[keep].related_articles}
                for ref in refs:
                    if ref.uid != scored[keep].article.uid and ref.uid not in existing:
                        scored[keep].related_articles.append(ref)
                        existing.add(ref.uid)
                log.info(
                    "semantic dedup: drop [%s] (same event as [%s])",
                    scored[i].article.title, scored[keep].article.title,
                )

    if drop:
        log.info("dedupe_semantic: removed %d same-event duplicates", len(drop))
    return [s for i, s in enumerate(scored) if i not in drop]


def summarize_top(
    client: openai.OpenAI,
    scored: list[ScoredArticle],
    keywords_md: str,
    model: str,
) -> list[ScoredArticle]:
    if not scored:
        return scored

    articles_json = json.dumps(
        [_article_to_dict(i, s.article, include_content=True, content_limit=3000) for i, s in enumerate(scored)],
        ensure_ascii=False,
        indent=2,
    )

    system_msg = (
        SUMMARIZER_SYSTEM
        + f"\n\n用户关注主题:\n\n<keywords>\n{keywords_md}\n</keywords>"
    )
    user_msg = f"待摘要的 {len(scored)} 条新闻:\n\n{articles_json}\n\n请输出 JSON 摘要结果。"

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=8000,
            temperature=0.2,
        )
        text = response.choices[0].message.content or ""
    except Exception as e:
        log.error("summarizer API error: %s", e)
        return scored

    usage = response.usage
    log.info(
        "summarizer: input=%d output=%d",
        usage.prompt_tokens if usage else 0,
        usage.completion_tokens if usage else 0,
    )

    try:
        result = _extract_json_array(text)
    except (json.JSONDecodeError, ValueError) as e:
        log.error("summarizer returned non-JSON, raw=%r, err=%s", text[:200], e)
        return scored

    by_id = {item.get("id"): item.get("summary", "") for item in result if isinstance(item, dict)}
    for idx, s in enumerate(scored):
        s.summary = str(by_id.get(idx, ""))[:400]
    return scored


def summarize_weekly_insights(
    client: openai.OpenAI, scored: list[ScoredArticle], model: str,
) -> tuple[list[str], list[str]]:
    """从事件卡片中提炼本周趋势和待跟踪事项；失败时不影响情报推送。"""
    if not scored:
        return [], []
    payload = [
        {
            "title": s.article.title, "summary": s.summary or s.article.summary[:500],
            "score": s.score, "evidence": s.evidence, "source_tier": s.article.source_tier,
        }
        for s in scored
    ]
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": TREND_SYSTEM},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            max_tokens=800,
            temperature=0.1,
        )
        data = json.loads(response.choices[0].message.content or "{}")
        trends = [str(x)[:80] for x in data.get("trends", []) if isinstance(x, str)][:3]
        watchlist = [str(x)[:80] for x in data.get("watchlist", []) if isinstance(x, str)][:2]
        return trends, watchlist
    except Exception as e:
        log.warning("weekly insights unavailable: %s", e)
        return [], []
