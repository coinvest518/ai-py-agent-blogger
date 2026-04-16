"""New LangGraph Agent.

This module defines a custom graph.

Lazy-load `graph` to avoid importing the entire agent package during
lightweight imports of submodules (prevents circular/expensive imports).
"""

__all__ = ["graph"]

def __getattr__(name: str):
    if name == "graph":
        from .graph import graph

        return graph
    raise AttributeError(f"module {__name__} has no attribute {name}")
