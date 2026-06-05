from __future__ import annotations

from typing import Any

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from config.settings import settings
from tools.protocol import ToolErrorCode, ToolResult, error_response, success_response

JsonDict = dict[str, Any]

# 查询 SPU 详情（admin-api，GET + query params）
ADMIN_API_SPU_PAGE = "/admin-api/system/service-spu/page"
# 托管维修下单（app-api，POST + JSON body）
CREATE_MANAGED_REPAIR_ORDER = "/app-api/order/company-managed-repair-order/create"

PLACEHOLDER_MARKERS = ("你的", "租户ID", "your-", "replace")


class SubmitOrderInput(BaseModel):
    order_info: JsonDict = Field(..., description="对话抽取出的订单信息")
    matched_product: JsonDict = Field(..., description="商品匹配工具返回的标准商品")
    submit: bool = Field(default=False, description="是否真实调用创建订单接口")


# ── 工具函数 ─────────────────────────────────────────────────────────────────


def _clean_text(value: object, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip() or default


def _is_placeholder(value: str) -> bool:
    text = _clean_text(value)
    return bool(text and any(marker in text for marker in PLACEHOLDER_MARKERS))


def _has_login_config() -> bool:
    return bool(
        settings.user_app_access_token
        and settings.user_app_tenant_id
        and not _is_placeholder(settings.user_app_access_token)
        and not _is_placeholder(settings.user_app_tenant_id)
    )


def _admin_headers() -> dict[str, str]:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if settings.user_app_tenant_id:
        headers["tenant-id"] = settings.user_app_tenant_id
    if settings.user_app_access_token:
        headers["Authorization"] = f"Bearer {settings.user_app_access_token}"
    return headers


def _app_headers() -> dict[str, str]:
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "type": settings.user_app_type,
        "platform": settings.user_app_platform,
    }
    if settings.user_app_access_token:
        headers["Authorization"] = f"Bearer {settings.user_app_access_token}"
    if settings.user_app_tenant_id:
        headers["tenant-id"] = settings.user_app_tenant_id
    if settings.user_app_version:
        headers["version"] = settings.user_app_version
    if settings.user_app_channel:
        headers["channel"] = settings.user_app_channel
    if settings.user_app_device_id:
        headers["device-id"] = settings.user_app_device_id
    if settings.user_app_spirit:
        headers["spirit"] = settings.user_app_spirit
    return headers


async def _post_admin(path: str, payload: JsonDict) -> JsonDict:
    url = settings.admin_api_base_url.rstrip("/") + path
    async with httpx.AsyncClient(timeout=settings.user_app_timeout_seconds) as client:
        response = await client.post(url, headers=_admin_headers(), json=payload)
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else {}


async def _post_app(path: str, payload: JsonDict) -> JsonDict:
    url = settings.user_app_base_url.rstrip("/") + path
    async with httpx.AsyncClient(timeout=settings.user_app_timeout_seconds) as client:
        response = await client.post(url, headers=_app_headers(), json=payload)
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else {}


# ── SPU 查询 ─────────────────────────────────────────────────────────────────


async def query_spu_by_name(name: str) -> JsonDict | None:
    """通过商品名称查询 SPU 详情，精确匹配优先，降级为首条结果。"""
    data = await _post_admin(
        ADMIN_API_SPU_PAGE,
        {"pageNo": 1, "pageSize": 10, "name": name},
    )
    items: list[JsonDict] = (data.get("data") or {}).get("list") or []
    if not items:
        return None
    for item in items:
        if _clean_text(item.get("name")) == name:
            return item
    return items[0]


# ── 故障匹配 ─────────────────────────────────────────────────────────────────


def _match_fault_phenomenon(fault: str, fault_list: list[JsonDict]) -> JsonDict | None:
    """将用户描述的故障匹配到 SPU 的 faultPhenomenonList，无匹配时取第一条。"""
    if not fault_list:
        return None
    if not fault:
        return fault_list[0]
    fault_text = fault.strip()
    for item in fault_list:
        if _clean_text(item.get("managedRepairFaultPhenomenonName")) == fault_text:
            return item
    for item in fault_list:
        name = _clean_text(item.get("managedRepairFaultPhenomenonName"))
        if name and (fault_text in name or name in fault_text):
            return item
    return fault_list[0]


# ── 地址默认值 ────────────────────────────────────────────────────────────────


