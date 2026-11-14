# 微信小程序运行说明

本次增加独立的小程序内容管线，不改变原 PushPlus 排期。keyword.md 只读，由人维护。

## 采集真实内容

```bash
source .venv/bin/activate
export DEEPSEEK_API_KEY=你的密钥
python -m cxy_agent.catalog --plan
python -m cxy_agent.catalog
# 首次联调可限制为每类两个关键词：
python -m cxy_agent.catalog --limit 2
```

默认检索全部44组关键词，范围取自 keyword.md（当前30天）。Google News RSS 检索需要网络可达；API故障会中止并保留旧目录。按排除词过滤、正文补抓、模型四维评估后，以相关性30%、新颖性30%、可实践性40%重算分数，达到6分才收录，每类最多20个事件。证据评分独立展示。摘要失败时回退来源摘要。每次采集替换当前目录，不提供历史归档。无结果时展示空状态，不生成虚构内容。

产物为 data/catalog.json。搜索基于关键词组的同义词 OR 组合；关键词文件保存后下次采集生效。Google搜索渠道故障不等于没有新闻，请检查采集日志。

## 本地预览

```bash
python -m cxy_agent.api
```

微信开发者工具导入 miniprogram 文件夹，使用测试号或自己的 AppID。开发配置使用 touristappid，默认读取采集时打包的 miniprogram/data/catalog.js，可直接预览。需要在线更新时，将 app.js 的 apiBase 改为 http://127.0.0.1:8787（本地联调）或实际 HTTPS 域名。域名校验仅为本地调试关闭。首页提供产研学分类、文本搜索、下拉刷新；详情提供摘要、来源、评分、同事件参考来源、复制原文链接和本机收藏。

收藏只保存在当前设备，不提供登录同步。原文采用复制链接，避免未配置业务域名时直接嵌入外部网页。

## 正式发布

1. 使用实际小程序 AppID，并开启域名校验。
2. 将 data/catalog.json 部署至 HTTPS 服务（例如静态服务暴露 /api/catalog），或将只读API置于生产HTTPS网关后；内置 http.server 仅供本地开发。
3. 在 app.js 配置 apiBase，在微信后台设置 request 合法域名。
4. 服务器定时运行 python -m cxy_agent.catalog，成功后原子替换目录；建议先手动采集验证网络和模型配额。
5. 使用微信开发者工具预览、真机测试、上传并提交微信审核。

本仓库不包含 AppSecret，模型密钥仅在采集端环境变量中。正式发布需要账号、域名及微信审核。

小程序显示名称已设为“数智产学研”；微信平台上的正式名称仍需在对应账号后台登记。内置数据随重新构建更新，线上动态更新需配置 apiBase。

## 用户按兴趣主动检索

首页选择兴趣后点击「智能体开始工作」。小程序 POST /api/tasks（interests 为关键词数组），每3秒 GET /api/tasks/{id} 查询任务；完成后在首页显示本次真实检索结果，支持详情和收藏。后端复用新闻检索、排除词过滤、模型评分、摘要流程，不修改公共目录、不发送 PushPlus。

启动：`.venv/bin/python -m cxy_agent.api`，服务器环境须配置 DEEPSEEK_API_KEY。任务保存在内存中，重启失效，完成后保留约1小时；最多并发2个任务，繁忙时返回429。内置 HTTP 服务用于开发，正式服务需在 HTTPS 网关后运行，并在网关配置访问控制、限流和请求超时。Google News 网络与模型服务必须可达。

体验版联调必须把 miniprogram/app.js 的 apiBase 设置为实际 HTTPS 后端地址，在微信后台配置 request 合法域名，再上传新版本。手机不能访问开发电脑的127.0.0.1。未配置 apiBase 时按钮会明确提示，不会以公共目录冒充检索结果。
