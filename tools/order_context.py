"""真实下单上下文：维保卡、用户资料、地址与联系人解析。"""

from __future__ import annotations

import asyncio
from typing import Any

from schemas.user import UserContext
from tools.order_submit_common import (
    DEFAULT_RESPONSE_TIME,
    DEFAULT_RESPONSE_TIME_UNIT,
    MANAGED_REPAIR_AREA_TREE_LIST,
    MANAGED_REPAIR_GLOBAL_CONFIG,
    USER_PROFILE_GET,
    JsonDict,
    clean_text,
    fetch_app_data,
    has_login_config,
    post_app,
)

import httpx


async def fetch_hosting_card(user: UserContext) -> JsonDict | None:
    from tools.hosting_card import fetch_hosting_card_with_diagnostics

    card, _diagnostics = await fetch_hosting_card_with_diagnostics(user)
    return card


async def fetch_user_profile(user: UserContext) -> JsonDict | None:
    return await fetch_app_data(USER_PROFILE_GET, user)


async def fetch_managed_repair_global_config(user: UserContext) -> JsonDict | None:
    return await fetch_app_data(MANAGED_REPAIR_GLOBAL_CONFIG, user)


async def fetch_managed_repair_area_tree(user: UserContext) -> list[JsonDict]:
    if not has_login_config(user):
        return []
    try:
        data = await post_app(MANAGED_REPAIR_AREA_TREE_LIST, {}, user)
    except httpx.HTTPError:
        return []
    if data.get("code") != 200:
        return []
    areas = data.get("data")
    return areas if isinstance(areas, list) else []


def hosting_card_to_selected_address(card: JsonDict) -> JsonDict:
    """对齐 App CreateHostingOrderStore.fetchHostingCard 构造的 selectedAddress。"""
    selected_address: JsonDict = {
        "province": card.get("province"),
        "city": card.get("city"),
        "area": card.get("area"),
        "provinceCode": card.get("provinceCode"),
        "cityCode": card.get("cityCode"),
        "areaCode": card.get("areaCode"),
        "address": card.get("address"),
        "simpleAddress": card.get("simpleAddress"),
        "houseNumber": card.get("houseNumber"),
        "lon": card.get("lon"),
        "lat": card.get("lat"),
        "hotelName": card.get("tenantName"),
        "comboCardId": card.get("id"),
        "contacts": card.get("contactName"),
        "phone": card.get("contactPhone"),
    }
    return {
        key: value
        for key, value in selected_address.items()
        if value not in (None, "")
    }


def user_profile_to_contacts(profile: JsonDict) -> JsonDict:
    contacts = (
        clean_text(profile.get("realName"))
        or clean_text(profile.get("nickname"))
        or clean_text(profile.get("workerName"))
    )
    phone = clean_text(profile.get("mobile"))
    return {key: value for key, value in {"contacts": contacts, "phone": phone}.items() if value}


def resolve_contacts(
    user: UserContext,
    user_profile: JsonDict | None,
    selected_address: JsonDict,
) -> tuple[str, str]:
    """联系人优先 userStore（profile 接口），其次网关 Header，最后维保卡。"""
    profile_contacts = user_profile_to_contacts(user_profile or {})
    contacts = (
        clean_text(profile_contacts.get("contacts"))
        or clean_text(user.contacts)
        or clean_text(selected_address.get("contacts"))
    )
    phone = (
        clean_text(profile_contacts.get("phone"))
        or clean_text(user.phone)
        or clean_text(selected_address.get("phone"))
    )
    return contacts, phone


def resolve_response_time(global_config: JsonDict | None, emergency_flag: int) -> tuple[int, str]:
    """对齐 App CreateHostingOrderStore.getResponseTimeForSubmit。"""
    if not global_config or global_config.get("responseTimeEnable") != 0:
        return DEFAULT_RESPONSE_TIME, DEFAULT_RESPONSE_TIME_UNIT
    if emergency_flag == 1:
        return (
            int(global_config.get("urgentBookTime") or 10),
            clean_text(global_config.get("urgentBookTimeUnit"), DEFAULT_RESPONSE_TIME_UNIT),
        )
    return (
        int(global_config.get("commonBookTime") or 10),
        clean_text(global_config.get("commonBookTimeUnit"), DEFAULT_RESPONSE_TIME_UNIT),
    )


def resolve_first_area(
    area_tree: list[JsonDict],
    area_scope: str,
) -> tuple[int | None, str | None]:
    if not area_scope:
        return None, None
    for area in area_tree:
        if clean_text(area.get("name")) == area_scope:
            area_id = area.get("id")
            return (int(area_id) if area_id is not None else None, clean_text(area.get("name")))
    return None, None


async def load_managed_repair_order_context(user: UserContext) -> JsonDict:
    hosting_card, user_profile, global_config, area_tree = await asyncio.gather(
        fetch_hosting_card(user),
        fetch_user_profile(user),
        fetch_managed_repair_global_config(user),
        fetch_managed_repair_area_tree(user),
    )

    selected_address = hosting_card_to_selected_address(hosting_card) if hosting_card else {}
    contacts, phone = resolve_contacts(user, user_profile, selected_address)

    return {
        "hosting_card": hosting_card,
        "user_profile": user_profile,
        "global_config": global_config,
        "area_tree": area_tree,
        "selected_address": selected_address,
        "contacts": contacts,
        "phone": phone,
        "hosting_card_error": None if hosting_card else "hosting card api returned empty data",
    }
