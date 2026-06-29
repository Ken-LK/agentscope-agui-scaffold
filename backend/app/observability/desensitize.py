"""PII desensitization (pure functions, no external deps — easy to unit test).

ID numbers (18/15 digit) are masked before phone numbers so the phone regex does
not eat an ID's leading digits. Field-name hints redact secret-ish values wholesale
so credentials never land in a log / trace.
"""

from __future__ import annotations

import re
from typing import Any

_ID_RE = re.compile(r"\d{17}[\dXx]|\d{15}")
_PHONE_RE = re.compile(r"1[3-9]\d{9}")

_SECRET_KEY_HINTS = (
    "api_key", "apikey", "access_key", "secret", "token", "password",
    "passwd", "credential", "authorization", "private_key",
)


def desensitize(value: str) -> str:
    """Mask Chinese ID numbers and mobile phone numbers in free text."""

    value = _ID_RE.sub(lambda m: m.group()[:4] + "****" + m.group()[-4:], value)
    value = _PHONE_RE.sub(lambda m: m.group()[:3] + "****" + m.group()[-4:], value)
    return value


def _is_secret_key(key: str) -> bool:
    k = key.lower()
    return any(h in k for h in _SECRET_KEY_HINTS)


def desensitize_mapping(data: Any) -> Any:
    """Recursively desensitize dict/list: secret-named keys redacted to ``***``;
    string values masked by regex."""

    if isinstance(data, dict):
        out: dict[str, Any] = {}
        for k, v in data.items():
            if isinstance(k, str) and _is_secret_key(k) and v not in (None, ""):
                out[k] = "***"
            else:
                out[k] = desensitize_mapping(v)
        return out
    if isinstance(data, list):
        return [desensitize_mapping(v) for v in data]
    if isinstance(data, str):
        return desensitize(data)
    return data
