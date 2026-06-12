from __future__ import annotations

from typing import Any

from schemas.user import UserContext
from tools.order_submit import HOSTING_CARD_GET, _has_login_config, _post_app

JsonDict = dict[str, Any]

HOSTING_CARD_STATUS_LABELS = {
    0: "未生效",
    1: "生效中",
    2: "已过期",
    3: "已停用",
}


def clean_text(value: object, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip() or default


def to_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def format_hosting_card_status(status: object) -> str:
    status_code = to_int(status)
    if status_code is None:
        return clean_text(status, "未知")
    return HOSTING_CARD_STATUS_LABELS.get(status_code, f"未知状态({status_code})")


def first_text(item: dict[str, object], *keys: str) -> str:
    for key in keys:
        text = clean_text(item.get(key))
        if text:
            return text
    return ""


def normalize_hosting_scope_item(item: object) -> JsonDict | None:
    if not isinstance(item, dict):
        return None

    spu_id = to_int(item.get("scopeRepairSpuId") or item.get("spuId") or item.get("id"))
    name = first_text(
        item,
        "scopeRepairSpuName",
        "repairSpuName",
        "serviceSpuName",
        "spuName",
        "templateName",
        "name",
    )
    area = first_text(item, "secondAreaName", "managedRepairAreaName", "firstAreaName", "areaName")
    code = first_text(item, "scopeRepairSpuCode", "spuCode", "templateCode", "code")

    if not name and spu_id is None and not code:
        return None

    return {
        "spu_id": spu_id,
        "spu_code": code or None,
        "spu_name": name or (f"SPU {spu_id}" if spu_id is not None else code),
        "area": area or None,
    }


def normalize_hosting_scope_items(items: object) -> list[JsonDict]:
    scope_items = items if isinstance(items, list) else []
    return [
        scope
        for scope in (normalize_hosting_scope_item(item) for item in scope_items)
        if scope is not None
    ]


async def fetch_hosting_card_with_diagnostics(user: UserContext) -> tuple[JsonDict | None, JsonDict]:
    """查询维保卡，并保留接口返回信息用于排查。"""

    if not _has_login_config(user):
        return None, {
            "endpoint": HOSTING_CARD_GET,
            "reason": "missing_login_config",
            "message": "缺少 access_token 或 tenant_id，未调用维保卡接口。",
            "code": None,
            "data": None,
            "raw_response": None,
        }

    try:
        raw_response = await _post_app(HOSTING_CARD_GET, {}, user)
    except Exception as exc:
        return None, {
            "endpoint": HOSTING_CARD_GET,
            "reason": "http_error",
            "message": f"{type(exc).__name__}: {exc}",
            "code": None,
            "data": None,
            "raw_response": None,
        }

    code = raw_response.get("code")
    message = clean_text(raw_response.get("msg") or raw_response.get("message"))
    body = raw_response.get("data")
    diagnostics: JsonDict = {
        "endpoint": HOSTING_CARD_GET,
        "reason": "ok",
        "code": code,
        "message": message,
        "data": body,
        "raw_response": raw_response,
    }

    if code != 200:
        diagnostics["reason"] = "api_non_200"
        return None, diagnostics
    if not isinstance(body, dict) or not body:
        diagnostics["reason"] = "empty_or_invalid_data"
        return None, diagnostics
    return body, diagnostics
