"""Affiliate link preparation: Travelpayouts Partner Links API + click tracker."""

from __future__ import annotations

import random
import re
import string
from typing import Any, Dict, List, Optional, Tuple

from .env import ConfigError, get, need
from .http import HTTPError, join_url, request_json

DEFAULT_TP_API = "https://api.travelpayouts.com"
MAX_LINKS_PER_REQUEST = 10
_CODE_RE = re.compile(r"[^a-z0-9-]+")


class TravelpayoutsLinks:
    """Create branded partner links with per-platform ``sub_id`` tracking.

    Docs: ``POST /links/v1/create`` with
    ``{"trs": <project id>, "marker": <marker>, "shorten": true,
    "links": [{"url": "...", "sub_id": "..."}]}``.
    """

    def __init__(self, env: Dict[str, str]) -> None:
        self.token = get(env, "TRAVELPAYOUTS_TOKEN", "TRAVELPAYOUTS_API_TOKEN")
        self.marker = get(env, "TRAVELPAYOUTS_MARKER")
        self.trs = get(env, "TRAVELPAYOUTS_TRS")
        self.api_base = (get(env, "TRAVELPAYOUTS_API_BASE", default=DEFAULT_TP_API)).rstrip("/")

    @property
    def available(self) -> bool:
        return bool(self.token and self.marker and self.trs)

    def missing(self) -> List[str]:
        missing = []
        if not self.token:
            missing.append("TRAVELPAYOUTS_TOKEN")
        if not self.marker:
            missing.append("TRAVELPAYOUTS_MARKER")
        if not self.trs:
            missing.append("TRAVELPAYOUTS_TRS")
        return missing

    def create(self, items: List[Tuple[str, str]]) -> List[str]:
        """Create partner links for ``[(url, sub_id), ...]`` (max 10)."""
        if not self.available:
            raise ConfigError(
                "Для партнёрских ссылок не хватает: {}".format(", ".join(self.missing()))
            )
        if not items:
            raise ConfigError("Нет ссылок для конвертации.")
        if len(items) > MAX_LINKS_PER_REQUEST:
            raise ConfigError("Links API принимает не более 10 ссылок за запрос.")
        body: Dict[str, Any] = {
            "trs": int(self.trs) if self.trs.isdigit() else self.trs,
            "marker": int(self.marker) if self.marker.isdigit() else self.marker,
            "shorten": True,
            "links": [{"url": url, "sub_id": sub_id} for url, sub_id in items],
        }
        data = request_json(
            "POST",
            join_url(self.api_base, "/links/v1/create"),
            headers={"X-Access-Token": self.token},
            json_body=body,
        )
        result = data.get("result") or {}
        links = result.get("links") or []
        urls: List[str] = []
        for item in links:
            if not isinstance(item, dict):
                continue
            partner = item.get("partner_url") or item.get("url")
            if partner:
                urls.append(str(partner))
        if len(urls) != len(items):
            raise ConfigError(
                "Links API вернул {} ссылок из {}: {}".format(
                    len(urls), len(items), str(data)[:300]
                )
            )
        return urls


class LinkTracker:
    """Own click tracker: ``POST /admin/links`` → ``/r/<code>`` short URL."""

    def __init__(self, env: Dict[str, str]) -> None:
        self.base_url = (get(env, "LINK_TRACKER_BASE")).rstrip("/")
        self.admin_token = get(env, "LINK_TRACKER_ADMIN_TOKEN", "LINK_TRACKER_STATS_TOKEN")

    @property
    def available(self) -> bool:
        return bool(self.base_url and self.admin_token)

    def verify(self) -> Dict[str, Any]:
        data = request_json(
            "GET",
            join_url(self.base_url, "/admin/links"),
            headers={"x-token": self.admin_token},
        )
        links = data.get("links") or []
        return {"ok": True, "links": len(links)}

    def wrap(self, target: str, network: str, label: str = "") -> str:
        if not self.available:
            raise ConfigError("Не заданы LINK_TRACKER_BASE / LINK_TRACKER_ADMIN_TOKEN")
        code = make_code(network)
        payload = {
            "code": code,
            "target": target,
            "channel": "affiliate-fanout",
            "network": network,
            "label": label,
            "active": True,
        }
        request_json(
            "POST",
            join_url(self.base_url, "/admin/links"),
            headers={"x-token": self.admin_token},
            json_body=payload,
        )
        return "{}/r/{}".format(self.base_url, code)


def make_code(network: str, length: int = 6) -> str:
    slug = _CODE_RE.sub("-", (network or "link").lower()).strip("-") or "link"
    suffix = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(length))
    return "fanout-{}-{}".format(slug, suffix)
