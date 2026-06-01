from functools import lru_cache

from langchain.agents import create_agent

from graph.llm import get_llm
from graph.middleware import AGENT_MIDDLEWARE
from tools.registry import get_tools


@lru_cache
def get_assist_agent():
    """辅助 Agent，用于闲聊、商品查询等非主下单流程。"""

    return create_agent(
        model=get_llm(),
        tools=get_tools(),
        system_prompt=(
            "你是酒店 AI 下单助手的辅助 Agent。"
            "你可以回答用户的简单问题，也可以在需要时调用工具查询。"
            "如果用户询问商品或设备相关信息，可调用 search_product_tool 查询商品库，"
            "商品库涵盖维修、安装、测量、托管维修等服务类型。"
            "如果用户询问实时资讯、天气、新闻或商品库中没有的信息，可调用 web_search_tool 搜索互联网。"
            "不要直接提交订单；如果用户要下单，请引导用户提供房号、商品和问题。"
        ),
        middleware=AGENT_MIDDLEWARE,
        name="assist_agent",
    )
