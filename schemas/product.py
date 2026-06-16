from pydantic import BaseModel, Field


class ProductItem(BaseModel):
    service_product_code: str
    service_product_name: str
    product_type: str
    category: str
    service_order_type: str
    unit: str
    price: str
    price_status: str
    related_category: str
    related_area: str
    fault_phenomenon: str
    remark: str


class ProductListResponse(BaseModel):
    total: int
    items: list[ProductItem]


class ProductSearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=10, ge=1, le=50)
    threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    has_fault: bool = Field(default=False, description="是否包含故障描述，为 True 时启用故障惩罚")
    include_diagnostics: bool = Field(default=False, description="是否返回检索解释诊断信息")


class ProductSearchResult(BaseModel):
    score: float
    service_product_code: str
    service_product_name: str
    service_order_type: str
    product_type: str
    related_area: str
    fault_phenomenon: str
    price: str
    unit: str


class ProductSearchDiagnosticCandidate(BaseModel):
    service_product_code: str | None = None
    service_product_name: str | None = None
    service_order_type: str | None = None
    fault_phenomenon: str | None = None
    vector_score: float | None = None
    keyword_overlap: bool | None = None
    fault_keyword_overlap: bool | None = None
    penalty: float | None = None
    bonus: float | None = None
    adjusted_score: float | None = None
    included: bool = False
    filtered_reason: str | None = None


class ProductSearchDiagnostics(BaseModel):
    query: str
    top_k: int | None = None
    threshold: float | None = None
    has_fault: bool = False
    fetch_k: int | None = None
    fallback_to_vector_results: bool = False
    returned_count: int | None = None
    returned_codes: list[str] = Field(default_factory=list)
    reason: str | None = None
    candidates: list[ProductSearchDiagnosticCandidate] = Field(default_factory=list)


class ProductSearchResponse(BaseModel):
    query: str
    count: int
    products: list[ProductSearchResult]
    diagnostics: ProductSearchDiagnostics | None = None
