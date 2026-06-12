"""托管维修下单 payload 构造。"""

from __future__ import annotations

from typing import Any

from tools.order_context import resolve_first_area, resolve_response_time
from tools.order_submit_common import JsonDict, clean_text, resolve_product_quantity


def match_fault_phenomenon(fault: str, fault_list: list[JsonDict]) -> JsonDict | None:
    if not fault_list:
        return None
    if not fault:
        return fault_list[0]
    fault_text = fault.strip()
    for item in fault_list:
        if clean_text(item.get("managedRepairFaultPhenomenonName")) == fault_text:
            return item
    for item in fault_list:
        name = clean_text(item.get("managedRepairFaultPhenomenonName"))
        if name and (fault_text in name or name in fault_text):
            return item
    return fault_list[0]


_match_fault_phenomenon = match_fault_phenomenon


def build_managed_repair_order_payload(
    order_info: JsonDict,
    spu: JsonDict,
    selected_address: JsonDict,
    contacts: str,
    phone: str,
    area_tree: list[JsonDict],
    global_config: JsonDict | None,
    ide_name: str = "",
) -> tuple[JsonDict, list[str]]:
    fault_list: list[JsonDict] = spu.get("faultPhenomenonList") or []
    matched_fault = match_fault_phenomenon(clean_text(order_info.get("fault")), fault_list)
    spu_fault_list: list[JsonDict] = []
    if matched_fault:
        spu_fault_list = [{
            "faultPhenomenonId": matched_fault.get("managedRepairFaultPhenomenonId"),
            "faultPhenomenonName": matched_fault.get("managedRepairFaultPhenomenonName"),
            "commonRepairType": matched_fault.get("commonRepairType") or [],
        }]

    area_list: list[JsonDict] = spu.get("areaList") or []
    area_scope = clean_text(order_info.get("managed_repair_scope") or order_info.get("area"))
    room_num = clean_text(order_info.get("room_number"))
    urgency = clean_text(order_info.get("urgency"))
    emergency_flag = 1 if urgency in {"urgent", "紧急"} else 0

    matched_area: JsonDict = {}
    if area_list and area_scope:
        for item in area_list:
            if clean_text(item.get("managedRepairAreaParentName")) == area_scope:
                matched_area = item
                break
        if not matched_area:
            matched_area = area_list[0]

    first_area_id, first_area_name = resolve_first_area(area_tree, area_scope)
    if first_area_id is None and area_scope:
        first_area_name = area_scope or None

    second_area_id = matched_area.get("managedRepairAreaId")
    second_area_name = clean_text(matched_area.get("managedRepairAreaName")) or None
    product_quantity = resolve_product_quantity(order_info)

    order_spu: JsonDict = {
        "spuId": spu.get("id"),
        "secondAreaId": second_area_id,
        "secondAreaName": second_area_name,
        "templateCode": clean_text(spu.get("code")),
        "templateName": clean_text(spu.get("name")),
        "templatePhoto": clean_text(spu.get("icon")),
        "num": product_quantity,
        "unit": clean_text(spu.get("measureUnitName"), "个"),
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

    response_time, response_time_unit = resolve_response_time(global_config, emergency_flag)
    hotel_address = clean_text(selected_address.get("address"))
    house_number = (
        clean_text(order_info.get("house_number"))
        or clean_text(selected_address.get("houseNumber"))
        or room_num
    )

    payload: JsonDict = {
        "contacts": contacts,
        "phone": phone,
        "ideName": clean_text(order_info.get("ide_name")) or ide_name or None,
        "lon": selected_address.get("lon"),
        "lat": selected_address.get("lat"),
        "province": clean_text(selected_address.get("province")),
        "city": clean_text(selected_address.get("city")),
        "area": clean_text(order_info.get("district")) or clean_text(selected_address.get("area")) or None,
        "provinceCode": clean_text(selected_address.get("provinceCode")) or None,
        "cityCode": clean_text(selected_address.get("cityCode")) or None,
        "areaCode": clean_text(selected_address.get("areaCode")) or None,
        "address": hotel_address,
        "hotelName": clean_text(selected_address.get("hotelName")),
        "houseNumber": house_number,
        "simpleAddress": clean_text(selected_address.get("simpleAddress")) or None,
        "responseTime": response_time,
        "comboCardId": selected_address.get("comboCardId"),
        "responseTimeUnit": response_time_unit,
        "emergencyFlag": emergency_flag,
        "orderDetailList": [order_detail],
        "confirmDuplicateSubmit": True,
    }

    missing: list[str] = []
    for field, value in [
        ("contacts", contacts),
        ("phone", phone),
        ("address", hotel_address),
        ("province", payload["province"]),
        ("city", payload["city"]),
        ("provinceCode", payload["provinceCode"]),
        ("cityCode", payload["cityCode"]),
        ("hotelName", payload["hotelName"]),
        ("comboCardId", payload["comboCardId"]),
    ]:
        if value in (None, ""):
            missing.append(field)
    if not selected_address:
        missing.append("hosting_card")
    return payload, sorted(set(missing))
