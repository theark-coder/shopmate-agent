# ShopMate Day 25 — HTTPS 预览、健康检查、发布与回滚

## 本次改动范围

继续复用 Day 24 的 `compose.yaml`，仅用第二份 `compose.day25.yaml` 叠加：

- App 改为启动 `shopmate_agent.public_demo:app`；添加 `/health/live` 与 `/health/ready`。
- App 的 `/health/ready` 检查现有 SQLite 业务表、SQLite 会话表、512 维本地向量文件、PostgreSQL 中 pgvector 数据数量/维度。
- Caddy `proxy` 为 App 加入 HTTP Basic Auth（预览账号 `preview`）并代理 SSE；`/api/secure` 不通过公开代理访问。
- `web/day25.html` 提供三个预置问题（政策、商品、匿名订单拒答）。
- 公网 HTTPS 用 ngrok 免费开发域名。仍需账号和 authtoken；这是一种演示 URL，不是生产 SLA。
- **不要使用 Cloudflare Quick Tunnel**：其官方文档说明不支持 SSE，会缓冲 `text/event-stream`。

## 0. 前提：保留已通过的 Day 24

在 Windows PowerShell 的 ShopMate 项目根目录运行：

```powershell
cd E:\shopmate\shopmate-agent
git status --short
# 建议在 Day 24 已提交且工作区干净时创建回滚标记
git tag day24-verified
```

将 Day 25 的压缩包直接解压到项目根目录（注意不要额外套一层文件夹）。

在 `.gitignore` **和** `.dockerignore` 末尾都增加：

```
.env.day25
```

这样既不会把演示密码哈希提交到 GitHub，也不会因为 Day 24 的 `COPY . /app` 将其复制进应用镜像。

不要覆盖 Day 24 `compose.yaml`、SQLite 数据文件、`data/index/chunks.npz` 或 `.env`。

## 1. 演示账号：生成只存储本地的密码哈希

在 PowerShell 运行：

```powershell
docker run --rm -it caddy:2-alpine caddy hash-password
```

根据提示输入**自己新设的演示密码**，复制输出的 bcrypt 哈希。复制示例文件：

```powershell
Copy-Item .env.day25.example .env.day25
notepad .env.day25
```

将 `.env.day25` 中 `DEMO_PASSWORD_HASH` 替换为生成的哈希，**保留两侧单引号**：

```
DEMO_PASSWORD_HASH='$2a$...生成的完整哈希...'
```

注意：**不要把真实密码、哈希或 ngrok Authtoken 发给 ChatGPT，也不要提交到 GitHub**。

`preview` 是 Caddy 的公开演示访问账号，只能保护这个预览 URL；它并非 Day 23 用户/商家授权身份。

## 2. 先在本机发布新版本

```powershell
docker compose -f compose.yaml -f compose.day25.yaml config --quiet
docker compose -f compose.yaml -f compose.day25.yaml up -d --build
docker compose -f compose.yaml -f compose.day25.yaml ps
```

预期 `app` 和 `db` 运行、`init` 成功退出、`proxy` 运行，`app` 健康状态为 healthy。

```powershell
curl.exe -i http://127.0.0.1:8000/health/live
curl.exe -i http://127.0.0.1:8000/health/ready
```

预期 `200`，ready 中四项 `ok`。

浏览器先打开 `http://127.0.0.1:8080`，用账号 `preview` 和你刚才设定的演示密码登录。

```powershell
# 代理必须拒绝公开的私人订单 API
curl.exe -i http://127.0.0.1:8080/api/secure/orders/ORD001
```

预期 404。不要通过公网代理公开 `/api/secure`：公开预览的 Basic Auth 账号不能代表真实订单所有者。

## 3. 获得第二台设备可访问的 HTTPS 地址

ngrok 需要免费账号和 authtoken（官方：https://ngrok.com/download/windows）。
Windows 端安装：

```powershell
winget install ngrok -s msstore
```

**新开一个 PowerShell 窗口**，输入自己的 authtoken（不要放入 Git、聊天或截图）：

```powershell
$env:NGROK_AUTHTOKEN = Read-Host "Paste your ngrok authtoken"
ngrok http 8080
```

让此窗口保持运行；ngrok 会显示分配给你的 HTTPS `*.ngrok-free.app` 开发域名。此公网 URL 经过 ngrok HTTPS，转发到本机 8080 的 Caddy 代理。浏览器若显示 ngrok 免费计划访问提示，按实际提示继续。

