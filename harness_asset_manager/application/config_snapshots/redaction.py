from __future__ import annotations

import re

# Common patterns for API keys, tokens, bearer headers, and credentials
SECRET_KEY_PATTERN = re.compile(
    r'(?i)"?([a-z0-9_-]*(?:api[_-]?key|secret|token|bearer|password|credentials|auth|private[_-]?key))"?\s*[:=]\s*["\']?([^"\'\s,#{}]+)["\']?'
)

API_KEY_PREFIX_PATTERN = re.compile(
    r'\b(sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9_]{30,})\b'
)


def redact_secrets(content: str) -> str:
    """Redact known secret patterns and API key strings from configuration text."""
    redacted = SECRET_KEY_PATTERN.sub(r'"\1": "[REDACTED]"', content)
    redacted = API_KEY_PREFIX_PATTERN.sub(r'[REDACTED]', redacted)
    return redacted
