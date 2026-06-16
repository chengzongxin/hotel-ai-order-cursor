from langchain_tavily import TavilySearch

from core.settings import settings

web_search_tool = TavilySearch(
    max_results=5,
    topic="general",
    tavily_api_key=settings.tavily_api_key,
)
web_search_tool.name = "web_search_tool"
web_search_tool.description = "使用 Tavily 搜索互联网获取最新信息，适用于用户询问实时资讯、天气、新闻等商品库中没有的内容。"