def _settings_defaults() -> JsonDict:
    return {
        key: value
        for key, value in {
            "contacts": settings.user_app_default_contacts,
            "phone": settings.user_app_default_phone,
            "province": settings.user_app_default_province,
            "city": settings.user_app_default_city,
            "address": settings.user_app_default_address,
            "houseNumber": settings.user_app_default_house_number,
            "ideName": settings.user_app_default_ide_name,
            "provinceCode": settings.user_app_default_province_code,
            "cityCode": settings.user_app_default_city_code,
            "areaCode": settings.user_app_default_area_code,
            "lon": settings.user_app_default_lon,
            "lat": settings.user_app_default_lat,
        }.items()
        if value not in (None, "")
    }


# ── 订单号提取 ────────────────────────────────────────────────────────────────


def _extract_order_no(response: JsonDict) -> str | None:
    candidate_keys = ("orderNo", "order_no", "parentOrderNo", "parent_order_no")
    for key in candidate_keys:
        value = response.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    data = response.get("data")
    if isinstance(data, str) and data.strip():
        return data.strip()
    if isinstance(data, dict):
        for key in candidate_keys:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


# ── 构建下单参数 ──────────────────────────────────────────────────────────────


def build_managed_repair_order_payload(
    order_info: JsonDict,
    spu: JsonDict,
) -> tuple[JsonDict, list[str]]:
    """根据 SPU 详情和对话订单信息构建托管维修下单参数。

    返回 (payload, missing_fields)。missing_fields 非空时不应提交。
    """
    defaults = _settings_defaults()

    def _get(key: str, fallback_key: str | None = None) -> str:
        v = _clean_text(order_info.get(key))
        if v:
            return v
        return _clean_text(defaults.get(fallback_key or key))

    # 故障现象：将用户描述匹配到 SPU faultPhenomenonList
    fault_list: list[JsonDict] = spu.get("faultPhenomenonList") or []
    matched_fault = _match_fault_phenomenon(_clean_text(order_info.get("fault")), fault_list)
    spu_fault_list: list[JsonDict] = []
    if matched_fault:
        spu_fault_list = [{
            "faultPhenomenonId": matched_fault.get("managedRepairFaultPhenomenonId"),
            "faultPhenomenonName": matched_fault.get("managedRepairFaultPhenomenonName"),
            "commonRepairType": matched_fault.get("commonRepairType") or [],
        }]

    # 区域信息：
    # - firstAreaId/firstAreaName 来自 settings 默认值（父级区域，如"客房"/"公区"）
    # - secondAreaId/secondAreaName 从 SPU areaList 按 managed_repair_scope 匹配
    area_list: list[JsonDict] = spu.get("areaList") or []
    area_scope = _clean_text(order_info.get("managed_repair_scope") or order_info.get("area"))
    room_num = _clean_text(order_info.get("room_number"))
    urgency = _clean_text(order_info.get("urgency"))
    emergency_flag = 1 if urgency in {"urgent", "紧急"} else 0

    # 从 SPU areaList 中找与 area_scope 父级名称匹配的子区域
    matched_area: JsonDict = {}
    if area_list and area_scope:
        for item in area_list:
            if _clean_text(item.get("managedRepairAreaParentName")) == area_scope:
                matched_area = item
                break
        if not matched_area:
            matched_area = area_list[0]

    first_area_id = settings.managed_repair_first_area_id
    first_area_name = area_scope or settings.managed_repair_first_area_name or None
    second_area_id = (
        matched_area.get("managedRepairAreaId")
        or settings.managed_repair_second_area_id
    )
    second_area_name = (
        _clean_text(matched_area.get("managedRepairAreaName"))
        or settings.managed_repair_second_area_name
        or None
    )

    order_spu: JsonDict = {
        "spuId": spu.get("id"),
        "secondAreaId": second_area_id,
        "secondAreaName": second_area_name,
        "templateCode": _clean_text(spu.get("code")),
        "templateName": _clean_text(spu.get("name")),
        "templatePhoto": _clean_text(spu.get("icon")),
        "num": 1,
        "unit": _clean_text(spu.get("measureUnitName"), "个"),
        "unitType": "0",
        "spuFaultPhenomenonList": spu_fault_list,
    }

    order_detail: JsonDict = {
        "spuTypeId": spu.get("typeId"),
        "firstAreaId": first_area_id,
        "firstAreaName": first_area_name,
        "roomNum": room_num,
        "imageList": "",
        "orderSpuList": [order_spu],
    }

    contacts = _get("contacts")
    phone = _get("phone")
    address = _get("address")

    payload: JsonDict = {
        "contacts": contacts,
        "phone": phone,
        "ideName": _get("ideName"),
        "lon": order_info.get("lon") or defaults.get("lon"),
        "lat": order_info.get("lat") or defaults.get("lat"),
        "province": _get("province"),
        "city": _get("city"),
        "area": _clean_text(order_info.get("district")) or _clean_text(defaults.get("area")) or None,
        "provinceCode": _clean_text(defaults.get("provinceCode")) or None,
        "cityCode": _clean_text(defaults.get("cityCode")) or None,
        "areaCode": _clean_text(defaults.get("areaCode")) or None,
        "address": address,
        "hotelName": settings.managed_repair_hotel_name,
        "houseNumber": room_num,
        "responseTime": settings.managed_repair_response_time,
        "comboCardId": settings.managed_repair_combo_card_id,
        "responseTimeUnit": settings.managed_repair_response_time_unit,
        "emergencyFlag": emergency_flag,
        "orderDetailList": [order_detail],
        "confirmDuplicateSubmit": True,
    }

    missing: list[str] = [
        field
        for field, value in [("contacts", contacts), ("phone", phone), ("address", address)]
        if not value
    ]
    return payload, sorted(set(missing))


