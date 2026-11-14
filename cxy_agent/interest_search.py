"""GitHub Actions 按用户兴趣检索，将结果写入任务独立的 artifact。"""
import json
import os
from pathlib import Path
from .catalog import collect, plan


def main():
    interests = json.loads(os.environ['SEARCH_INTERESTS'])
    _, groups = plan()
    allowed = {t.split('：', 1)[-1] for words in groups.values() for word in words for t in word.terms}
    if not isinstance(interests, list) or not 1 <= len(interests) <= 100 or any(not isinstance(t, str) or t not in allowed for t in interests):
        raise ValueError('请选择有效关键词')
    result = collect(interests=list(dict.fromkeys(interests)), persist=False)
    Path('interest-result.json').write_text(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
