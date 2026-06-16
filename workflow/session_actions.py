"""Deterministic session operations triggered by frontend UI actions."""

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from services.service_types import SERVICE_TYPE_MANAGED_REPAIR, resolve_order_submit_route
from workflow.checkpoint import checkpoint_path, get_graph_config
from workflow.constants import PHASE_PRE_ORDER
from workflow.order_context_loader import load_order_context
from workflow.order_defaults import normalize_order_defaults
from workflow.order_fields import (
    build_order_card_fields,
    collect_missing_order_info,
    normalize_order_card_update,
)
from workflow.preview import build_order_preview
from workflow.products import find_product_by_code, get_selected_product
from workflow.questions import build_missing_info_fallback_question
from workflow.session_access import ensure_session_access
from workflow.submission import empty_submission, get_effective_service_type, submit_order_from_state
from memory.postgres_log import save_conversation_log
from schemas.user import SessionAccessError, UserContext, require_user
from tools.hosting_coverage import check_hosting_product_coverage


def _builder_helpers():
    from workflow.builder import build_graph

    return build_graph


async def select_product_in_session(
    session_id: str,
    product_code: str,
    user: UserContext,
) -> dict[str, object]:
    """在前端点选商品后，更新会话中的 selected_product_code 与 service_type。"""
    build_graph = _builder_helpers()
    active_user = require_user(user)
    async with AsyncSqliteSaver.from_conn_string(str(checkpoint_path())) as checkpointer:
        await checkpointer.setup()
        graph = build_graph(checkpointer)
        config = get_graph_config(active_user, session_id)
        snapshot = await graph.aget_state(config)
        state = snapshot.values or {}
        if not state:
            raise SessionAccessError("会话不存在或尚未开始对话")
        ensure_session_access(state, active_user)

        products = state.get("products") or []
        selected = find_product_by_code(products, product_code)
        if not selected:
            raise ValueError(f"商品 {product_code} 不在当前检索结果中")

        service_type = selected.get("service_order_type") or state.get("service_type")
        order_info = normalize_order_defaults(
            service_type=service_type,
            order_info=state.get("order_info", {}),
            last_user_message=state.get("last_user_message", ""),
        )
        effective_service_type = service_type
        coverage_result: dict[str, object] = {}
        if service_type == SERVICE_TYPE_MANAGED_REPAIR:
            result = await check_hosting_product_coverage(
                order_info=order_info,
                matched_product=selected,
                user=active_user,
            )
            coverage_result = result.get("data") or {}
            effective_service_type = str(coverage_result.get("effective_service_type") or service_type)
            order_info = normalize_order_defaults(
                service_type=effective_service_type,
                order_info=order_info,
                last_user_message=state.get("last_user_message", ""),
            )
        else:
            coverage_result = {
                "checked": False,
                "covered": None,
                "reason": "非托管维修商品，无需校验维保卡范围",
                "effective_service_type": service_type,
            }
        order_context = await load_order_context(active_user)
        order_card_fields = build_order_card_fields(
            service_type=effective_service_type,
            order_info=order_info,
            order_context=order_context,
        )
        missing_info = collect_missing_order_info(effective_service_type, order_info, order_card_fields)

        update = {
            "selected_product_code": product_code.strip(),
            "service_type": service_type,
            "effective_service_type": effective_service_type,
            "coverage_result": coverage_result,
            "order_submit_route": resolve_order_submit_route(effective_service_type),
            "order_info": order_info,
            "order_context": order_context,
            "order_card_fields": order_card_fields,
            "missing_info": missing_info,
            "phase": PHASE_PRE_ORDER,
            "submission": empty_submission(),
            "product_selection_rejected": False,
        }
        await graph.aupdate_state(config, update, as_node="search_product_node")

        merged_state = dict(state)
        merged_state.update(update)
        order_preview = build_order_preview(merged_state)
        if order_preview is None:
            raise ValueError("更新商品后无法生成订单预览")

        product_name = selected.get("service_product_name") or product_code
        repair_level = selected.get("repair_category") or selected.get("product_type") or selected.get("service_order_type") or "待确认"
        message = f"好的，已为您选择【{product_name}（{repair_level}）】，正在生成预下单卡片。"
        if missing_info:
            message = f"{message}\n{build_missing_info_fallback_question(missing_info)}"

        return {
            "session_id": session_id,
            "order_preview": order_preview,
            "message": message,
        }


