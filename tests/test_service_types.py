"""Service type routing policy tests."""

from services.service_types import (
    SERVICE_TYPE_MANAGED_REPAIR,
    SERVICE_TYPE_SINGLE_INSTALL,
    SERVICE_TYPE_SINGLE_MEASURE,
    SERVICE_TYPE_SINGLE_REPAIR,
    is_managed_repair,
    is_repair_service,
    resolve_order_submit_route,
)


def test_resolve_order_submit_route_for_supported_service_types():
    assert resolve_order_submit_route(SERVICE_TYPE_MANAGED_REPAIR) == "managed_repair"
    assert resolve_order_submit_route(SERVICE_TYPE_SINGLE_REPAIR) == "single_repair"
    assert resolve_order_submit_route(SERVICE_TYPE_SINGLE_INSTALL) == "single_install"
    assert resolve_order_submit_route(SERVICE_TYPE_SINGLE_MEASURE) == "single_measure"


def test_resolve_order_submit_route_for_unknown_service_type():
    assert resolve_order_submit_route(None) is None
    assert resolve_order_submit_route("未知服务") is None


def test_repair_service_predicates():
    assert is_managed_repair(SERVICE_TYPE_MANAGED_REPAIR) is True
    assert is_managed_repair(SERVICE_TYPE_SINGLE_REPAIR) is False
    assert is_repair_service(SERVICE_TYPE_MANAGED_REPAIR) is True
    assert is_repair_service(SERVICE_TYPE_SINGLE_REPAIR) is True
    assert is_repair_service(SERVICE_TYPE_SINGLE_INSTALL) is False
