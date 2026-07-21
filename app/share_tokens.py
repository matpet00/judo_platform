"""Opaque share tokens for public event / training links."""

from __future__ import annotations

import secrets


def new_share_token() -> str:
    """URL-safe token (~22 chars)."""
    return secrets.token_urlsafe(16)
