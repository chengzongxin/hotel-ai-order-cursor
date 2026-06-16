"""Table-driven evals for order field policy."""

import pytest

from services.order_policy import (
    build_order_card_fields,
    collect_missing_order_info,
    normalize_order_card_update,
)


@pytest.mark.parametrize(
    ("service_type", "order_info", "expected_missing"),
    [
        (
            "托管维修",
            {"area": "客房", "room_number": "301", "product": "门锁", "fault": "打不开"},
            [],
        ),
        (
            "托管维修",
            {"area": "公区", "managed_repair_scope": "公区", "product": "电梯", "fault": "异响"},
            [],
        ),
        (
            "单次维修服务",
            {"product": "空调", "fault": "不制冷"},
            ["expected_start_time"],
        ),
        (
            "单次安装",
            {"product": "五金挂件", "expected_start_time": "明天上午"},
            ["goods_arrival_status"],
        ),
        (
            "单次测量",
            {"product": "窗帘", "expected_start_time": "周五下午"},
            [],
        ),
    ],
)
def test_required_order_fields_by_service_type(service_type, order_info, expected_missing):
    assert collect_missing_order_info(service_type, order_info) == expected_missing


def test_card_required_fields_add_contact_requirements():
    order_info = {
        "product": "空调",
        "fault": "不制冷",
        "expected_start_time": "明天上午",
    }
    card_fields = build_order_card_fields("单次维修服务", order_info, order_context={})

    missing = collect_missing_order_info("单次维修服务", order_info, card_fields)

    assert missing == ["contacts", "phone"]


def test_card_update_normalizes_managed_public_area():
    updated = normalize_order_card_update(
        order_info={"product": "灯", "fault": "不亮"},
        updates={"area_room": "大堂"},
        service_type="托管维修",
    )

    assert updated["area"] == "公区"
    assert updated["managed_repair_scope"] == "公区"
    assert updated["room_number"] == "/"
