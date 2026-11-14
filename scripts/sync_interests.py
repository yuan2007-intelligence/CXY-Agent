"""从人工维护的 keyword.md 生成小程序兴趣选项；不修改源文档。"""
import json
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
groups = []
group = None
for line in (root / 'keyword.md').read_text().splitlines():
    if line.startswith('### '):
        category = next((key for marker, key in [('第一部分', 'industry'), ('第二部分', 'research'), ('第三部分', 'academia')] if marker in line), None)
        group = {'id': category, 'name': {'industry': '产 · 产业与实践', 'research': '研 · 科研与技术', 'academia': '学 · 学习与成长'}.get(category), 'options': []} if category else None
        if group:
            groups.append(group)
    elif line.strip().startswith('- ') and groups and group:
        label = re.sub(r'\s*★+\s*$', '', line.strip()[2:]).strip()
        # 冒号前为条目说明，其后的并列关键词各自成为选项。
        keywords = label.split('：', 1)[-1]
        for keyword in re.split('[、]', keywords):
            keyword = keyword.strip()
            if keyword and not any(o['id'] == keyword for o in group['options']):
                group['options'].append({'id': keyword, 'label': keyword, 'terms': [keyword]})
(root / 'miniprogram/data/interests.js').write_text('module.exports = ' + json.dumps(groups, ensure_ascii=False, indent=2) + '\n')
