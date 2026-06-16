import pytest
from langchain_core.messages import HumanMessage

from workflow.questions import build_ask_response


PRODUCTS = [
    {"service_product_code": "A", "service_product_name": "空调维修", "service_order_type": "单次维修服务"},
]


@pytest.mark.asyncio
async def test_ask_response_for_rejected_product_selection():
    response = await build_ask_response({"product_selection_rejected": True})

    assert response.question == "好的，请您再详细描述商品和故障现象，我再帮您推荐服务商品。"
    assert response.should_emit is True
    assert response.off_topic_count == 0


@pytest.mark.asyncio
async def test_ask_response_for_product_recommendations():
    response = await build_ask_response({"products": PRODUCTS, "selected_product_code": None})

    assert "为您推荐以下服务商品" in response.question
    assert response.should_emit is True


@pytest.mark.asyncio
async def test_ask_response_for_numbered_selection_with_missing_info():
    response = await build_ask_response(
        {
            "products": PRODUCTS,
            "selected_product_code": "A",
            "missing_info": ["expected_start_time"],
            "messages": [HumanMessage(content="第一个")],
        }
    )

    assert "已为您选择" in response.question
    assert "期待开工时间" in response.question
    assert response.should_emit is True


@pytest.mark.asyncio
async def test_ask_response_for_product_feedback_with_missing_info():
    response = await build_ask_response(
        {"missing_info": ["phone"]},
        product_search_feedback="已匹配到标准商品。",
    )

    assert response.question == "已匹配到标准商品。\n请问联系电话是多少？"
    assert response.should_emit is True
