"""Environment loading for affiliate-fanout.

Values are read from a ``.env`` file (optional) and from ``os.environ``
(process environment wins over the file). Secrets are never printed or logged:
only presence/length is reported by ``--verify``.
"""

from __future__ import annotations

import os
from typing import Dict, Iterable, Optional


def parse_env_file(path: str) -> Dict[str, str]:
    values: Dict[str, str] = {}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for raw in handle:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    values[key] = value
    except FileNotFoundError:
        return {}
    return values


def load_env(path: Optional[str] = None, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Load env file (if any), then overlay process environment and extras."""
    values: Dict[str, str] = {}
    if path:
        values.update(parse_env_file(path))
    values.update({k: v for k, v in os.environ.items() if isinstance(v, str)})
    if extra:
        values.update(extra)
    return values


class ConfigError(Exception):
    """Required configuration is missing."""


def need(env: Dict[str, str], *keys: str) -> str:
    """Return the first non-empty value for ``keys`` or raise ConfigError."""
    for key in keys:
        value = (env.get(key) or "").strip()
        if value:
            return value
    raise ConfigError("Не задано: {}".format(" / ".join(keys)))


def get(env: Dict[str, str], *keys: str, default: str = "") -> str:
    for key in keys:
        value = (env.get(key) or "").strip()
        if value:
            return value
    return default


def has(env: Dict[str, str], *keys: str) -> bool:
    return bool(get(env, *keys))


def masked_length(env: Dict[str, str], key: str) -> str:
    value = env.get(key) or ""
    if not value:
        return "missing"
    return "set(len={})".format(len(value))


def env_keys_with_prefix(env: Dict[str, str], prefix: str) -> Iterable[tuple]:
    """Yield ``(key, value)`` pairs for non-empty values with the prefix."""
    for key in sorted(env):
        if key.startswith(prefix) and (env.get(key) or "").strip():
            yield key, env[key].strip()
