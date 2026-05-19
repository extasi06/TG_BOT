"""Utilities for safely sending text in Telegram Markdown messages."""

from __future__ import annotations


def escape_markdown(text: str) -> str:
    """Escape Markdown markup characters for Telegram Markdown."""
    if not text:
        return ""
    # Order matters: escape backslashes first.
    text = text.replace("\\", "\\\\")
    for char in "*_[]()`:":
        text = text.replace(char, f"\\{char}")
    return text
