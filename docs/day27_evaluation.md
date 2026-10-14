# Day 27 · ShopMate 客服事实、引用、转人工与人工评审

本次任务严格对应《Agent开发_60天每日打卡_修订版.xlsx》第 27 天：**开发集做消融；冻结版本跑 20 题留出集；复核价格/库存来自工具，政策来自文档；人工评审；统计成功数、误承诺、转人工、成本和失败案例。**

## 一、不要改变 Day26 的运行环境

今天只增加 `scripts/eval_day27.py`、两份独立题集、9 个离线测试和这份文档。评测直接调用 `shopmate_agent.shopmate_graph.build_graph().invoke(...)`，**不会调用公网 HTTPS、Caddy、ngrok、第三方 LLM**；不修改数据库、Docker、会话或权重。

建议先为 Day26 建立恢复点（确认当前已经提交后）：

```powershell
cd E:\shopmate\shopmate-agent
git status --short
git tag day26-verified
```

解压 Day27 压缩包到项目根目录，执行：

```powershell
uv run python -m pytest tests/test_day27_eval.py -v
uv run python -m pytest -q
```

## 二、概念与两种数据集

- **开发集 `eval/day27/dev.json`**：7 题，用于比较原图与「关闭政策文档证据」消融图。只替换 `policy_retrieve` 的输出，其余节点和评分器保持不变。政策题应该变差，商品与未授权订单题不能被牵连。指标仅用于分析组件价值，不允许基于留出题反向调参。
- **留出集 `eval/day27/holdout.json`**：固定 20 题：8 政策、6 商品、3 未授权订单、2 应转人工、1 澄清。与开发集不重复，生成报告后不要再修改标签。
- **自动评分**：使用独立的权威 SQLite `prices`/`inventory` 及政策 Markdown，避免让 Agent 的自称 `verified=True` 直接充当真值。价格必须精确匹配，引用必须对应结构化工具/政策文件。匿名订单不得透露数据库订单状态。未获依据不能承诺退款/发货，政策例外应明确转人工。
- **人工评审**：自动评分不等于人工判断。需亲自逐题看答案、来源、业务边界，为 20 题分别填写 `PASS` 或 `FAIL`，记录关键失败原因。

## 三、跑开发集消融 + 冻结的 20 题留出集

```powershell
uv run python scripts/eval_day27.py --mode all
```

输出三个文件：

- `reports/day27/dev_ablation.json`：开发集基线与关闭政策来源后的结果（附逐题状态）。
- `reports/day27/holdout.json`：20 题逐题答案、引用、失败标签、成功率、误承诺、转人工表现、成本边界及源码 SHA-256。
- `reports/day27/human_review.csv`：供人工填写的 20 题复核表（UTF-8 BOM，Excel 可打开）。

**注意：** 评测版本记录 git SHA 和源码/两份题集/政策文件 SHA-256。数据库未被写入，价格/库存每次从只读 SQLite 查询；若重新生成数据库或修改商品价格，重新跑出来的结果可能变化，应保留当时数据快照说明。报告的 `cost.actual_model_tokens=null` 与 `cost.measured_total_usd=null` 是事实：当前规则图没有真实调用大模型，基础设施/人工成本也未测量；请勿填 0 元作为总成本。

示例查看结果：

```powershell
Get-Content .\reports\day27\dev_ablation.json -Raw
Get-Content .\reports\day27\holdout.json -Raw
```

**失败案例必须留在报告中。** 特别关注 `H18`、`H19` 这种需要人工处理的政策例外：现有图并未专门设计转人工分支，预期可能失败。今天的目标是准确发现问题，不是在留出集上「调到满分」。

## 四、人工复核 20 题，冻结报告

先运行上一步，打开：

```powershell
notepad .\reports\day27\human_review.csv
```

建议改用 Excel 打开 CSV。每题核对：**答案事实是否精确、引用是否存在、是否误承诺、是否泄露匿名订单、是否需要转人工**。将 `manual_verdict` 列逐行填 `PASS`/`FAIL`，有争议在 `review_notes` 中写明理由。不要修改 `case_id` 或删行。

填写完后：

```powershell
uv run python scripts/eval_day27.py --mode finalize
```

此步骤**不会重新跑模型或评测题**，仅读取已有的 `holdout.json` 与你亲自填写的 CSV，计算人工通过数及人与自动评分分歧。如果任何一题未填，会显示具体 ID，补填即可。

**防止覆盖已填写表格：** 生成题集的 `--mode all`/`--mode holdout` 只运行一次；如果已开始人工评分，不要再次运行这些模式。需复跑时先备份旧结果与 CSV 并注明新一轮版本。

## 五、GitHub 与面试

确认提交报告不包含账号密码、Authtoken 或用户真实订单数据；项目使用的是演示数据：

```powershell
git add scripts/eval_day27.py eval/day27/dev.json eval/day27/holdout.json tests/test_day27_eval.py docs/day27_evaluation.md reports/day27/dev_ablation.json reports/day27/holdout.json reports/day27/human_review.csv
git commit -m "test: evaluate ShopMate policy grounding and held-out cases"
git push origin main
git tag day27-eval-v1
```

**面试题：** 「客服答复看着很流畅，为什么仍可能不可用？」

期望说明：事实可能不来自结构化工具或权威文档；价格库存随时变化；越权查单；政策例外不转人工、做出无依据承诺；所以必须评估事实正确性、可追溯引用、权限边界、拒答/转人工，而不是只评价流畅度。

**今日验收：** 新增测试和全量 pytest 均通过；开发集对比结果存在；20 题留出集有真实逐题报告；人工 CSV 完成 20 项；记录成功数、误承诺、转人工、成本与失败案例；推送 GitHub；面试答题。报告结果不要求人为达成 100%。
