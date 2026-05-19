from langchain_core.tools import tool

from config.settings import settings


@tool
def qdrant_status() -> str:
    """返回 Qdrant 的预留配置信息，用于确认后续向量库接入点。"""

    return (
        "Qdrant is configured but not queried yet. "
        f"url={settings.qdrant_url}, collection={settings.qdrant_collection}"
    )
