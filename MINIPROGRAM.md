# 小程序每周信息汇总

## 工作方式

GitHub Actions 的 Weekly mini program catalog 工作流每周一北京时间06:00（UTC周日22:00）开始采集，也可手动 Run workflow。使用仓库 Secret DEEPSEEK_API_KEY，按人工维护的 keyword.md 全部关键词检索近7天新闻，去重、过滤排除词、评分并整理摘要。keyword.md 不会被程序修改。每个查询最多取8条搜索结果，周报不再限制每类40条候选或20条结果；保留质量分达到6分的信息。“全部关键词”不代表互联网全部信息。

采集成功才替换 data/catalog.json 和打包数据 miniprogram/data/catalog.js，失败保留上一期。通过 GitHub Pages 发布 catalog.json。小程序打开或下拉刷新读取最新汇总，关键词选择只在本机过滤，不触发实时检索，不需要云函数、GitHub Token或用户密钥。原 PushPlus 排期不变。

## 一次性配置

1. 推送代码后，在仓库 Settings → Pages → Build and deployment → Source 选择 GitHub Actions。
2. 确认 Settings → Secrets and variables → Actions 中已有 DEEPSEEK_API_KEY。
3. 在 Actions 手动运行 Weekly mini program catalog，等采集和 deploy 均成功。
4. 验证 https://yuan2007-intelligence.github.io/CXY-Agent/catalog.json 能返回JSON。
5. 微信公众平台 → 开发管理 → 开发设置 → 服务器域名 → request合法域名，添加 https://yuan2007-intelligence.github.io 。如微信不允许该域名或手机网络无法访问，需换用微信允许且手机可访问的静态托管域名，并修改 app.js 的 catalogUrl。
6. 开发者工具真机验证后，上传新体验版。

GitHub Actions 定时任务可能排队延迟，06:00是计划启动时间，并非汇总完成时间。GitHub Pages可访问性与微信域名配置需要真机验证。

## 本地验证

```bash
.venv/bin/python -m cxy_agent.catalog --weekly
python3 scripts/sync_interests.py
.venv/bin/python -m unittest discover -s tests -q
```

选择兴趣后显示任意一个所选词匹配的内容；支持标题、摘要与采集正文命中的关键词。选择保存在当前设备，可在首页兴趣设置中修改或清空。未选择时显示全部。收藏也仅保存在当前设备。