async def update_order_info_in_session(
    session_id: str,
    updates: dict[str, object],
    user: UserContext,
) -> dict[str, object]:
    """前端编辑预下单卡片后，同步更新当前会话状态。"""
    build_graph = _builder_helpers()
    active_user = require_user(user)
    async with AsyncSqliteSaver.from_conn_string(str(checkpoint_path())) as checkpointer:
        await checkpointer.setup()
        graph = build_graph(checkpointer)
        config = get_graph_config(active_user, session_id)
        snapshot = await graph.aget_state(config)
        state = snapshot.values or {}
        if not state:
            raise SessionAccessError("会话不存在或尚未开始对话")
        ensure_session_access(state, active_user)

        selected_product = get_selected_product(
            state.get("products") or [],
            state.get("selected_product_code"),
            default_to_first=False,
        )
        if not selected_product:
            raise ValueError("请先选择商品，再修改预下单信息")

        service_type = get_effective_service_type(state)
        order_info = normalize_order_card_update(
            order_info=state.get("order_info", {}),
            updates=updates,
            service_type=service_type,
        )
        order_info = normalize_order_defaults(
            service_type=service_type,
            order_info=order_info,
            last_user_message=state.get("last_user_message", ""),
        )
        order_context = state.get("order_context") or {}
        if not order_context:
            order_context = await load_order_context(active_user)

        order_card_fields = build_order_card_fields(
            service_type=service_type,
            order_info=order_info,
            order_context=order_context,
        )
        missing_info = collect_missing_order_info(service_type, order_info, order_card_fields)

        update = {
            "order_info": order_info,
            "order_context": order_context,
            "order_card_fields": order_card_fields,
            "missing_info": missing_info,
            "phase": PHASE_PRE_ORDER,
            "submission": empty_submission(),
        }
        await graph.aupdate_state(config, update, as_node="prepare_order_context_node")

        merged_state = dict(state)
        merged_state.update(update)
        order_preview = build_order_preview(merged_state)
        if order_preview is None:
            raise ValueError("更新下单信息后无法生成订单预览")

        return {
            "session_id": session_id,
            "order_preview": order_preview,
            "message": "已更新预下单信息。",
        }


async def confirm_order_in_session(
    session_id: str,
    user: UserContext,
) -> dict[str, object]:
    """前端点击确认按钮时直接提交当前预下单，避免再次依赖 LLM 判断“确认”。"""
    build_graph = _builder_helpers()
    active_user = require_user(user)
    async with AsyncSqliteSaver.from_conn_string(str(checkpoint_path())) as checkpointer:
        await checkpointer.setup()
        graph = build_graph(checkpointer)
        config = get_graph_config(active_user, session_id)
        snapshot = await graph.aget_state(config)
        state = snapshot.values or {}
        if not state:
            raise SessionAccessError("会话不存在或尚未开始对话")
        ensure_session_access(state, active_user)

        selected_product = get_selected_product(
            state.get("products") or [],
            state.get("selected_product_code"),
            default_to_first=False,
        )
        if not selected_product:
            raise ValueError("请先选择商品，再确认下单")

        service_type = get_effective_service_type(state)
        order_info = normalize_order_defaults(
            service_type=service_type,
            order_info={
                **(state.get("order_info") or {}),
                "user_confirmed": True,
                "user_cancelled": False,
            },
            last_user_message=state.get("last_user_message", ""),
        )
        order_card_fields = state.get("order_card_fields") or []
        missing_info = collect_missing_order_info(service_type, order_info, order_card_fields)
        if missing_info:
            update = {
                "order_info": order_info,
                "missing_info": missing_info,
                "phase": PHASE_PRE_ORDER,
                "submission": empty_submission(),
            }
            await graph.aupdate_state(config, update, as_node="validate_order_node")
            merged_state = dict(state)
            merged_state.update(update)
            return {
                "session_id": session_id,
                "answer": build_missing_info_fallback_question(missing_info),
                "order_preview": build_order_preview(merged_state),
            }

        confirmed_state = dict(state)
        confirmed_state["order_info"] = order_info
        confirmed_state["missing_info"] = []
        submit_update = await submit_order_from_state(confirmed_state, active_user, emit=False)
        await graph.aupdate_state(config, submit_update, as_node="submit_node")

        merged_state = dict(confirmed_state)
        merged_state.update(submit_update)
        answer_messages = submit_update.get("messages") or []
        answer = str(answer_messages[-1].content) if answer_messages else "已处理确认下单请求。"
        await save_conversation_log(session_id, "human", "确认")
        await save_conversation_log(session_id, "ai", answer)
        return {
            "session_id": session_id,
            "answer": answer,
            "order_preview": build_order_preview(merged_state),
        }
