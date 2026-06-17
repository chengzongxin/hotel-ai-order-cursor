"""LangGraph 状态机常量与阶段定义。"""

MAX_RETRY_COUNT = 2

CANCEL_ORDER_KEYWORDS = ("取消", "不用了", "不提交", "先算了", "撤销", "放弃", "不要了")
PUBLIC_AREA_KEYWORDS = (
    "公区",
    "公共区域",
    "大厅",
    "大堂",
    "接待区",
    "公区卫生间",
    "公共厕所",
    "布草间",
    "办公室",
    "洗衣房",
    "员工区",
    "走廊",
    "过道",
    "电梯",
    "电梯厅",
    "前台",
    "餐厅",
    "会议室",
    "楼梯间",
    "楼顶",
    "健身房",
    "停车场",
    "仓库",
    "设备间",
)
GUEST_ROOM_KEYWORDS = (
    "客房",
    "房间",
    "房里",
    "屋内",
    "住客区",
    "维修房",
    "客房楼层",
    "卫生间",
    "淋浴间",
)
VALID_MANAGED_REPAIR_SCOPES = {"客房", "公区"}
PRODUCT_NONE_SELECTIONS = {"0", "以上都不符合", "都不符合", "不符合", "没有合适", "没有匹配"}

PHASE_IDLE = "idle"
PHASE_PRODUCT_SELECTION = "product_selection"
PHASE_PRE_ORDER = "pre_order"
PHASE_COLLECTING = "collecting"
PHASE_SUBMITTED = "submitted"
PHASE_CANCELLED = "cancelled"
ACTIVE_ORDER_PHASES = {PHASE_COLLECTING, PHASE_PRODUCT_SELECTION, PHASE_PRE_ORDER}
