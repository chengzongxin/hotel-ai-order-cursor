from __future__ import annotations

from langchain_core.tools import tool

from schemas.user import UserContext, user_from_runtime_config
from tools.hosting_card import (
    clean_text,
    fetch_hosting_card_with_diagnostics,
    format_hosting_card_status,
    normalize_hosting_scope_items,
)
from tools.protocol import ToolErrorCode, ToolResult, error_response, success_response

JsonDict = dict[str, object]


def _build_scope_summary(card: dict[str, object], scopes: list[JsonDict]) -> str:
    card_name = clean_text(card.get("comboName"), "未命名维保卡")
    status = format_hosting_card_status(card.get("status"))
    hotel_name = clean_text(card.get("tenantName"))
    address = clean_text(card.get("address") or card.get("simpleAddress"))

    lines = [f"当前用户维保卡：{card_name}（状态：{status}）。"]
    if hotel_name:
        lines.append(f"适用酒店：{hotel_name}。")
    if address:
        lines.append(f"地址：{address}。")

    if not scopes:
        lines.append("该维保卡未返回具体维保商品范围。")
        return "\n".join(lines)

    lines.append(f"维保范围共 {len(scopes)} 项：")
    for scope in scopes[:30]:
        area = f"（区域：{scope['area']}）" if scope.get("area") else ""
        code = f"，编码：{scope['spu_code']}" if scope.get("spu_code") else ""
        lines.append(f"- {scope['spu_name']}{area}{code}")
    if len(scopes) > 30:
        lines.append(f"...另有 {len(scopes) - 30} 项未展开。")
    return "\n".join(lines)


async def query_hosting_scope(user: UserContext) -> ToolResult:
    """查询当前用户维保卡及其维保商品范围。"""

    try:
        card, interface_response = await fetch_hosting_card_with_diagnostics(user)
    except Exception as exc:
        return error_response(
            error_code=ToolErrorCode.UPSTREAM_ERROR,
            message=f"查询维保卡接口失败：{exc}",
        )

    if not card:
        return success_response(
            data={
                "has_hosting_card": False,
                "summary": "当前用户没有可用维保卡，暂时无法查询维保范围。",
                "scopes": [],
                "interface_response": interface_response,
            },
            message="hosting card not found",
        )

    scopes = normalize_hosting_scope_items(card.get("scopeRepairSpuIdList"))

    data: JsonDict = {
        "has_hosting_card": True,
        "hosting_card_id": card.get("id"),
        "hosting_card_name": card.get("comboName"),
        "hosting_card_status": card.get("status"),
        "hosting_card_status_display": format_hosting_card_status(card.get("status")),
        "hotel_name": card.get("tenantName"),
        "address": card.get("address") or card.get("simpleAddress"),
        "scope_count": len(scopes),
        "scopes": scopes,
        "summary": _build_scope_summary(card, scopes),
        "interface_response": interface_response,
    }
    return success_response(data=data, message="hosting scope queried")


@tool
async def query_hosting_scope_tool() -> ToolResult:
    """查询当前登录用户的维保卡维保范围，返回维保卡状态、酒店信息和维保商品列表。"""

    return await query_hosting_scope(user_from_runtime_config())
