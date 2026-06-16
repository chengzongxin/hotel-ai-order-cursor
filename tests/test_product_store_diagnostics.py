"""ProductVectorStore diagnostic behavior tests."""

from langchain_core.documents import Document

from repositories.product_store import ProductVectorStore


class FakeVectorStore:
    def __init__(self, results):
        self.results = results

    def similarity_search_with_relevance_scores(self, query, k):
        return self.results[:k]


def make_store(results):
    store = object.__new__(ProductVectorStore)
    store.vector_store = FakeVectorStore(results)
    return store


def doc(code, name, service_type, fault=""):
    return Document(
        page_content=f"{name} {fault}".strip(),
        metadata={
            "service_product_code": code,
            "service_product_name": name,
            "service_order_type": service_type,
            "fault_phenomenon": fault,
        },
    )


def test_search_with_diagnostics_reports_keyword_filter_and_scores():
    store = make_store(
        [
            (doc("A", "门锁", "托管维修", "打不开"), 0.91),
            (doc("B", "空调", "单次维修服务", "不制冷"), 0.89),
        ]
    )

    products, diagnostics = store.search_with_diagnostics(
        query="门锁 打不开",
        top_k=1,
        threshold=0,
        has_fault=True,
    )

    assert [item["service_product_code"] for item in products] == ["A"]
    assert diagnostics["returned_codes"] == ["A"]
    assert diagnostics["candidates"][0]["keyword_overlap"] is True
    assert diagnostics["candidates"][0]["included"] is True
    assert diagnostics["candidates"][1]["keyword_overlap"] is False
    assert diagnostics["candidates"][1]["filtered_reason"] == "keyword_mismatch"


def test_search_with_diagnostics_reports_fault_penalty():
    store = make_store(
        [
            (doc("A", "水龙头", "单次安装", ""), 0.9),
            (doc("B", "水龙头", "单次维修服务", "漏水"), 0.86),
        ]
    )

    products, diagnostics = store.search_with_diagnostics(
        query="水龙头 漏水",
        top_k=2,
        threshold=0,
        has_fault=True,
    )

    candidate_a = diagnostics["candidates"][0]
    assert candidate_a["service_product_code"] == "A"
    assert candidate_a["penalty"] > 0
    assert candidate_a["adjusted_score"] < candidate_a["vector_score"]
    assert [item["service_product_code"] for item in products] == ["B", "A"]


def test_search_with_diagnostics_reranks_by_fault_keyword_overlap():
    store = make_store(
        [
            (doc("A", "空调", "单次维修服务", "电机更换"), 0.9),
            (doc("B", "空调", "单次维修服务", "异物清除"), 0.86),
        ]
    )

    products, diagnostics = store.search_with_diagnostics(
        query="空调 有异物卡住",
        top_k=2,
        threshold=0,
        has_fault=True,
    )

    assert [item["service_product_code"] for item in products] == ["B", "A"]
    candidate_a = diagnostics["candidates"][0]
    candidate_b = diagnostics["candidates"][1]
    assert candidate_a["fault_keyword_overlap"] is False
    assert candidate_a["penalty"] > 0
    assert candidate_b["fault_keyword_overlap"] is True
    assert candidate_b["bonus"] > 0


def test_search_with_diagnostics_reports_below_threshold():
    store = make_store([(doc("A", "门锁", "托管维修", "打不开"), 0.4)])

    products, diagnostics = store.search_with_diagnostics(
        query="门锁 打不开",
        top_k=1,
        threshold=0.8,
        has_fault=False,
    )

    assert products == []
    assert diagnostics["returned_count"] == 0
    assert diagnostics["candidates"][0]["filtered_reason"] == "below_threshold"
