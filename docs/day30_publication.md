# Day 30 — ShopMate v1.0 正式发布与项目一总结

原始 Excel 第 30 天：**项目一选型复盘（客服价值、成本、边界与剩余风险）；发布 shopmate-agent v1.0；公开仓库 + 线上 URL + 评测报告；验证重启和回滚；完整演示并检查网页与代码版本；5 分钟介绍 + 5 分钟追问。**

## 一、范围约束（不要重做 Day 24～29）

- 当前源码以 `shopmate-day29-freeze` 对应的代码为发布基线。
- **不修改原有 Agent / Docker Compose / 数据库 / 30×512 索引**；新内容只有发布核对脚本、离线单测、发布清单及发布说明。
- 不覆盖 Day 27 冻结报告；当前自动留出 17/20。Day29 修复 H18/H19 的人工转接提示，不证明重新计算后的 20 题变为 19/20。
- `README.md`、MIT LICENSE、第三方声明和架构图已经在 Day 28 做过；只引用，不重新编写。

## 二、Windows PowerShell 执行（第一次使用）

将 DAY30 ZIP 解压到项目根目录，**不要带额外的子文件夹层级**。先确认 Git 工作区无无关改动：

```powershell
cd E:\shopmate\shopmate-agent
git status --short
git tag --list shopmate-day29-freeze
uv run python -m pytest tests/test_day30_release.py -v
uv run python -m pytest -q
```

### 1. 检查服务重启与真实 SSE

仅在没有真实演示访客时执行以下重启。**不要执行 `docker compose down -v`**，也无需重新 pull Python 镜像。

```powershell
docker compose -f compose.yaml -f compose.day25.yaml -f compose.day26.yaml restart app
docker compose -f compose.yaml -f compose.day25.yaml -f compose.day26.yaml ps
curl.exe -i http://127.0.0.1:8000/health/ready
uv run python scripts/smoke_day29.py --output reports/day30/restart_smoke.json
```

要求 HTTP `/health/ready` 为 200，重启后 5/5；检查 `reports/day30/restart_smoke.json` 的 `implementation_sha256` 与 Day29 原报告完全一致，才表示应用逻辑与已冻结代码一致。

### 2. 验证回滚路径（非破坏性）

不对在线数据库做变更；先查看冻结与主分支的业务源码差异：

```powershell
git diff shopmate-day29-freeze main -- src/shopmate_agent/ web/ compose.yaml compose.day25.yaml compose.day26.yaml
```

**如果这里没有输出，说明 Day30 没改动运行时源码；版本回滚只需回到已知良好的 Day29 Tag。** 如果需要一次实际回滚演练，仅在保存/提交当前修改、确保演示无人访问后进行：

```powershell
git switch --detach shopmate-day29-freeze
docker compose -f compose.yaml -f compose.day25.yaml -f compose.day26.yaml up -d --build
curl.exe -i http://127.0.0.1:8000/health/ready
uv run python scripts/smoke_day29.py --output reports/day29/rollback-verification.json
# 恢复准备发布的主分支
git switch main
docker compose -f compose.yaml -f compose.day25.yaml -f compose.day26.yaml up -d --build
```

实际回滚会暂时中断演示，且 `--build` 在 Docker Hub 网络不通时可能失败：应先完成无破坏的 `git diff` 验证，并根据当前本机镜像和网络情况安排真正回滚。不要删数据卷，不要在有未保存改动时强制切换。

### 3. 获得当前公网 HTTPS 入口

ngrok 已在 Windows 上配置过时，不要再启动第二个同名 endpoint：

```powershell
curl.exe -s http://127.0.0.1:4040/api/tunnels
```

取 JSON 中 `public_url`；应该指向 `localhost:8080`。如果没有在线隧道，再通过已配置 ngrok 的客户端启动 `ngrok http 8080`。用**手机蜂窝网络、无痕模式**实测登录、政策引用、商品工具、匿名查单拒答、政策例外提示。不要把 Basic Auth 密码、Token 或 `http://127.0.0.1` 作为公网 URL。

### 4. 生成正式清单

将 URL 替换成你**当前实际可访问**的 HTTPS 地址，不能直接照抄示例：

```powershell
uv run python scripts/check_day30_release.py --demo-url "https://你的实际-ngrok-域名" --output reports/day30/release_manifest.json
Get-Content .\reports\day30\release_manifest.json -Raw
```

