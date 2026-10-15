# Day 29 · 项目一首次访问验收与版本冻结

来源：`Agent开发_60天每日打卡_修订版.xlsx` — 第 29 天，项目一验收。

**严格验收**：无痕浏览器演示 5 个预置任务；修复崩溃/错误引用/无法复现等首次体验问题中最重要的一项；保留演示账号、访问说明、已知失败、日志及冻结标签。Day 30 才正式发布 v1.0。

## 原因、修复范围与冻结基线

Day 27 冻结留出集自动 17/20，三个失败：H05「发货政策」错误意图，H18/H19「退货/保修例外」未转人工。**本次只修复一个根因：H18/H19 同一类政策例外缺少人工转接分支。** 不擅自把评分更新为 19/20，不重跑或覆盖 Day 27 的 `holdout.json` 和 `human_review.csv`。

修改涉及 `shopmate_graph.py` 的有限意图路由、`stream_api.py` 对新的 handoff 安全结束事件的处理、原有 Day 25 演示页面新增两个按钮，以及 README/历史演示文档和离线 CI 更新。**不创建真实人工工单**；只提示联系人工处理，也不自动批准退款或例外。

## 1. 安装（Windows PowerShell）

把 ZIP 解压到 `E:\shopmate\shopmate-agent`（不要额外多套一层目录）。先检查当前已知良好的版本：

```powershell
cd E:\shopmate\shopmate-agent
git status --short
# 保留已验收 Day 28 的正式恢复点（如果 tag 已存在，请不要重复创建）
git tag day28-verified
uv run python scripts/apply_day29.py --check
uv run python scripts/apply_day29.py
uv run python -m pytest tests/test_day29_acceptance.py -v
uv run python -m pytest -q
```

`apply_day29.py` 根据精确源码锚点执行小范围修改；先验证所有锚点，缺失则退出；重复运行可跳过已安装补丁。原版本有未提交的重要修改时先提交/备份，避免混合修改。

## 2. 重新构建现有容器（保留数据与隧道）

Day 29 **没有新的 Compose 文件**，仍用 Day 24/25/26 已验收的组合：

```powershell
docker compose -f compose.yaml -f compose.day25.yaml -f compose.day26.yaml up -d --build
docker compose -f compose.yaml -f compose.day25.yaml -f compose.day26.yaml ps
curl.exe -i http://127.0.0.1:8000/health/live
curl.exe -i http://127.0.0.1:8000/health/ready
```

浏览器打开 `http://127.0.0.1:8080`；若 Windows ngrok 仍在线，可沿用原公网 HTTPS URL；不要重复启动同一 ngrok 端点。**不要运行 `docker compose down -v`，不要复制公开演示密码或 Token 到 GitHub。**

## 3. 无痕浏览器：五个预置任务

用浏览器无痕窗口登录本地预览账号 `preview`（密码为自己设置的 `.env.day25` 凭据）：

| ID | 点击按钮 | 应观察到什么 |
|---|---|---|
| S01 | 退货政策 | 政策引用 `policy-returns`、检索事件、回答增量、完成事件 |
| S02 | 商品价格 | SQLite `P001` 演示价格及引用 `db:products:P001`；真实业务不得信任示例价格 |
| S03 | 匿名订单拒答 | 不泄露 `ORD001` 的私有状态，没有 `db:orders` 引用 |
| S04 | 政策例外转人工 | 明确需要人工核实，不承诺批准，不能假称“已创建人工工单” |
| S05 | 信息不足先澄清 | 要求补充上下文，不猜测价格或订单详情 |

再在手机蜂窝网络或第二台设备核对 HTTPS 入口仍能访问。因使用的是免费 ngrok，本机/隧道断开后公网 URL 可能失效，不承诺永久在线。

## 4. 自动化 5 项真实 HTTP/SSE 冒烟

在 PowerShell，确认 8000 端口只有本机可访问，然后：

```powershell
uv run python scripts/smoke_day29.py --output reports/day29/smoke.json
Get-Content .\reports\day29\smoke.json -Raw
```

**验收需 `5/5 PASS`**。脚本顺序请求真实 App，不依赖 ngrok，真实解析 SSE `start`、`answer_delta`、`complete`，检查引用/安全拒答/人工转接/澄清；记录完成情况、版本实现 SHA-256、错误案例。不计为 LLM 测试或压力测试。

如果失败，先看本地 `/health/ready`、App 日志、`git diff`；不要重新安装 Docker、重建 SQLite 或删除卷。

## 5. 已知问题与 Bug 优先级

- **P0（阻止演示）**：应用崩溃、账号无法登录、任意私有订单泄露、文档引用伪造、无法启动；优先回滚。
- **P1（本次修复）**：政策例外返回普通政策、无法转人工；H18/H19 的同类根因。
- **P2（仍公开记录）**：H05「现在的发货政策是什么？」仍可能被分类为澄清，而非配送政策。**不改动旧留出集，不声称全部问题已解决**。

对齐 Day 27：**17/20 是 Day 27 旧版留出集的事实**，Day 29 的 5/5 是不同样本的上线冒烟结果，两者不能直接相加或替代。

## 6. 版本冻结、GitHub 与回滚

先检查变更及敏感信息。Day 29 当前文件除文档、源码、测试、报告外不应改动业务数据库及 `data/index/chunks.npz`。

```powershell
git diff --check
git status --short
# 确保以下两个都是真实结果：pytest 全部通过、smoke.json 5/5

git add src/shopmate_agent/shopmate_graph.py src/shopmate_agent/stream_api.py web/day25.html README.md docs/day28_demo.md .github/workflows/offline-ci.yml docs/day29_acceptance.md scripts/apply_day29.py scripts/smoke_day29.py tests/test_day29_acceptance.py reports/day29/smoke.json
git commit -m "fix: hand off policy exceptions and freeze five-task first-visit smoke"
git push origin main
```

**确认新提交的 GitHub Actions 为绿色后**，再标记冻结版本：

```powershell
git tag -a shopmate-day29-freeze -m "Day29 reviewed five-task demo and handoff fix"
git push origin shopmate-day29-freeze
```

需要恢复 Day 28 时：停 ngrok（如有）、在演示空闲时将代码切回 `day28-verified`，然后使用同样三份 Compose 文件 `up -d --build`。**不要删除数据卷、不要在有未提交改动时直接强制 checkout。** 恢复到 main 时再重建，确保最终网页和代码来自同一版本。

## Day 29 面试题

> 面试官第一次访问，怎样最快看到项目的核心能力？

推荐从“30 秒 README 价值表 → 2 分钟无痕演示政策依据/商品工具/匿名拒答/转人工 → 30 秒展示真实指标、已知缺陷和可复现版本”回答。快速部署、日志与重启/回滚要能现场找到。
