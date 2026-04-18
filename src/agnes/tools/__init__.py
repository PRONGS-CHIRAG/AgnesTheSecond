"""Agnes tool adapters (MCP-style external service wrappers).

Currently provides the ``WebSearchProvider`` Protocol plus a Tavily-backed
implementation used by the Phase 5 function-calling loop.
"""

from .web_search import (
    SearchHit,
    TavilySearchProvider,
    WebSearchError,
    WebSearchProvider,
)

__all__ = [
    "SearchHit",
    "TavilySearchProvider",
    "WebSearchError",
    "WebSearchProvider",
]
