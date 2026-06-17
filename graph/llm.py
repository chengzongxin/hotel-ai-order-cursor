from functools import lru_cache

import httpx
from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables.config import RunnableConfig, ensure_config, merge_configs

from config.settings import settings
from graph.llm_callbacks import get_llm_trace_handler


def get_llm_run_config(config: RunnableConfig | None = None) -> RunnableConfig:
    """合并当前 Runnable 上下文与 LLM 追踪 callback。

    仅挂在 get_llm().with_config(...) 上不够：with_structured_output、
    create_agent 等包装层不会继承该 callback，必须在每次 invoke/astream 传入。
    """
    handler = get_llm_trace_handler()
    base_config = config if config is not None else ensure_config()
    callbacks = base_config.get("callbacks")
    # LangGraph 运行时 callbacks 可能是 AsyncCallbackManager，不能 list() 迭代。
    if isinstance(callbacks, list) and handler in callbacks:
        return base_config
    return merge_configs(base_config, {"callbacks": [handler]})


@lru_cache
def get_llm() -> BaseChatModel:
    # 忽略系统 SOCKS/HTTP 代理，避免 Cursor 等 IDE 注入的本地代理导致 LLM 请求失败。
    http_async_client = httpx.AsyncClient(trust_env=False)
    return init_chat_model(
        model=settings.openai_model,
        model_provider="openai",
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key,
        temperature=settings.openai_temperature,
        extra_body={"enable_thinking": False},
        http_async_client=http_async_client,
    )
