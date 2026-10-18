# CXY-Agent 定时采集执行手册

> 本手册供 Kimi Work 定时任务（local_conversation）每次运行时阅读并严格执行。
> 目标：无人工干预的产学研情报闭环采集。

## 每次运行的标准流程

1. **拉取最新配置**
   - 优先用 GitHub 插件的 `get_file_contents`（owner=`yuan2007-intelligence`，
     repo=`CXY-Agent`，path=`keyword.md`）获取最新版，写入本项目目录下的
     `keyword.md`（覆盖旧文件）；
   - 插件不可用时，改用 `FetchURL` 获取
     `https://raw.githubusercontent.com/yuan2007-intelligence/CXY-Agent/main/keyword.md`。
2. **生成检索计划**
   - 运行 `python -m agent plan keyword.md`，得到按产 / 学 / 研 / 政策分类的
     查询清单及各自的时间范围（近 N 天）。
3. **逐条检索**
   - 对计划中的每条查询调用 `WebSearch`，使用查询自带的时间过滤（对应 `days`），
     中文查询为主，★★★ 关键字的查询可追加一条英文对照查询。
   - 每条查询保留 3~5 条候选，记录：标题、URL、摘要、来源、发布日期、类别。
4. **过滤与评分**
   - 严格丢弃命中「七、排除词」的条目。
   - 按相关性 30% / 时效性 40% / 来源权威度 30% 打分排序
     （实现见 `agent/scoring.py`，可用 `python -c` 调用，也可按同一口径手工评分）。
5. **产出日报**
   - 用 `agent/report.py` 的口径生成中文 Markdown，写入
     `reports/YYYY-MM-DD.md`（YYYY-MM-DD 为运行当天日期）。
   - 同时在会话中输出 5~8 条最有价值情报的要点摘要（一行一条）。

## 质量红线

- 禁止编造情报：每条收录必须有真实检索结果支撑，URL 可点开核验；
- 排除词命中即弃，不做例外；
- 单期日报收录上限 20 条，宁精勿滥；
- 若某类别本期检索无有效结果，日报中如实标注「本期无收录」。

## 异常处理

- `keyword.md` 拉取失败：使用本地已有副本并在日报开头注明；
- 检索工具不可用：记录失败查询清单到 `reports/` 同名文件末尾，正常结束本次运行。
