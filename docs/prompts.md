# Prompt 目录说明

所有生产路径的 Prompt 均放在 `prompts/`，通过 `workflow/prompts.py` 的 `load_prompt` / `render_prompt` 加载。

## 核心规则

> **一个 LangGraph 节点 → 一类 Prompt → 一个同名子目录**

| LangGraph 节点 | 子目录 | Prompt 文件 |
| --- | --- | --- |
| `intent_node` | `prompts/intent/` | `intent/intent.md` |
| `ask_node` | `prompts/ask/` | `missing_info.md`、`off_topic.md` 等 |
| `assist_node` | `prompts/assist/` | `assist/assist.md` |
| `confirm_node` | `prompts/confirm/` | `confirm/confirm.md` |
| `submit_node` | `prompts/submit/` | `submit/submit.md` |
| `cancel_node` | `prompts/cancel/` | `cancel/cancel.md` |

**不需要 Prompt 子目录的节点**（纯逻辑 / 工具，不调用 LLM Prompt）：

| 节点 | 说明 |
| --- | --- |
| `search_product_node` | 调用 `search_product_tool` 做向量检索 |
| `validate_order_node` | 校验必填字段、递增 `retry_count` |

说明：

- 子目录名去掉 `_node` 后缀（`intent_node` → `intent/`）。
- 该节点只有一份主 Prompt 时，可用 **`{目录}/{目录}.md`**（如 `intent/intent.md`、`cancel/cancel.md`）。
- 同一节点多份 Prompt 时，在同一子目录用功能名区分（如 `ask/off_topic.md`）。
- 节点内仍有少量**固定兜底文案**写在 Python（见下文「未文件化」），新增时优先放进对应子目录。

## 文件清单

| 路径 | 节点 |
| --- | --- |
| `intent/intent.md` | `intent_node` |
| `ask/missing_info.md` | `ask_node` |
| `ask/missing_info_retry.md` | `ask_node` |
| `ask/off_topic.md` | `ask_node` |
| `ask/unknown_fallback.md` | `ask_node` |
| `assist/assist.md` | `assist_node` |
| `confirm/confirm.md` | `confirm_node` |
| `submit/submit.md` | `submit_node`（仅提交成功） |
| `cancel/cancel.md` | `cancel_node` |

## 未文件化（仍在 Python）

| 位置 | 说明 |
| --- | --- |
| `workflow/questions.py::build_missing_info_fallback_question` | 缺字段固定追问（含时间、货物状态） |
| `build_product_search_feedback` | 商品匹配成功前缀（`workflow/products.py`，对话气泡与 API 推导共用） |
| `assist_node` 空回复兜底 | 引导用户提供房号、商品、问题 |
| `submit_node` 失败分支 | 未真提交、缺参数、地址接口失败等 |
| `workflow/questions.py::build_topic_boundary_response` | `next_question` 部分硬编码 |

## 修改注意

- 改 `.md` 后需重启进程（`load_prompt` 带 `@lru_cache`）。
- 同步更新 `workflow/builder.py`、`workflow/questions.py`、`workflow/agent.py` 与本文件。
