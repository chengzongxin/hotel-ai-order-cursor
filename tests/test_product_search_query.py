"""商品检索 query 构造逻辑测试。"""

from graph.products import build_product_search_query


def test_build_query_with_product_and_fault():
    query = build_product_search_query(
        {"product": "空调", "fault": "不制冷"},
        last_user_message="1208空调不制冷",
    )
    assert query == "空调 不制冷"


def test_build_query_adds_install_hint_without_fault():
    query = build_product_search_query(
        {"product": "洗衣机"},
        last_user_message="帮我安装洗衣机",
    )
    assert "洗衣机" in query
    assert "安装" in query


def test_build_query_skips_install_hint_when_fault_present():
    query = build_product_search_query(
        {"product": "水龙头", "fault": "漏水"},
        last_user_message="安装水龙头",
    )
    assert query == "水龙头 漏水"
    assert "安装" not in query.split()
