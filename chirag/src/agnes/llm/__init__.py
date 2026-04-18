"""Shared OpenAI client helpers.

All phases that call OpenAI go through :mod:`openai_client` so rate-limit
semantics (``openai.RateLimitError`` + ``Retry-After`` header) are handled
in one place.
"""

from .openai_client import (
    is_rate_limited,
    make_client,
    retry_after_seconds,
)

__all__ = ["is_rate_limited", "make_client", "retry_after_seconds"]
