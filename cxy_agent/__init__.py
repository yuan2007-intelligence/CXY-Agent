"""数智学研智能体（CXY-Agent）：智能制造领域产学研情报的采集、评估与推送。

管线：RSS / Google News / RSSHub 发现 → 时间与去重过滤 → DeepSeek 粗筛 →
正文抓取 + 指纹去重 → 四维价值终评（相关性/创新性/证据强度/可行动性）+
event_key 事件聚合 → 中文摘要 → Markdown 落盘 + PushPlus 微信推送。
"""
__version__ = "0.1.0"
