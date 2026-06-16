"""Backend/frontend product search contract guardrails."""

from pathlib import Path

from schemas.product import ProductSearchDiagnostics, ProductSearchResponse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_PRODUCT_TYPES = PROJECT_ROOT / "frontend/src/types/product.ts"


def test_product_search_response_schema_includes_diagnostics():
    schema = ProductSearchResponse.model_json_schema()

    assert "diagnostics" in schema["properties"]


def test_product_search_diagnostics_schema_keeps_core_fields():
    schema = ProductSearchDiagnostics.model_json_schema()

    expected_fields = {
        "query",
        "top_k",
        "threshold",
        "has_fault",
        "fetch_k",
        "fallback_to_vector_results",
        "returned_count",
        "returned_codes",
        "candidates",
    }

    assert expected_fields <= set(schema["properties"])


def test_frontend_product_types_mention_diagnostics_contract_fields():
    source = FRONTEND_PRODUCT_TYPES.read_text(encoding="utf-8")

    for field in [
        "ProductSearchDiagnostics",
        "ProductSearchDiagnosticCandidate",
        "diagnostics?",
        "vector_score?",
        "adjusted_score?",
        "fault_keyword_overlap?",
        "bonus?",
        "filtered_reason?",
        "fallback_to_vector_results?",
    ]:
        assert field in source
