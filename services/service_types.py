"""Service type constants and routing policy."""

SERVICE_TYPE_MANAGED_REPAIR = "托管维修"
SERVICE_TYPE_SINGLE_REPAIR = "单次维修服务"
SERVICE_TYPE_SINGLE_INSTALL = "单次安装"
SERVICE_TYPE_SINGLE_MEASURE = "单次测量"

MANAGED_REPAIR_ROUTE = "managed_repair"
SINGLE_REPAIR_ROUTE = "single_repair"
SINGLE_INSTALL_ROUTE = "single_install"
SINGLE_MEASURE_ROUTE = "single_measure"

ORDER_SUBMIT_ROUTE_BY_SERVICE_TYPE = {
    SERVICE_TYPE_MANAGED_REPAIR: MANAGED_REPAIR_ROUTE,
    SERVICE_TYPE_SINGLE_REPAIR: SINGLE_REPAIR_ROUTE,
    SERVICE_TYPE_SINGLE_INSTALL: SINGLE_INSTALL_ROUTE,
    SERVICE_TYPE_SINGLE_MEASURE: SINGLE_MEASURE_ROUTE,
}

REPAIR_SERVICE_TYPES = {SERVICE_TYPE_MANAGED_REPAIR, SERVICE_TYPE_SINGLE_REPAIR}


def resolve_order_submit_route(service_type: str | None) -> str | None:
    """Map a business service type to the submit route used by the UI/API."""

    return ORDER_SUBMIT_ROUTE_BY_SERVICE_TYPE.get(service_type or "")


def is_managed_repair(service_type: str | None) -> bool:
    return service_type == SERVICE_TYPE_MANAGED_REPAIR


def is_repair_service(service_type: str | None) -> bool:
    return service_type in REPAIR_SERVICE_TYPES
