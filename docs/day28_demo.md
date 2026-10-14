# Three-minute ShopMate Demo / 三分钟演示脚本

Before recording: ensure `app`, `db`, `proxy` are running, the preview login is known, and **do not show `.env`, tokens, local private orders or real customer details**. Prefer the local `http://127.0.0.1:8080` demo; ngrok address is transient.

| Time | Action and expected observation | What it proves |
|---|---|---|
| **00:00–00:25** | Open README. Point to architecture diagram, API examples, reproducibility and Day 27 report. | Engineering handoff, not a screenshot-only project. |
| **00:25–00:45** | Open authenticated preview as `preview` and select the **七天退货有什么条件？** preset. | Demonstration account and a known question. |
| **00:45–01:25** | Submit; point out retrieval trace, incremental `answer_delta` and final `policy-returns` citation. | Grounded policy + genuine SSE. |
| **01:25–02:05** | Select **商品P001多少钱？**; show source `db:products:P001` and live demo SQLite price/stock. | Structured tool result, not guessed price. |
| **02:05–02:35** | Select **订单ORD001现在什么状态？**; show **no private status leaked**. | Refusal when visitor has no order ownership credentials. |
| **02:35–03:00** | Show Day 27 report: 17/20; click the H18 failure entry. The present graph returns policy but **does not escalate exception to a human**. | Honest known limitation and prioritized next improvement. |

**Failure/Refusal requirement**: The demo includes both a correct anonymous-order refusal and a genuine known failing scenario (H18). Do not claim H18 is resolved or that the current answer is an authorized refund decision. H05/H19 are also still tracked.

### What if demo fails during an interview?

1. Confirm `docker compose -f compose.yaml -f compose.day25.yaml -f compose.day26.yaml ps` and `/health/ready` status.
2. Open `docker compose -f compose.yaml -f compose.day25.yaml -f compose.day26.yaml logs --tail=50 app proxy`.
3. Prefer local 8080 testing before debugging ngrok. If SSE stalls, inspect event trace and proxies; avoid hiding failures.
4. Open the **versioned offline evaluation report** as a fallback while acknowledging the live demo is unavailable.
