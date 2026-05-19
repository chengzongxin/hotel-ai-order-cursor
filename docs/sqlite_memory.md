# LangGraph + SQLite Memory

## 设计目标

SQLite Memory 负责解决 Agent “失忆”的问题。这里的记忆分成两类：

- 多轮对话消息：保存用户和 AI 的每轮消息。
- LangGraph checkpoint：保存图运行过程中的状态快照，支持按 `session_id` 恢复。

## session_id

每一次对话都属于一个 `session_id`。前端或调用方只要把同一个 `session_id` 传回来，后端就能恢复上下文。

请求示例：

```json
{
  "session_id": "guest-1208",
  "message": "空调不制冷"
}
```

## SQLite 文件

默认路径：

```text
data/agent_memory.sqlite3
```

可以通过 `.env` 修改：

```env
SQLITE_MEMORY_PATH=data/agent_memory.sqlite3
CONVERSATION_SUMMARY_MAX_MESSAGES=12
```

## 数据表

`sessions` 表保存会话级信息：

- `session_id`
- `conversation_summary`
- `created_at`
- `updated_at`

`messages` 表保存多轮消息：

- `session_id`
- `role`
- `content`
- `created_at`

LangGraph checkpoint 表由 `AsyncSqliteSaver` 自动创建。

## 恢复上下文

恢复上下文依赖两件事：

1. `SQLiteChatMemory.get_langchain_messages(session_id)` 恢复历史消息。
2. `AsyncSqliteSaver` 使用同一个 `thread_id=session_id` 恢复图状态。

代码中对应配置：

```python
config={"configurable": {"thread_id": active_session_id}}
```

## conversation summary

当消息数量超过 `CONVERSATION_SUMMARY_MAX_MESSAGES` 时，系统会把较早的消息压缩成 `conversation_summary`。

当前版本使用稳定的本地压缩摘要，不额外调用 LLM。后续可以升级成独立 `summary_node`，让模型生成更自然的摘要。
