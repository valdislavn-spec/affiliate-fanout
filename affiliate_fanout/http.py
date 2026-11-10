"""Minimal HTTP helpers for the affiliate fan-out adapters (stdlib only)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
DEFAULT_TIMEOUT = 25.0


class HTTPError(Exception):
    """Non-2xx response or transport failure."""

    def __init__(self, message: str, status: int = 0, body: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.body = body


def request(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    json_body: Optional[Any] = None,
    form_body: Optional[Dict[str, Any]] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Tuple[int, str]:
    """Perform an HTTP request and return ``(status, body_text)``."""
    hdrs = {"Accept": "application/json", "User-Agent": USER_AGENT}
    hdrs.update(headers or {})
    data: Optional[bytes] = None
    if json_body is not None:
        data = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    elif form_body is not None:
        data = urllib.parse.urlencode(form_body, doseq=True).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/x-www-form-urlencoded")
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001 - best effort
            pass
        raise HTTPError(
            "HTTP {} {}: {}".format(exc.code, url.split("?")[0], body[:200]),
            status=exc.code,
            body=body,
        )
    except urllib.error.URLError as exc:
        raise HTTPError("network error for {}: {}".format(url.split("?")[0], exc.reason))
    except (TimeoutError, OSError) as exc:
        raise HTTPError("timeout/OS error for {}: {}".format(url.split("?")[0], exc))


def request_json(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    json_body: Optional[Any] = None,
    form_body: Optional[Dict[str, Any]] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """Like :func:`request` but parses JSON and rejects non-objects."""
    status, body = request(
        method,
        url,
        headers=headers,
        json_body=json_body,
        form_body=form_body,
        timeout=timeout,
    )
    try:
        data = json.loads(body) if body else {}
    except ValueError as exc:
        raise HTTPError("invalid JSON from {}: {}".format(url.split("?")[0], body[:120])) from exc
    if not isinstance(data, dict):
        raise HTTPError("expected JSON object from {}".format(url.split("?")[0]))
    if status >= 400:
        raise HTTPError("HTTP {} from {}".format(status, url.split("?")[0]), status=status)
    return data


def join_url(base: str, path: str) -> str:
    return "{}{}".format((base or "").rstrip("/"), path)
