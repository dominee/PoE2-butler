"""CSRF helpers.

We use a double-submit pattern: the session in Redis stores a random CSRF
token, and the SPA echoes it in the ``X-CSRF-Token`` header for every state-
changing request. The token is also exposed via the ``poe2b_csrf`` cookie
(readable from JS) so the SPA can pick it up.
"""

from __future__ import annotations

import hmac


def tokens_equal(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return hmac.compare_digest(a, b)
