# ShopMate · Day 26 性能 / 限流与 20 并发压测

## 今天的精确任务（60 天 Excel）

- 理论：限流、HTTP 429/5xx、指数退避 + full jitter、缓存、p95、TTFT。
- 实现：模型/请求超时、限流保护、固定 20 并发测试，统计 TTFT、p95、失败率、token 情况。
- 验证：报告样本、硬件、模型、并发及环境限制。面试：**用户并发增长时先限哪一层？**

> **重要事实**：当前 `shopmate_graph.py` 的 answer 使用规则和 SQLite / 政策原文，没有在线 LLM。无 provider token usage，因此结果 JSON 的 `actual_model_tokens` 是 `null`（不适用），绝不拿字符数冒充 Token。`TTFT` 指第一段 `answer_delta` 的时间，不是 SSE 的 `start` 事件。

## 增量结构：保持 Day 24 / Day 25 的成果

新增文件：

- `src/shopmate_agent/perf_guard.py`：只守护 `POST /api/chat/stream`，429（60 秒滑动窗口）、503（并发占满）、超时；保留 SSE 错误事件。
- `src/shopmate_agent/day26_app.py`：复用 Day25 原有 `app`，只新增中间件。
- `compose.day26.yaml`：第三个叠加 Compose 文件，**不替换**原始配置、不修改数据库、不重新建索引。
- `scripts/load_test_day26.py`：固定演示问题集，默认 40 请求、20 并发、固定随机种子 26，输出 JSON。
- `tests/test_day26_perf.py`：离线限流、退避、TTFT 指标测试。

**服务端默认配置：** 同时最多 4 个 SSE 请求；每分钟最多 120 个进入处理；每个请求最多 60 秒。请求被挡住时返回 429/503 和 `Retry-After`；若流已开始才超时，HTTP 状态无法改写，只能发 `event:error`。健康检查不受影响。此限制为**单 Uvicorn 进程**，扩展到多工作进程后应使用 Redis/Caddy 集中限流。

## 1. 安装（Windows PowerShell）

```powershell
cd E:\shopmate\shopmate-agent
# 展开 day26 ZIP 到项目根目录，不能多一层文件夹
uv run python -m pytest tests/test_day26_perf.py -v
uv run python -m pytest -q
```

检查叠加配置：

```powershell
docker compose -f compose.yaml -f compose.day25.yaml -f compose.day26.yaml config --quiet
docker compose -f compose.yaml -f compose.day25.yaml -f compose.day26.yaml up -d --build
docker compose -f compose.yaml -f compose.day25.yaml -f compose.day26.yaml ps
curl.exe -i http://127.0.0.1:8000/health/ready
```

浏览器、Caddy 8080、手机公网 HTTPS 地址仍用 Day25 的服务，**Windows 版 ngrok 如果仍 online 不必重启**。

## 2. 先建立顺序请求基线（非 20 并发，只做对照）

```powershell
uv run python scripts/load_test_day26.py --requests 10 --concurrency 1 --hardware "i7-10750H / 16GB RAM / GTX 1650" --output reports/day26/baseline.json
```

## 3. 必做：固定 20 并发，40 请求

```powershell
uv run python scripts/load_test_day26.py --requests 40 --concurrency 20 --seed 26 --retries 0 --hardware "i7-10750H / 16GB RAM / GTX 1650" --output reports/day26/performance.json
```

这个脚本直接请求本机 App `127.0.0.1:8000`，不经 ngrok，以便不消耗隧道额度、隔离公网网络波动。服务端上限是 4，所以 **20 并发时发生部分 503 是可预期的背压效果，不代表压测自动失败**。报告应如实记载失败率，而非为了好看的数字故意把失败剔除。`HTTP 200` 但 SSE 发 `error` 或缺 `complete` 也计为失败。

如需观察允许重试时的真实表现，可以做**额外**一轮：

```powershell
uv run python scripts/load_test_day26.py --requests 40 --concurrency 20 --seed 26 --retries 1 --hardware "i7-10750H / 16GB RAM / GTX 1650" --output reports/day26/performance_retry.json
```

重试仅针对**尚未建立 SSE 流之前**返回的 429/5xx，使用指数退避 + jitter 且尊重 `Retry-After`。已经开始流式回复、发生半途断线时不重试，避免回答重复。遇到 429 的 `Retry-After` 可能需要等待几十秒；不要暴力重试。

查看报告：

```powershell
Get-Content .\reports\day26\performance.json -Raw
```

## 4. 理论与业务边界

- **p95**：95% 请求不超过的延迟阈值。报告中 p95 只针对完整成功的请求；同时看失败率才能防止隐藏尾部失败。
- **TTFT**：从发送请求到第一段 *答案内容* `answer_delta` 的时间；不把 `start` 事件当成答案。
- **429**：本服务每分钟配额耗尽；`Retry-After` 指示最早重试时机。
- **503**：请求正在处理的数量已达上限；客户端可以退避，不应占满排队。
- **5xx/超时**：最重要是可观测性。流开始后无法改 HTTP 状态，SSE `error` 必须被浏览器识别。
- **缓存**：政策知识可按文档版本号、商家范围构建缓存键；商品价格/库存随时变化不能简单缓存；私人订单与用户会话绝不能无身份隔离地共享缓存。**今天只学习缓存设计，不修改已有工具输出以免产生陈旧事实。**
- **多副本**：本版防护是进程内内存，单个 worker 生效；扩容时用 Redis 或 API Gateway/Caddy 共享限制，不要误称集群级限流。
- **模型 API**：以后接入 LLM 时，应单独在 LLM SDK 调用层针对 provider 429、502/503/504 实现有边界的重试，以及每次调用的超时与 usage 统计；当前离线规则式模型不能模拟为真实 LLM Token 指标。

## 5. GitHub 提交

```powershell
git add compose.day26.yaml src/shopmate_agent/perf_guard.py src/shopmate_agent/day26_app.py scripts/load_test_day26.py tests/test_day26_perf.py docs/day26_performance.md reports/day26/baseline.json reports/day26/performance.json
# 可选添加 reports/day26/performance_retry.json
git commit -m "feat: add day26 admission control and reproducible SSE load test"
git push origin main
```

确认 `reports/day26/*.json` 不包含账号密码、Token、实际订单信息；报告只包含汇总数、系统环境信息。

## 6. 回滚与退出

不必更改源码，重新用 Day25 的两份 Compose 文件即可停用性能叠加：

```powershell
docker compose -f compose.yaml -f compose.day25.yaml -f compose.day26.yaml down
docker compose -f compose.yaml -f compose.day25.yaml up -d --build
```

此过程不会删 PostgreSQL named volume；**不要运行 `down -v`**。从 Day26 叠加回退到 Day25 前关闭旧代理会造成短暂演示中断，请选择无人访问时操作。

## 7. Day 26 交付验收

请回报：新增测试、完整 pytest、20 并发/40 请求报告中的 TTFT p95/延迟 p95/失败率/429/503、硬件与模型边界、GitHub；然后回答面试题：**用户并发增长时先限哪一层？为什么？**
