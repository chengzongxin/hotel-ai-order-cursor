"""Order workflow events and reducer helpers.

Events make important state transitions explicit. The reducer currently emits
LangGraph-compatible dict patches so it can be introduced incrementally.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class OrderWorkflowEvent(BaseModel):
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class UserMessageReceived(OrderWorkflowEvent):
    type: Literal["UserMessageReceived"] = "UserMessageReceived"


class ProductMatched(OrderWorkflowEvent):
    type: Literal["ProductMatched"] = "ProductMatched"


class ProductSelected(OrderWorkflowEvent):
    type: Literal["ProductSelected"] = "ProductSelected"


class OrderCardUpdated(OrderWorkflowEvent):
    type: Literal["OrderCardUpdated"] = "OrderCardUpdated"


class OrderConfirmed(OrderWorkflowEvent):
    type: Literal["OrderConfirmed"] = "OrderConfirmed"


class OrderSubmitted(OrderWorkflowEvent):
    type: Literal["OrderSubmitted"] = "OrderSubmitted"


class OrderCancelled(OrderWorkflowEvent):
    type: Literal["OrderCancelled"] = "OrderCancelled"


def event_to_state_patch(event: OrderWorkflowEvent) -> dict[str, Any]:
    patch = dict(event.payload)
    existing_events = patch.pop("order_events", None)
    events = existing_events if isinstance(existing_events, list) else []
    events.append(event.model_dump(mode="json"))
    patch["order_events"] = events
    patch["last_order_event"] = event.type
    return patch


def apply_order_event(
    state: dict[str, Any],
    event: OrderWorkflowEvent,
) -> dict[str, Any]:
    """Return a merged state projection for local preview/tests."""

    patch = event_to_state_patch(event)
    existing_events = state.get("order_events") if isinstance(state.get("order_events"), list) else []
    patch["order_events"] = [*existing_events, event.model_dump(mode="json")]
    return {**state, **patch}

