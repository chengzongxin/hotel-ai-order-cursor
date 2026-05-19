from langchain_core.tools import tool
from pydantic import BaseModel, Field

from rag.product_retriever import get_product_retriever
from tools.protocol import ToolResult, success_response


class ProductRecallInput(BaseModel):
    query: str = Field(..., min_length=1, description="用户描述的维修商品、设备或区域")
    top_k: int = Field(default=5, ge=1, le=20, description="返回数量")
    threshold: float | None = Field(default=None, ge=0, le=1, description="相似度过滤阈值")


class FaultRecallInput(BaseModel):
    query: str = Field(..., min_length=1, description="用户描述的故障现象")
    top_k: int = Field(default=5, ge=1, le=20, description="返回数量")
    threshold: float | None = Field(default=None, ge=0, le=1, description="相似度过滤阈值")


@tool(args_schema=ProductRecallInput)
def recall_repair_product_tool(
    query: str,
    top_k: int = 5,
    threshold: float | None = None,
) -> ToolResult:
    """基于 embedding 召回维修商品，返回标准 JSON。"""

    results = get_product_retriever().search_products(
        query=query,
        top_k=top_k,
        threshold=threshold,
    )
    return success_response(
        data={
            "query": query,
            "count": len(results),
            "results": results,
        }
    )


@tool(args_schema=FaultRecallInput)
def recall_repair_fault_tool(
    query: str,
    top_k: int = 5,
    threshold: float | None = None,
) -> ToolResult:
    """基于 embedding 召回维修故障，返回标准 JSON。"""

    results = get_product_retriever().search_faults(
        query=query,
        top_k=top_k,
        threshold=threshold,
    )
    return success_response(
        data={
            "query": query,
            "count": len(results),
            "results": results,
        }
    )
