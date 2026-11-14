"""关键词驱动的小程序内容构建器；不发送微信消息。"""
import argparse
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
import openai
from agent.keyword_parser import load_config
from . import sources
from . import filter as scoring

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / 'data/catalog.json'
# 本地后端配置；已有服务器环境变量优先，不执行文件中的任何代码。
_env_file = ROOT / '.env'
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _name, _sep, _value = _line.partition('=')
        if _sep and _name.strip() == 'DEEPSEEK_API_KEY':
            os.environ.setdefault('DEEPSEEK_API_KEY', _value.strip().strip('\"').strip("'"))
LABELS = {'industry': '产 · 产业实践', 'research': '研 · 技术前沿', 'academia': '学 · 学习成长'}


def plan():
    cfg = load_config(ROOT / 'keyword.md')
    groups = {'industry': cfg.industry_events, 'research': cfg.research, 'academia': cfg.academia}
    return cfg, groups


def collect(limit=None, interests=None, persist=True):
    cfg, groups = plan()
    if interests is not None:
        from copy import copy
        filtered = {}
        for category, words in groups.items():
            chosen = []
            for word in words:
                terms = [t.split('：', 1)[-1] for t in word.terms if t.split('：', 1)[-1] in interests]
                if terms:
                    item = copy(word)
                    item.terms = terms
                    chosen.append(item)
            if chosen:
                filtered[category] = chosen
        groups = filtered
        if not groups:
            raise ValueError('请选择有效关键词')
    key = os.environ.get('DEEPSEEK_API_KEY')
    if not key:
        raise RuntimeError('请设置 DEEPSEEK_API_KEY；不会用演示内容替代真实情报')
    client = openai.OpenAI(api_key=key, base_url='https://api.deepseek.com', timeout=90)
    keywords = (ROOT / 'keyword.md').read_text()
    cards = []
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
    stats = {}
    for category, words in groups.items():
        selected = sorted(words, key=lambda k: -k.priority)
        if limit:
            selected = selected[:limit]
        print(f'开始采集 {LABELS[category]}：{len(selected)} 组关键词', flush=True)
        queries = [' OR '.join('"' + t.replace('"', '') + '"' for t in k.terms) for k in selected]
        raw = sources.fetch_google_news(queries, max_per_query=8, days=cfg.days)
        raw = sources.dedupe_by_content(sources.dedupe(sources.filter_by_age(raw, cfg.days*24, drop_undated=True)))
        raw = [a for a in raw if not any(t.lower() in (a.title+' '+a.summary).lower() for t in cfg.exclusions)]
        focused = scoring.focus_keywords_md(keywords, category)
        if interests is not None:
            focused = '用户本次关注关键词：' + '、'.join(t for k in selected for t in k.terms) + '\n仅保留与这些关键词相关的内容。\n' + focused
        coarse = scoring.score_articles(client, raw, focused, 'deepseek-chat', active_category=category)
        if any(s.reason in ('评分失败', '解析失败', '结果格式错误') for s in coarse):
            raise RuntimeError('粗筛失败，保留上次内容，请重试')
        candidates = sorted([s for s in coarse if s.score >= 4 and category in s.categories], key=lambda s: -s.score)[:40]
        sources.fetch_article_bodies([s.article for s in candidates], max_workers=8, max_chars=6000)
        assessed = scoring.assess_research_value(client, candidates, focused, 'deepseek-chat', category)
        if any(s.reason in ('终评失败', '终评缺失') for s in assessed):
            raise RuntimeError('终评失败，保留上次内容，请重试')
        # keyword.md 指定：相关性30%、新颖性30%、可实践性40%。证据仍单独展示。
        for s in assessed:
            s.score = round(s.relevance*.3+s.innovation*.3+s.actionability*.4, 2)
        top = scoring.group_by_event([s for s in assessed if s.score >= 6])[:20]
        top = scoring.summarize_top(client, top, focused, 'deepseek-chat')
        stats[category] = {'fetched': len(raw), 'selected': len(top)}
        for s in top:
            a = s.article
            cards.append({'id': a.uid, 'title': a.title, 'category': category, 'categoryLabel': LABELS[category],
                          'summary': s.summary or a.summary, 'source': a.source, 'url': a.url,
                          'date': a.published_at.isoformat()[:10] if a.published_at else '', 'score': s.score,
                          'evidence': s.evidence, 'priority': max((k.priority for k in words if any(t.lower() in (a.title+' '+a.summary).lower() for t in k.terms)), default=1),
                          'references': [{'title': r.title, 'url': r.url} for r in s.related_articles]})
    result = {'updatedAt': datetime.now(timezone.utc).astimezone().isoformat(), 'days': cfg.days, 'stats': stats,
              'keywords': {c: [{'label': k.label, 'priority': k.priority} for k in ks] for c, ks in groups.items()}, 'items': cards}
    if not persist:
        return result
    CATALOG.parent.mkdir(exist_ok=True)
    temp = CATALOG.with_suffix('.tmp')
    temp.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    temp.replace(CATALOG)
    bundled = ROOT / 'miniprogram/data/catalog.js'
    bundled.parent.mkdir(parents=True, exist_ok=True)
    bundled.write_text('module.exports = ' + json.dumps(result, ensure_ascii=False) + '\n')
    print(f'已更新 {len(cards)} 条真实情报：{CATALOG}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', action='store_true')
    parser.add_argument('--limit', type=int, help='每类最多检索多少条关键词；默认全部')
    args = parser.parse_args()
    if args.plan:
        cfg, groups = plan()
        print(json.dumps({'days': cfg.days, 'keywords': {c: [k.label for k in ks] for c, ks in groups.items()}}, ensure_ascii=False, indent=2))
    else:
        if args.limit is not None and args.limit < 1:
            parser.error('--limit 必须大于0')
        collect(args.limit)
