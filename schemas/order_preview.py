from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OrderStatus(str, Enum):
    """订单生命周期状态。"""

    IDLE = "idle"
    COLLECTING = "collecting"
    CONFIRMING = "confirming"
    SUBMITTED = "submitted"
    CANCELLED = "cancelled"


class UrgencyLevel(str, Enum):
    """紧急程度。"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class ProductSearchStatus(str, Enum):
    """商品检索状态。"""

    SKIPPED = "skipped"
    SUCCESS = "success"
    NO_MATCH = "no_match"
    ERROR = "error"


class OrderInfo(BaseModel):
    """用户已描述、可被确认/提交的订单信息。"""

    model_config = ConfigDict(extra="allow")

    room_number: str | None = Field(default=None, description="房号；公区维修时可能为 /")
    product: str | None = Field(default=None, description="用户描述的商品/设备")
    fault: str | None = Field(default=None, description="故障现象")
    area: str | None = Field(default=None, description="区域，如 客房、公区")
    managed_repair_scope: str | None = Field(default=None, description="托管维修范围：客房 / 公区")
    urgency: UrgencyLevel | str | None = Field(default=None, description="紧急程度")
    expected_start_time: str | None = Field(default=None, description="期待开工时间")
    goods_arrival_status: str | None = Field(default=None, description="货物是否到场")
    user_confirmed: bool = Field(default=False, description="用户是否已确认下单")
    user_cancelled: bool = Field(default=False, description="用户是否已取消当前预下单")


class ProductOption(BaseModel):
    """单个可下单商品，供前端卡片展示与选择。"""

    code: str = Field(..., description="商品编码，如 FWSP01537", examples=["FWSP01537"])
    name: str = Field(..., description="商品名称", examples=["门锁损坏（困客人）"])
    service_type: str = Field(..., description="服务类型", examples=["托管维修"])
    category: str | None = Field(default=None, description="商品分类")
    unit: str | None = Field(default=None, description="计价单位")
    price: str | None = Field(default=None, description="参考价格")
    price_status: str | None = Field(default=None, description="价格状态")
    repair_category: str | None = Field(default=None, description="维修等级，如 小修/中修/大修")
    fault_phenomenon: str | None = Field(default=None, description="标准故障现象描述")
    related_area: str | None = Field(default=None, description="适用区域")
    remark: str | None = Field(default=None, description="服务说明")
    score: float | None = Field(default=None, ge=0.0, le=1.0, description="与检索 query 的相似度")
    rank: int = Field(..., ge=1, description="推荐排序，1 为最高")
    is_recommended: bool = Field(default=False, description="是否为系统默认推荐（Top1）")
    is_selected: bool = Field(default=False, description="当前是否已被选中")


class ProductSection(BaseModel):
    """商品匹配结果区块。"""

    status: ProductSearchStatus | str | None = Field(
        default=None,
        description="检索状态：skipped / success / no_match / error",
    )
    query: str | None = Field(default=None, description="本轮检索使用的 query")
    feedback: str | None = Field(default=None, description="面向用户的匹配说明文案")
    selected_code: str | None = Field(default=None, description="当前选中的商品编码")
    items: list[ProductOption] = Field(default_factory=list, description="全部候选商品，按 rank 排序")


class SubmissionSection(BaseModel):
    """真实下单参数与结果（提交后才有内容）。"""

    payload: dict[str, Any] = Field(default_factory=dict, description="构造出的真实下单参数")
    result: dict[str, Any] = Field(default_factory=dict, description="真实下单接口返回")
    missing_fields: list[str] = Field(default_factory=list, description="仍缺失的下单字段")


class OrderPreview(BaseModel):
    """对话过程中的订单预览，供前端侧边栏/卡片渲染。"""

    service_type: str | None = Field(default=None, description="服务类型")
    service_type_display: str | None = Field(
        default=None,
        description="展示用服务类型，如 托管维修（客房）",
    )
    status: OrderStatus | str | None = Field(default=None, description="订单状态")
    order_info: OrderInfo = Field(default_factory=OrderInfo, description="已收集的订单信息")
    products: ProductSection = Field(default_factory=ProductSection, description="商品匹配与选择")
    missing_info: list[str] = Field(default_factory=list, description="仍需用户补充的字段名")
    submission: SubmissionSection = Field(default_factory=SubmissionSection, description="提交阶段数据")


def product_raw_to_option(
    raw: dict[str, Any],
    *,
    rank: int,
    selected_code: str | None,
) -> ProductOption:
    """将商品库原始字段映射为 API 对外结构。"""
    code = str(raw.get("service_product_code") or "")
    return ProductOption(
        code=code,
        name=str(raw.get("service_product_name") or ""),
        service_type=str(raw.get("service_order_type") or raw.get("product_type") or ""),
        category=raw.get("category"),
        unit=raw.get("unit"),
        price=raw.get("price"),
        price_status=raw.get("price_status"),
        repair_category=raw.get("repair_category"),
        fault_phenomenon=raw.get("fault_phenomenon"),
        related_area=raw.get("related_area"),
        remark=raw.get("remark"),
        score=raw.get("score"),
        rank=rank,
        is_recommended=rank == 1,
        is_selected=bool(code and code == selected_code),
    )


def build_product_section(
    *,
    products: list[dict[str, Any]],
    selected_code: str | None,
    search_status: str | None,
    search_query: str | None,
    search_feedback: str | None,
) -> ProductSection:
    """将状态机中的商品列表映射为 API 对外结构。"""
    from graph.products import resolve_selected_code

    resolved_code = resolve_selected_code(products, selected_code)

    items = [
        product_raw_to_option(raw, rank=index, selected_code=resolved_code)
        for index, raw in enumerate(products, start=1)
        if raw.get("service_product_code")
    ]

    return ProductSection(
        status=search_status,
        query=search_query,
        feedback=search_feedback,
        selected_code=resolved_code,
        items=items,
    )


def build_order_preview_model(state: dict[str, Any]) -> OrderPreview | None:
    """从 LangGraph state 构造结构化 OrderPreview。"""
    from graph.products import derive_product_section_fields, get_selected_product

    order_info_raw = state.get("order_info") or {}
    products = state.get("products") or []
    selected_code = state.get("selected_product_code")
    real_order_payload = state.get("real_order_payload") or {}
    real_order_result = state.get("real_order_result") or {}

    if (
        not order_info_raw
        and not products
        and not real_order_payload
        and not real_order_result
    ):
        return None

    search_status, search_query, search_feedback = derive_product_section_fields(state)
    service_type = state.get("service_type")
    if not service_type and products:
        selected = get_selected_product(products, selected_code)
        service_type = selected.get("service_order_type") or None

    return OrderPreview(
        service_type=service_type,
        service_type_display=state.get("service_type_display"),
        status=state.get("status"),
        order_info=OrderInfo.model_validate(order_info_raw),
        products=build_product_section(
            products=products,
            selected_code=selected_code,
            search_status=search_status,
            search_query=search_query,
            search_feedback=search_feedback,
        ),
        missing_info=state.get("missing_info") or [],
        submission=SubmissionSection(
            payload=real_order_payload,
            result=real_order_result,
            missing_fields=state.get("real_order_missing_fields") or [],
        ),
    )