将该 URL 在**手机蜂窝网络/第二台电脑**和**无痕浏览器**里打开：使用预览账号 `preview`，然后逐个测试页面上的三个预置问题。

- 退货政策：检索事件、答案增量、完成事件、来源 `policy-returns`。
- 商品价格：工具事件、答案增量、完成事件、来源 `db:products:P001`。
- 订单查询：匿名不能泄露订单状态，保持无数据/安全拒答。

**注意观察：** 公网浏览器应该在流尚未结束时看到 `answer_delta` 增量出现，而不是一直空白直到一次性显示答案。若被 ngrok 或其他代理缓冲，SSE 还不能算通过，请不要把 `complete` 一次性到达误判为流式成功。

结束 ngrok 运行：在 ngrok 终端按 `Ctrl+C`，并清除当前 PowerShell 中临时环境变量：

```powershell
Remove-Item Env:NGROK_AUTHTOKEN
```

免费计划额度/访问提示会变化，请按账号显示为准。这个 demo 不具备服务器长期开机、生产 HTTPS/证书管理、日志治理等保证。

## 4. 定位一次真实健康检查失败

先记录健康状态：

```powershell
curl.exe -i http://127.0.0.1:8000/health/ready
```

在**本机演示数据库**进行临时故障演练（不要在有真实用户请求期间操作）：

```powershell
docker compose -f compose.yaml -f compose.day25.yaml stop db
curl.exe -i http://127.0.0.1:8000/health/ready
docker compose -f compose.yaml -f compose.day25.yaml ps
docker compose -f compose.yaml -f compose.day25.yaml logs --tail=40 app
```

预期 App 的 liveness 仍为 200，但 readiness 为 503，JSON 中 `checks.pgvector = "failed"`。日志可见 `health probe failed: pgvector (...)`，不含连接密码。

立即恢复：

```powershell
docker compose -f compose.yaml -f compose.day25.yaml start db
# 等几秒，直到 db healthy、app healthy
curl.exe -i http://127.0.0.1:8000/health/ready
```

再次看到 200 / `pgvector=ok` 才完成故障演练。`docker compose stop db` 是可控停止测试，不应丢失持久化数据。

## 5. 发布版本号与回滚

测试和网页验收完成后：

```powershell
uv run python -m pytest tests/test_day25_release.py -v
uv run python -m pytest -v

git add .gitignore .dockerignore compose.day25.yaml deploy/Caddyfile.day25 src/shopmate_agent/health_api.py src/shopmate_agent/public_demo.py web/day25.html tests/test_day25_release.py docs/day25_release.md .env.day25.example
git commit -m "feat: add HTTPS demo proxy health probes and rollback runbook"
git push origin main
git tag day25-demo-v1
```

**如何回到 Day 24：**

```powershell
# 先关闭新版本代理和业务服务，不删除 pgvector 的 Named Volume
# 如果 ngrok 窗口仍在，先 Ctrl+C 停止
docker compose -f compose.yaml -f compose.day25.yaml down
# 回退到预先标记的已知良好源码
git switch --detach day24-verified
# 只按原 Day24 Compose 启动
docker compose -f compose.yaml up -d --build
```

**恢复到 Day 25 最新源码：**

```powershell
docker compose -f compose.yaml down
git switch main
docker compose -f compose.yaml -f compose.day25.yaml up -d --build
```

`.env.day25` 留在本地（被忽略）；如果你使用过临时 demo 密码，重新生成可以更新预览凭据。**严禁 `docker compose down -v`**，会删除命名卷。

## 6. 常见排查顺序

1. `docker compose ... ps`：服务是否运行、是否 unhealthy。
2. `docker compose ... logs --tail=60 app proxy db`：应用、代理或数据库错误。
3. `curl.exe -i http://127.0.0.1:8000/health/live`：App 进程是否可用。
4. `curl.exe -i http://127.0.0.1:8000/health/ready`：数据库、会话和索引状态。
5. 用预览账号打开 `http://127.0.0.1:8080`：Caddy Basic Auth 与反向代理是否正常。
6. `ngrok http 8080` 日志：HTTPS 隧道是否连接成功。
7. 第二设备检查预置问题和流式增量：定位 DNS、TLS、代理或浏览器问题。
8. 只有在本地链路完全正常而公网仍失败时，才排查 ngrok、网络出口和浏览器跨站/访问提示问题。
