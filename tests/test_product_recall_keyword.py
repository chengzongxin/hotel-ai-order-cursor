"""商品召回关键词重叠纯逻辑测试（无 embedding 依赖）。"""

from rag.product_store import NO_FAULT_PENALTY, _has_keyword_overlap, _keyword_overlap_tokens


def test_keyword_overlap_tokens_expands_query_chars():
    tokens = _keyword_overlap_tokens("门把手", expand_chars=True)
    assert "门把手" in tokens
    assert "门" in tokens
    assert "把" in tokens


def test_keyword_overlap_tokens_product_side_no_expand():
    tokens = _keyword_overlap_tokens("门五金", expand_chars=False)
    assert "五金" in tokens
    assert "门" in tokens


def test_has_keyword_overlap_door_handle_and_hardware():
    assert _has_keyword_overlap("门把手 坏了", "门五金")


def test_has_keyword_overlap_ac_and_water_cabinet():
    assert not _has_keyword_overlap("空调 漏水", "水柜(中修)")


def test_has_keyword_overlap_ac_query():
    assert _has_keyword_overlap("空调 不制冷", "空调(小修)")


def test_no_fault_penalty_constant():
    assert NO_FAULT_PENALTY == 0.15
