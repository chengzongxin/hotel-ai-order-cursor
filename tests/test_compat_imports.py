def test_legacy_package_imports_still_resolve() -> None:
    from config.settings import settings
    from domain.service_types import SERVICE_TYPE_MANAGED_REPAIR
    from graph.builder import build_graph
    from rag.product_store import ProductVectorStore

    assert settings is not None
    assert SERVICE_TYPE_MANAGED_REPAIR == "托管维修"
    assert callable(build_graph)
    assert ProductVectorStore.__name__ == "ProductVectorStore"
