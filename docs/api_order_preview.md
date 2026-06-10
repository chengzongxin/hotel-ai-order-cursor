# 订单预览 API 说明（前端对接）

本文档描述 `/api/chat`、`/api/chat/stream`、`/api/chat/{session_id}/history` 返回中的 `order_preview` 结构，以及商品选择接口。

在线文档：启动服务后访问 `http://localhost:8000/docs`，可看到 Pydantic 模型与示例。

## 设计原则

1. **商品统一放在数组**：`order_preview.products.items[]`，前端直接渲染卡片列表。
2. **字段语义化**：对外使用 `code` / `name` / `service_type`，不再暴露 Excel 原始列名。
3. **选中态明确**：`products.selected_code` + 每个 item 的 `is_selected`。
4. **可扩展**：提交相关数据放在 `submission` 区块，避免与收集/确认阶段混在一起。

## order_preview 顶层结构

| 字段 | 类型 | 说明 |
|------|------|------|
| `service_type` | string \| null | 服务类型，如 `托管维修` |
| `service_type_display` | string \| null | 展示文案，如 `托管维修（客房）` |
| `status` | string \| null | `idle` / `collecting` / `confirming` / `submitted` / `cancelled` |
| `order_info` | object | 用户已描述的订单信息 |
| `products` | object | 商品检索与候选列表 |
| `missing_info` | string[] | 仍需补充的字段名 |
| `submission` | object | 真实下单参数与结果（提交后才有） |

### order_info

| 字段 | 说明 |
|------|------|
| `room_number` | 房号 |
| `product` | 用户描述的设备/商品 |
| `fault` | 故障现象 |
| `area` | 区域 |
| `managed_repair_scope` | 托管维修范围：`客房` / `公区` |
| `urgency` | `low` / `medium` / `high` / `urgent` |
| `expected_start_time` | 期待开工时间 |
| `goods_arrival_status` | 货物到场状态 |
| `user_confirmed` | 是否已确认 |
| `user_cancelled` | 是否已取消 |

### products

| 字段 | 说明 |
|------|------|
| `status` | `skipped` / `success` / `no_match` / `error` |
| `query` | 检索 query，如 `门锁 打不开` |
| `feedback` | 给用户看的匹配说明 |
| `selected_code` | 当前选中商品编码 |
| `items` | 候选商品数组，按 `rank` 排序 |

### products.items[]（商品卡片）

| 字段 | 说明 |
|------|------|
| `code` | 商品编码，下单/选择时使用 |
| `name` | 商品名称 |
| `service_type` | 服务类型 |
| `category` | 分类 |
| `unit` | 单位 |
| `price` | 参考价 |
| `price_status` | 价格状态 |
| `repair_category` | 小修/中修/大修 |
| `fault_phenomenon` | 标准故障描述 |
| `related_area` | 适用区域 |
| `remark` | 服务说明 |
| `score` | 相似度分数 |
| `rank` | 推荐排序，1 最高 |
| `is_recommended` | 是否系统默认 Top1 |
| `is_selected` | 是否当前选中 |

### submission

| 字段 | 说明 |
|------|------|
| `payload` | 构造出的真实下单参数 |
| `result` | 创建订单接口返回 |
| `missing_fields` | 仍缺失字段 |

## 流式事件（NDJSON）

`POST /api/chat/stream` 每行一个 JSON：

| type | 用途 |
|------|------|
| `session` | 返回 `session_id` |
| `status` | 节点进度文案 |
| `preview` | 增量 `order_preview` |
| `token` | AI 回复 token |
| `final` | 完整 `answer` + 最终 `order_preview` |
| `error` | 错误信息 |

`preview` / `final` 中的 `order_preview` 结构与上表一致。

## 选择商品

用户在前端点击某张商品卡片后：

```http
POST /api/chat/{session_id}/select-product
Content-Type: application/json

{
  "product_code": "FWSP01537"
}
```

响应：

```json
{
  "session_id": "4454328f-db92-4d2e-8f09-da0e7c6d63e8",
  "message": "已选择商品【门锁损坏（困客人）】。",
  "order_preview": { "...": "同上结构，selected_code 与 is_selected 已更新" }
}
```

选择成功后，用户可继续发送 `确认` 走原有下单流程。

## 前端渲染建议

1. 当 `products.items.length > 0` 时展示商品卡片列表。
2. 用 `item.is_selected` 或对比 `item.code === products.selected_code` 高亮当前选中项。
3. 点击卡片调用 `select-product`，再用返回的 `order_preview` 刷新 UI。
4. `status === "confirming"` 且 `missing_info` 为空时，展示确认按钮/引导用户回复「确认」。

## 状态机字段（LangGraph AgentState）

商品相关状态已简化为两个字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `products` | object[] | 检索到的全部商品（按相似度排序） |
| `selected_product_code` | string \| null | 当前选中编码；未指定时默认 Top1 |

对外 `order_preview.products` 由上述状态在 API 层推导（`status` / `query` / `feedback`），前端无需感知状态机细节。

## 迁移说明（Breaking Change）

以下字段已从 **API 响应** 和 **状态机** 移除：

| 旧字段 | 新字段 |
|--------|--------|
| `matched_product` | `products` + `selected_product_code`（状态机） / `products.items` + `products.selected_code`（API） |
| `product_candidates` | `products` / `products.items` |
| （旧状态机 `product_search_*`） | `products.status` / `products.query` / `products.feedback`（API 层推导，不再写入 state） |
| `real_order_payload` | `submission.payload` |
| `real_order_result` | `submission.result` |
| `real_order_missing_fields` | `submission.missing_fields` |

## 示例

```json
{
  "service_type": "托管维修",
  "service_type_display": "托管维修（客房）",
  "status": "confirming",
  "order_info": {
    "room_number": "301",
    "product": "门锁",
    "fault": "打不开",
    "area": "客房",
    "managed_repair_scope": "客房",
    "urgency": "medium",
    "user_confirmed": false,
    "user_cancelled": false
  },
  "products": {
    "status": "success",
    "query": "门锁 打不开",
    "feedback": "根据您描述的【打不开】，已为您匹配到【门锁损坏（困客人）】，服务类型为【托管维修（客房）】。",
    "selected_code": "FWSP01537",
    "items": [
      {
        "code": "FWSP01537",
        "name": "门锁损坏（困客人）",
        "service_type": "托管维修",
        "price": "48.08",
        "repair_category": "大修",
        "score": 0.6756,
        "rank": 1,
        "is_recommended": true,
        "is_selected": true
      },
      {
        "code": "FWSP01423",
        "name": "门锁(小修)",
        "service_type": "托管维修",
        "price": "8.02",
        "repair_category": "小修",
        "score": 0.6397,
        "rank": 2,
        "is_recommended": false,
        "is_selected": false
      }
    ]
  },
  "missing_info": [],
  "submission": {
    "payload": {},
    "result": {},
    "missing_fields": []
  }
}
```
