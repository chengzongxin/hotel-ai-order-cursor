from workflow.order_defaults import normalize_order_defaults


def test_repair_defaults_add_normal_urgency():
    normalized = normalize_order_defaults(
        service_type="单次维修服务",
        order_info={"product": "空调", "fault": "不制冷"},
    )

    assert normalized["urgency"] == "medium"


def test_goods_arrival_status_is_normalized_or_removed():
    assert normalize_order_defaults(
        service_type="单次安装",
        order_info={"goods_arrival_status": "已到场"},
    )["goods_arrival_status"] == "已到场"

    assert "goods_arrival_status" not in normalize_order_defaults(
        service_type="单次安装",
        order_info={"goods_arrival_status": "不确定的状态"},
    )


def test_managed_repair_public_area_clears_room_number():
    normalized = normalize_order_defaults(
        service_type="托管维修",
        order_info={"area": "大堂", "product": "灯", "fault": "不亮"},
        last_user_message="大堂灯不亮",
    )

    assert normalized["managed_repair_scope"] == "公区"
    assert normalized["area"] == "公区"
    assert normalized["room_number"] == "/"


def test_managed_repair_room_number_wins_as_guest_room():
    normalized = normalize_order_defaults(
        service_type="托管维修",
        order_info={"area": "大堂", "room_number": "301"},
        last_user_message="301 门锁打不开",
    )

    assert normalized["managed_repair_scope"] == "客房"
    assert normalized["area"] == "客房"
    assert normalized["room_number"] == "301"


def test_expected_start_time_is_inferred_from_latest_message():
    normalized = normalize_order_defaults(
        service_type="单次测量",
        order_info={"expected_start_time": "明天"},
        last_user_message="上午十点",
    )

    assert normalized["expected_start_time"] == "明天 上午十点"
