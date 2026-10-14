# API Examples (Windows PowerShell) / API 调用示例

All commands use the app's **local-only** `127.0.0.1:8000`; never expose this private API port to the public Internet. Ensure the Day26 Compose overlay is started.

## Health endpoints

```powershell
curl.exe -i http://127.0.0.1:8000/health/live
curl.exe -i http://127.0.0.1:8000/health/ready
```

Both should return `200` when all dependencies are healthy. On a controlled database outage `/health/ready` returns `503` with category-level failures (not secret connection strings).

## SSE: receive raw progress events

The following avoids PowerShell quoting inconsistencies by using Python standard library to write a **BOM-free** JSON request file:

```powershell
cd E:\shopmate\shopmate-agent
uv run python -c "from pathlib import Path; import json; Path('day28-request.json').write_text(json.dumps({'question':'七天退货有什么条件？'},ensure_ascii=False), encoding='utf-8')"
curl.exe -N -X POST http://127.0.0.1:8000/api/chat/stream -H "Content-Type: application/json" --data-binary "@day28-request.json"
Remove-Item .\day28-request.json
```

Expected event **kinds** (payload fields vary): `start`, `retrieval`, one or more `answer_delta`, and `complete` with `citations` containing `policy-returns`. HTTP 200 alone is not enough: an SSE `error` or a missing `complete` is a failure. The streaming `start` event is not TTFT.

To demonstrate an anonymous order refusal, repeat using question `订单ORD001现在什么状态？`. The answer must not include private order status or pretend an anonymous session has the Day23 owner identity.

## Public preview / private routes

`http://127.0.0.1:8080` uses Caddy Basic Auth (`preview` and the locally configured password). The public preview does not publish `/api/secure/*`:

```powershell
curl.exe -i http://127.0.0.1:8080/api/secure/orders/ORD001
```

Expected: HTTP `404`. Direct API port 8000 has Day23's **separate** Bearer-token authentication; do not use demo Basic Auth as order-owner identity.
