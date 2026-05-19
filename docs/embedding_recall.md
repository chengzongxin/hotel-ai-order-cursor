# 维修商品 Embedding 召回系统

## 目标

该模块从 `assets/spu.xlsx` 读取维修商品数据，并使用 embedding 做语义召回。

支持两类召回：

- 商品召回：根据用户说的设备、物品、区域，找到最相关的维修商品。
- 故障召回：根据用户说的故障现象，找到可能匹配的维修商品和故障项。

## 技术

- `sentence-transformers`：生成文本向量。
- `numpy`：计算 cosine similarity。
- `openpyxl`：读取 Excel。

## 配置

`.env` 中可配置：

```env
SPU_EXCEL_PATH=assets/spu.xlsx
EMBEDDING_MODEL_NAME=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_CACHE_DIR=data/embedding_cache
PRODUCT_RECALL_THRESHOLD=0.45
FAULT_RECALL_THRESHOLD=0.4
```

## Tool

### recall_repair_product_tool

根据用户输入召回维修商品。

输入：

```json
{
  "query": "空调不制冷",
  "top_k": 5,
  "threshold": 0.45
}
```

输出：

```json
{
  "status": "success",
  "error_code": null,
  "message": "ok",
  "data": {
    "query": "空调不制冷",
    "count": 1,
    "results": [
      {
        "score": 0.8231,
        "code": "FWSP00001",
        "name": "空调",
        "category": "客房设备/空调",
        "fault_phenomenon": "不制冷、漏水、噪音大"
      }
    ]
  },
  "fallback": null
}
```

### recall_repair_fault_tool

根据故障描述召回相关维修项。

输入：

```json
{
  "query": "洗碗机漏水",
  "top_k": 5,
  "threshold": 0.4
}
```

## 阈值过滤

`threshold` 越高，结果越少但更精确。

建议：

- 商品召回：`0.45`
- 故障召回：`0.4`
- 如果没有结果，可以临时降到 `0.3`

## 缓存

首次调用会加载模型并生成向量，速度较慢。系统会把向量缓存到：

```text
data/embedding_cache/
```

当 Excel 文件大小、修改时间或模型名称变化时，会自动重建缓存。
