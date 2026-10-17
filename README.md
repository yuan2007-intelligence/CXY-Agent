# CXY-Agent · 数智学研智能体

产学研情报闭环采集智能体：每次采集时读取仓库根目录的 [`keyword.md`](./keyword.md)，
将关键字注入检索上下文，自动完成「检索 → 过滤 → 评分 → 日报」全流程，
实现无人工干预的闭环采集。用户只需维护 `keyword.md`，编辑保存后下次采集自动生效。

## 工作原理

```
keyword.md（用户维护）
      │ 每次采集时拉取最新版
      ▼
agent/keyword_parser.py   解析领域/产/学/研/政策关键字、排除词、采集偏好
      ▼
agent/queries.py          展开为检索计划（主体词 × 事件词，按优先级配额）
      ▼
采集层（Kimi Work 定时任务） 按计划逐条检索，收集候选情报条目
      ▼
agent/scoring.py          排除词过滤 + 三因子评分（相关性 30% / 时效 40% / 来源 30%）
      ▼
agent/report.py           生成中文 Markdown 情报日报 → reports/
```

## 目录结构

```
├── keyword.md        # 检索配置（用户直接维护，唯一需要动的文件）
├── agent/            # 核心库：解析 / 查询 / 评分 / 报告
├── AUTOMATION.md     # 定时采集任务执行手册（智能体每次运行时阅读）
└── reports/          # 产出的情报日报（按日期归档）
```

## 本地自检

```bash
python -m agent summary   # 解析配置并打印摘要
python -m agent plan      # 打印本次采集的检索计划
```

## 闭环运行

由 Kimi Work 定时任务驱动，详见 [AUTOMATION.md](./AUTOMATION.md)。
任务每次运行时：拉取最新 `keyword.md` → 生成检索计划 → 逐条检索近 7 天情报 →
排除词过滤 → 评分排序 → 输出 `reports/YYYY-MM-DD.md` 并在会话中给出要点摘要。

## 维护关键字

见 `keyword.md` 第一节「维护指南」。要点：

- 新增：在对应分类下以 `- ` 开头另起一行；同义词用 `、` 分隔；
- 优先级：行尾加 ★（★★★ 核心必采 / ★★ 重要 / ★ 一般）；
- 屏蔽：把不想看到的词写入「七、排除词」，命中即丢弃；
- 保留所有 `##` / `###` 标题与列表格式，解析器依赖该结构。

## License

MIT（见 LICENSE）
