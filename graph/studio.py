from graph.builder import build_graph

# LangGraph Studio 直接加载这个 graph 对象。
# Studio / LangGraph API 会自动管理 persistence，不要在这里传自定义 checkpointer。
graph = build_graph()
