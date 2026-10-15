# ShopMate Agent — 可复现的 AI Agent 工程演示

[![Offline CI](https://github.com/theark-coder/shopmate-agent/actions/workflows/offline-ci.yml/badge.svg)](https://github.com/theark-coder/shopmate-agent/actions/workflows/offline-ci.yml)

面向电商客服的 **FastAPI + LangGraph** 演示工程，覆盖商品查询、政策依据、订单权限隔离、SSE 进度、Docker/pgvector 持久化、HTTPS 预览、限流、离线评测。

> **能力边界**：当前在线演示的回答由 **规则式 LangGraph** 生成，并**没有调用在线 LLM**。`BAAI/bge-small-zh-v1.5` 的 512 维向量用于离线索引实验和 pgvector 演示；当前客服回答路径中的政策答复直接读取已登记的 Markdown，并不通过 pgvector 实时检索。勿把本项目宣传为生产级 LLM 客服系统。

## Day 29 面试官首次访问（5 个预置任务）

启动 Day 26 叠加版后在无痕浏览器打开 `http://127.0.0.1:8080`，使用本地设置的 `preview` 演示账号。首页包含政策引用、价格库存、匿名查单拒答、政策例外转人工、信息不足澄清五个按钮。详见 [Day 29 首访验收与冻结指南](docs/day29_acceptance.md)；新版本结果见本机生成并提交的 `reports/day29/smoke.json`。**Day 27 的 17/20 是修复前冻结基线，不代表 Day 29 最新成绩。**

## 30 秒看价值

| 能力 | 示例提问 | 可观察结果 |
| --- | --- | --- |
| 价格与库存 | `商品P001多少钱？` | 结构化 SQLite 数据、`db:products:P001` 来源 |
| 退货政策 | `七天退货有什么条件？` | 原文依据、`policy-returns` 来源与 SSE 分段答复 |
| 拒绝越权查单 | `订单ORD001现在什么状态？` | 匿名演示不会泄露私人订单详情 |
| 政策例外转人工（Day 29 修复） | `七天退货过期，能破例退款吗？` | 明确提示需要人工客服核实，不自动批准退款；Day 27 留出集报告保留历史失败 |

![Offline CI](https://img.shields.io/badge/tests-offline%20CI-informational)  **评测事实**：Day 27 固定 20 题留出集自动成功 **17/20（85%）**；失败 H05 / H18 / H19。人工复核已完成；H05 曾存在人工与自动评分分歧，修正情况以版本化的人工复核文件和最终报告为准。详见 [完整报告](reports/day27/holdout.json) 和 [人工 CSV](reports/day27/human_review.csv)。

## 架构与部署

[完整架构图（Mermaid）](docs/day28_architecture.md) · [Windows/Docker 全流程](docs/day24_deploy.md) · [HTTPS/回滚](docs/day25_release.md) · [性能与限流](docs/day26_performance.md)

### 新环境快速启动（Windows PowerShell）

要求：**Docker Desktop + Git**。初次构建需要联网获取镜像、Python 依赖和固定版本的 Embedding 模型；机器应预留足够磁盘空间，模型首次下载耗时可能较长。**不需要独立 GPU**。

```powershell
# 在新的目录克隆，不必使用原作者的 E: 盘路径
git clone https://github.com/theark-coder/shopmate-agent.git
cd shopmate-agent
Copy-Item .env.example .env
# 修改 .env 内本地 PostgreSQL 密码；不要把 .env 上传 GitHub
notepad .env
# 原始 Day24 服务；第一次启动 init 构建并导入 30 x 512-D 索引
docker compose up -d --build
docker compose ps
curl.exe -i http://127.0.0.1:8000/
```

若要启动带健康检查、预览登录和 Day26 限流的演示版本：

```powershell
# 先执行并按提示输入密码，复制输出 bcrypt 哈希
docker run --rm -it caddy:2-alpine caddy hash-password
Copy-Item .env.day25.example .env.day25
notepad .env.day25
# 将生成的 bcrypt 哈希填入 .env.day25 的 DEMO_PASSWORD_HASH，保留两侧单引号
docker compose -f compose.yaml -f compose.day25.yaml -f compose.day26.yaml up -d --build
curl.exe -i http://127.0.0.1:8000/health/live
curl.exe -i http://127.0.0.1:8000/health/ready
# 浏览器打开 http://127.0.0.1:8080，输入 preview / 你自己设置的密码
```

临时公网 HTTPS 演示：安装并配置 ngrok 后在本机运行 `ngrok http 8080`，从手机打开转发的 HTTPS 地址。**ngrok 电脑与 Docker 必须持续在线；临时 URL/免费配额不保证长期可用**。公共 Caddy 代理屏蔽 `/api/secure/*`；其 Basic Auth 不能替代 Day23 的真实用户/商家身份鉴权。不要将 `8000` 端口直接暴露到公网。

> **持久化**：PostgreSQL 使用 Docker named volume `pg_data`，SQLite 会话及 `chunks.npz` 使用 `./data:/app/data`。不要运行 `docker compose down -v`。

## API 与离线复现

- [健康检查与 SSE 示例](docs/day28_api_examples.md) —— 提供 Windows PowerShell 可执行命令。
- [3 分钟演示脚本](docs/day28_demo.md) —— 包括**一个失败/拒答案例**。
- [仓库与 CI 说明](docs/day28_open_source.md) —— 说明离线 CI 与环境限制。
- [Day 27 评测方法](docs/day27_evaluation.md) 与 [留出集报告](reports/day27/holdout.json)。
- [Day 26 20 并发压测](reports/day26/performance.json)：40 请求中 4 成功、36 个 503；**90% 失败率是当前 4 并发保护的结果，不代表已能承载 20 并发**。成功请求 TTFT p95 为 657.5 ms，非端到端用户规模性能承诺。

### 本地测试

```powershell
uv run python -m pytest -q
uv run python scripts/check_day28_repo.py
# 离线图评测需要先在本地准备演示数据库：
uv run python scripts/eval_day27.py --mode dev
```

`CI` 使用轻量依赖安装，运行不调用第三方模型的**关键路径 pytest 子集**，避免在 CI 下载 PyTorch/模型权重；**不能把 CI 子集等同于完整 pytest**。完整本地测试和 Compose 演示仍应分别验证。

## 数据、License 与贡献

`data/knowledge/` 中的 30 份 Markdown 和 `scripts/seed_demo_data.py` 生成的价格/订单均为**合成演示数据**，并非真实商家或真实用户信息；语料有 `doc_id`、`version`、`source`。冻结的评测题集在 `eval/day27/`，不能把留出集当开发集反复调参。Embedding 模型与 PostgreSQL 数据迁移参见 [语料与模型说明](docs/day28_architecture.md)。

代码采用 [MIT License](LICENSE)（项目维护者发布前应核对版权归属）。模型、第三方依赖与服务条款**不受本仓库 MIT 自动重新授权**，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

**已知限制**：H05 政策问题误识别；H18/H19 在 Day 27 冻结版未转人工，Day 29 已修复（以独立冒烟报告验证）；当前运行时无 LLM token 统计；限流是单进程内存状态；演示账户不是生产权限系统；当前 HTTPS 入口依赖本机 ngrok。问题和评测报告应随发布版本一同保留。
