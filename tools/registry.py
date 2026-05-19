from langchain_core.tools import BaseTool

from tools.basic import current_time, echo
from tools.maintenance import check_package_tool, create_order_tool, search_product_tool
from tools.qdrant_placeholder import qdrant_status
from tools.rag import recall_repair_fault_tool, recall_repair_product_tool


def get_tools() -> list[BaseTool]:
    return [
        current_time,
        echo,
        search_product_tool,
        recall_repair_product_tool,
        recall_repair_fault_tool,
        check_package_tool,
        create_order_tool,
        qdrant_status,
    ]
