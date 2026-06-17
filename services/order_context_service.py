"""Order context loading service."""

from schemas.user import UserContext
from tools.order_context import load_managed_repair_order_context


async def load_order_context(user: UserContext) -> dict[str, object]:
    try:
        return await load_managed_repair_order_context(user)
    except Exception as exc:
        return {
            "context_error": f"{type(exc).__name__}: {exc}",
            "selected_address": {},
            "contacts": None,
            "phone": None,
        }

