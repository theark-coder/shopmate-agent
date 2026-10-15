# ShopMate Agent v1.0.0 — 发布说明

## 核心能力

- **规则式 LangGraph 电商客服流程**：商品/价格库存、政策原文依据、匿名订单安全拒答、政策例外转人工提示与澄清。
- **FastAPI/SSE 演示**：`retrieval`、`tool`、`answer_delta`、`complete`、`error`；带预置问题页面。
- **部署/安全**：Docker Compose、SQLite 会话持久化、PostgreSQL/pgvector 30×512 维演示向量、Caddy Basic Auth、公开 `/api/secure/*` 路由屏蔽、健康检查。
- **工程保障**：单进程限流/超时、离线 CI、可复现实验和回滚指南。

## 已实测指标（各自测试范围不同）

| 场景 | 结果 | 说明 |
| --- | --- | --- |
| Day 27 冻结留出集 | **17/20 (85%)** | 历史基线；H05/H18/H19 失败。**不因 Day 29 修复而改写。** |
| Day 29 真实 HTTP/SSE 首访冒烟 | **5/5 PASS** | 修复后 5 个固定演示任务；不等于新一轮 20 题评测。 |
| Day 26 本地 20 并发、40 请求 | **4 成功 / 36 个 503** | 默认在途上限 4 的背压验证；不是 20 并发可用性证明。 |
| Token/完整成本 | **未测量** | 当前在线问答未调用 LLM；基础设施和人工成本未完整计量。 |

证据：[Day 27 留出集](https://github.com/theark-coder/shopmate-agent/blob/v1.0.0/reports/day27/holdout.json) · [Day 29 冒烟](https://github.com/theark-coder/shopmate-agent/blob/v1.0.0/reports/day29/smoke.json) · [Day 26 压测](https://github.com/theark-coder/shopmate-agent/blob/v1.0.0/reports/day26/performance.json) · [Day 30 发布清单](https://github.com/theark-coder/shopmate-agent/blob/v1.0.0/reports/day30/release_manifest.json)。

## 架构和风险说明

运行时是**规则式 LangGraph**，并非在线大模型生成；政策回答直接读取权威演示 Markdown，**pgvector 仅用于索引与持久化演示，尚未接入实时客服检索路径**。所有商品、价格、订单、政策和账号均为合成演示数据。Day 29 “转人工”仅提示联系客服，**未真正创建工单**。H05 意图识别问题仍存在；进程内限流不适合多副本集群共享配额。

## 访问与复现

- 源码：[GitHub 仓库](https://github.com/theark-coder/shopmate-agent)
- **公网演示入口**：见同版本 `reports/day30/release_manifest.json` 的 `demo_url`。当前使用临时 ngrok HTTPS 开发域名；**电脑、Docker 与 ngrok 不持续运行时可能不可访问**。
- 本地部署：查看 [README](https://github.com/theark-coder/shopmate-agent/blob/v1.0.0/README.md) 与 [Day 24 部署指南](https://github.com/theark-coder/shopmate-agent/blob/v1.0.0/docs/day24_deploy.md)；HTTPS 与回滚：[Day 25 指南](https://github.com/theark-coder/shopmate-agent/blob/v1.0.0/docs/day25_release.md)。

> 发布到 GitHub Releases 时，这份 Markdown 中指向仓库文件的相对链接可直接用；建议在发布说明正文附上绝对 URL。**确认公开演示正在运行且手机验证成功，才宣称“目前可访问”。**