# ── 主入口 ────────────────────────────────────────────────────────────────────


async def submit_real_order(
    order_info: JsonDict,
    matched_product: JsonDict,
    submit: bool,
) -> ToolResult:
    """
    1. 通过匹配到的商品名查询 admin-api SPU 详情
    2. 构建托管维修下单参数
    3. 若 submit=True 且 USER_APP_SUBMIT_ENABLED=true，调用创建订单接口
    """
    product_name = _clean_text(matched_product.get("service_product_name"))

    spu: JsonDict = {}
    spu_query_error: str | None = None
    if product_name:
        try:
            result = await query_spu_by_name(product_name)
            print(f"SPU 查询结果: {result}")
            if result:
                spu = result
        except Exception as exc:
            print(f"SPU 查询错误: {exc}")
            spu_query_error = f"{type(exc).__name__}: {exc}"

    payload, missing_fields = build_managed_repair_order_payload(order_info, spu)

    data: JsonDict = {
        "request_payload": payload,
        "missing_fields": missing_fields,
        "submit_enabled": settings.user_app_submit_enabled,
        "submitted": False,
        "parent_order_no": None,
        "spu_detail": spu,
        "spu_query_error": spu_query_error,
    }

    should_submit = submit and settings.user_app_submit_enabled
    if not should_submit:
        return success_response(
            data=data,
            message="built order payload; real submit is disabled",
        )

    if missing_fields:
        return error_response(
            error_code=ToolErrorCode.INVALID_INPUT,
            message=f"cannot submit order, missing fields: {', '.join(missing_fields)}",
            data=data,
        )
    if not _has_login_config():
        return error_response(
            error_code=ToolErrorCode.INVALID_INPUT,
            message="cannot submit order, USER_APP_ACCESS_TOKEN or USER_APP_TENANT_ID is not configured",
            data=data,
        )

    try:
        create_result = await _post_app(CREATE_MANAGED_REPAIR_ORDER, payload)
        # 打印接口参数及返回
        print(f"下单接口参数: {payload}")
        print(f"下单接口返回: {create_result}")
        data["create_order_response"] = create_result
        order_no = _extract_order_no(create_result)
        data["parent_order_no"] = order_no
        data["submitted"] = create_result.get("code") == 200 and bool(order_no)
    except httpx.HTTPError as exc:
        return error_response(
            error_code=ToolErrorCode.UPSTREAM_ERROR,
            message=f"order api request failed: {exc}",
            data=data,
        )

    if not data["submitted"]:
        create_result = data.get("create_order_response") or {}
        if isinstance(create_result, dict):
            code = create_result.get("code")
            msg = create_result.get("msg") or create_result.get("message") or "no message"
            message = f"order api returned code={code}, msg={msg}, but no order number was found"
        else:
            message = "order api did not return a valid response"
        return error_response(
            error_code=ToolErrorCode.UPSTREAM_ERROR,
            message=message,
            data=data,
        )

    return success_response(data=data, message="order submitted")


@tool(args_schema=SubmitOrderInput)
async def submit_real_order_tool(
    order_info: JsonDict,
    matched_product: JsonDict,
    submit: bool = False,
) -> ToolResult:
    """查询商品详情并构造托管维修下单参数，在启用配置后调用真实下单接口。"""
    return await submit_real_order(
        order_info=order_info,
        matched_product=matched_product,
        submit=submit,
    )
