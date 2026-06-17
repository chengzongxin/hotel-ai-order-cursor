"""Order routing rules."""


def resolve_order_submit_route(service_type: str | None) -> str | None:
    route_map = {
        "托管维修": "managed_repair",
        "单次维修服务": "single_repair",
        "单次安装": "single_install",
        "单次测量": "single_measure",
    }
    return route_map.get(service_type or "")