这个脚本会检查 Day 27 历史分数/失败 ID，Day 29 五任务及源码指纹，Day 26 过载数据，README 真实边界，最终记录报告 SHA-256 和 URL。**它不会连接公网、验证 CI 或发布 GitHub Release；这些仍需人工完成。**

## 三、提交、CI、Release

```powershell
git add scripts/check_day30_release.py tests/test_day30_release.py docs/day30_publication.md docs/day30_release_notes.md reports/day30/release_manifest.json reports/day30/restart_smoke.json
git diff --cached --check
git commit -m "release: prepare ShopMate v1.0 evidence and retrospective"
git push origin main
```

如果 `restart_smoke.json` 尚未生成，把它从 `git add` 中去掉并先完成重启验证。**绝不要把 Token/密码放到仓库。** 推送后在 GitHub Actions 等待当前 commit 的绿色 CI。然后：

```powershell
# 确认本地 HEAD 就是 CI 绿色通过的 main
git status --short
git log -1 --oneline
# 不要在 CI 失败时创建正式发布 Tag
git tag -a v1.0.0 -m "ShopMate Agent v1.0 release"
git push origin v1.0.0
```

访问 https://github.com/theark-coder/shopmate-agent/releases/new ：Tag 选 `v1.0.0`；标题 `ShopMate Agent v1.0`；正文使用 `docs/day30_release_notes.md` 的内容并补充**当前 HTTPS URL**。点击 **Publish release**。检查公开仓库、Release、Day27/Day29 报告链接、README 版本与发布 Tag 的源码一致。

> 仅创建 git tag **不等于**发布 GitHub Release。用户需在网页点击 `Publish release`，或使用已安装且登录的 `gh release create`。发布后提供 Release 页面 URL 供验收。

## 四、技术选型复盘与风险分级

| 维度 | 本版结论 |
| --- | --- |
| 客服价值 | 价格库存查询、政策引用、匿名订单拒答、政策例外安全转人工提示 |
| 选型 | FastAPI 做服务、LangGraph 做可观察路由、SQLite 做演示业务库、SSE 做增量展示、Compose 做复现 |
| pgvector | 30×512 向量持久化/离线检索实验，当前实时问答不依赖在线 pgvector 检索 |
| 成本 | 模型 API 调用数 0（当前规则式回答）、Token 不适用；未测总云费与人工运维，不应写“0 成本” |
| P0 | 真实权限泄露、关键接口崩溃、引用造假、部署失败：阻止发布并回滚 |
| P1 | 政策例外错误承诺/不转人工；Day29 添加了安全提示，但不等于工单系统 |
| P2 | H05 发货政策识别仍失败；后续可扩大意图覆盖并在**新**评测集上验证 |
| 演示环境 | ngrok 免费开发域名 + Windows 本机持续在线；不具备生产可用性 SLA |

## 五、10 分钟模拟面试提纲（5 分钟介绍 + 5 分钟追问）

**5 分钟介绍：** 00:00-00:45 业务痛点和客服价值；00:45-01:45 图架构及路由；01:45-03:20 现场演示政策/商品/匿名订单/转人工/SSE；03:20-04:20 17/20 留出、5/5 冒烟、90% 过载失败率和局限；04:20-05:00 复现命令与回滚方式。

**5 分钟追问（需回答）：**
1. 商品问题：为什么调用 SQLite 价格/库存工具，而不是直接检索文档或让模型猜？
2. 政策问题：如何给出文档版本、来源，以及不能自动批准例外的理由？
3. 订单问题：为什么必须使用服务端身份、owner 校验、商家隔离？匿名为什么只能拒答？
4. 演示中有 pgvector，为什么当前不用于在线问答？真实性如何表述？
5. 20 并发有 90% 503，应该如何分阶段扩容、避免无限排队？

## Day30 验收

- 本地 `pytest`（新增与全量）均通过；清单 PASS 并生成报告，GitHub 提交。
- 最新 `main` Actions 绿色；版本 `v1.0.0` Tag 与 GitHub Release 同时可见。
- `README`、Release 与报告公开，线上 HTTPS 在第二设备实际可访问；演示账号正常。
- `/health/ready` 重启后为 200；5/5 HTTP/SSE；回滚验证有证据；版本指纹一致。
- 面试介绍 + 三类业务路由追问完整，明确 Demo 的合成数据范围及未测成本。
