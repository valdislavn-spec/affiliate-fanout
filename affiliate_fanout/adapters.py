"""Platform adapters for publishing affiliate posts via free APIs.

Each adapter is a small function with an explicit env dependency. Errors are
raised as :class:`AdapterError` so the CLI can report per-platform results and
continue with the remaining platforms.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html as html_lib
import json
import random
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .env import ConfigError, get, need
from .http import HTTPError, join_url, request, request_json

URL_RE = re.compile(r"https?://[^\s\"'<>]+")


class AdapterError(Exception):
    """A single platform failed (message is safe to show to the user)."""


@dataclass
class PublishResult:
    platform: str
    ok: bool
    url: str = ""
    detail: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {"platform": self.platform, "ok": self.ok, "url": self.url, "detail": self.detail}


# ---------------------------------------------------------------------------
# Telegram Bot API (via optional Cloudflare/Pipedream relay)
# ---------------------------------------------------------------------------
TG_DEFAULT_BASE = "https://api.telegram.org"


def _tg_call(env: Dict[str, str], method: str, params: Optional[Dict[str, Any]] = None) -> Any:
    token = need(env, "TELEGRAM_BOT_TOKEN")
    base = (get(env, "TELEGRAM_API_BASE", default=TG_DEFAULT_BASE)).rstrip("/")
    url = "{}/bot{}/{}".format(base, token, method)
    params = params or {}
    if method.startswith("get") or method == "getMe":
        query = urllib.parse.urlencode(params)
        status, body = request("GET", url + ("?" + query if query else ""))
    else:
        status, body = request("POST", url, form_body=params)
    try:
        data = json.loads(body) if body else {}
    except ValueError:
        raise AdapterError("Telegram вернул не JSON: {}".format(body[:120]))
    if not data.get("ok"):
        raise AdapterError(
            "Telegram API: {}".format(data.get("description") or body[:160])
        )
    return data.get("result")


def verify_telegram(env: Dict[str, str]) -> Dict[str, Any]:
    me = _tg_call(env, "getMe")
    channels: List[str] = []
    for key in sorted(env):
        if key.startswith("TELEGRAM_CHAT_ID_") and (env.get(key) or "").strip():
            try:
                chat = _tg_call(env, "getChat", {"chat_id": env[key].strip()})
                channels.append(chat.get("title") or chat.get("username") or key)
            except AdapterError:
                continue
    return {
        "ok": True,
        "account": "@{}".format(me.get("username") or me.get("first_name")),
        "channels": channels,
    }


def post_telegram(env: Dict[str, str], chat_id: str, text: str) -> PublishResult:
    message = _tg_call(
        env,
        "sendMessage",
        {"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"},
    )
    chat = message.get("chat") or {}
    username = chat.get("username")
    url = "https://t.me/{}".format(username) if username else ""
    return PublishResult(
        "telegram", True, url, "message_id={}".format(message.get("message_id"))
    )


# ---------------------------------------------------------------------------
# Tumblr API v2 (OAuth 1.0a)
# ---------------------------------------------------------------------------
TUMBLR_DEFAULT_BASE = "https://api.tumblr.com"


def _pct(value: Any) -> str:
    return urllib.parse.quote(str(value), safe="~")


def _oauth1_signature(
    method: str, url: str, params: Dict[str, str], consumer_secret: str, token_secret: str
) -> str:
    pairs = sorted((_pct(k), _pct(v)) for k, v in params.items())
    param_string = "&".join("{}={}".format(k, v) for k, v in pairs)
    base_string = "&".join([method.upper(), _pct(url), _pct(param_string)])
    key = "{}&{}".format(_pct(consumer_secret), _pct(token_secret))
    digest = hmac.new(key.encode(), base_string.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def _tumblr_request(
    env: Dict[str, str], method: str, path: str, params: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    base = (get(env, "TUMBLR_API_BASE", default=TUMBLR_DEFAULT_BASE)).rstrip("/")
    url = join_url(base, path)
    consumer_key = need(env, "TUMBLR_CONSUMER_KEY")
    consumer_secret = need(env, "TUMBLR_CONSUMER_SECRET")
    token = need(env, "TUMBLR_OAUTH_TOKEN")
    token_secret = need(env, "TUMBLR_OAUTH_TOKEN_SECRET")
    body_params = {k: str(v) for k, v in (params or {}).items()}
    oauth = {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": str(random.getrandbits(64)),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_version": "1.0",
        "oauth_token": token,
    }
    signature = _oauth1_signature(
        method, url, {**oauth, **body_params}, consumer_secret, token_secret
    )
    header = "OAuth " + ", ".join(
        ['{}="{}"'.format(_pct(k), _pct(v)) for k, v in {**oauth, "oauth_signature": signature}.items()]
    )
    if method.upper() == "GET":
        if body_params:
            url += "?" + urllib.parse.urlencode(body_params)
        status, body = request("GET", url, headers={"Authorization": header})
    else:
        status, body = request(
            "POST", url, headers={"Authorization": header}, form_body=body_params
        )
    try:
        data = json.loads(body) if body else {}
    except ValueError:
        raise AdapterError("Tumblr вернул не JSON: {}".format(body[:120]))
    meta = data.get("meta") or {}
    if meta.get("status") not in (200, 201):
        raise AdapterError("Tumblr API: {}".format(data.get("errors") or str(data)[:160]))
    return data.get("response") or {}


def verify_tumblr(env: Dict[str, str]) -> Dict[str, Any]:
    info = _tumblr_request(env, "GET", "/v2/user/info")
    user = info.get("user") or {}
    return {
        "ok": True,
        "account": "tumblr:{}".format(user.get("name") or ""),
        "channels": [get(env, "TUMBLR_BLOG") or "vlad-007"],
    }


def post_tumblr(env: Dict[str, str], title: str, text: str) -> PublishResult:
    blog = need(env, "TUMBLR_BLOG").strip().lstrip("@")
    body_html = "<p>{}</p>".format(
        html_lib.escape(text).replace("\n", "<br/>")
    )
    response = _tumblr_request(
        env,
        "POST",
        "/v2/blog/{}/post".format(blog),
        {"type": "text", "title": title, "body": body_html, "format": "html"},
    )
    post_id = response.get("id") or response.get("id_string") or ""
    url = "https://{}.tumblr.com/post/{}".format(blog, post_id) if post_id else ""
    return PublishResult("tumblr", True, url)


# ---------------------------------------------------------------------------
# Bluesky / AT Protocol
# ---------------------------------------------------------------------------
BSKY_DEFAULT_BASE = "https://bsky.social"


def _bsky_base(env: Dict[str, str]) -> str:
    return (get(env, "BLUESKY_BASE_URL", default=BSKY_DEFAULT_BASE)).rstrip("/")


def _bsky_session(env: Dict[str, str]) -> Dict[str, Any]:
    handle = need(env, "BLUESKY_HANDLE")
    password = need(env, "BLUESKY_APP_PASSWORD")
    data = request_json(
        "POST",
        join_url(_bsky_base(env), "/xrpc/com.atproto.server.createSession"),
        json_body={"identifier": handle, "password": password},
    )
    if not data.get("accessJwt"):
        raise AdapterError("Bluesky: нет accessJwt в ответе")
    return data


def verify_bluesky(env: Dict[str, str]) -> Dict[str, Any]:
    session = _bsky_session(env)
    return {"ok": True, "account": "@{}".format(session.get("handle"))}


def _bluesky_facets(text: str) -> List[Dict[str, Any]]:
    facets = []
    for match in URL_RE.finditer(text):
        url = match.group(0).rstrip(".,)")
        start = len(text[: match.start()].encode("utf-8"))
        end = start + len(url.encode("utf-8"))
        facets.append(
            {
                "index": {"byteStart": start, "byteEnd": end},
                "features": [
                    {"$type": "app.bsky.richtext.facet#link", "uri": url}
                ],
            }
        )
    return facets


def post_bluesky(env: Dict[str, str], text: str) -> PublishResult:
    session = _bsky_session(env)
    record: Dict[str, Any] = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
    }
    facets = _bluesky_facets(text)
    if facets:
        record["facets"] = facets
    data = request_json(
        "POST",
        join_url(_bsky_base(env), "/xrpc/com.atproto.repo.createRecord"),
        headers={"Authorization": "Bearer " + session["accessJwt"]},
        json_body={
            "repo": session.get("did"),
            "collection": "app.bsky.feed.post",
            "record": record,
        },
    )
    uri = data.get("uri") or ""
    rkey = uri.rsplit("/", 1)[-1] if uri else ""
    url = (
        "https://bsky.app/profile/{}/post/{}".format(session.get("handle"), rkey)
        if rkey
        else ""
    )
    return PublishResult("bluesky", True, url)


# ---------------------------------------------------------------------------
# Mastodon-compatible networks: Mastodon, Akkoma, Pixelfed
# ---------------------------------------------------------------------------
FEDIVERSE_NETWORKS: Dict[str, Tuple[str, str]] = {
    "mastodon": ("MASTODON_BASE_URL", "MASTODON_TOKEN"),
    "akkoma": ("AKKOMA_BASE_URL", "AKKOMA_TOKEN"),
    "pixelfed": ("PIXELFED_BASE_URL", "PIXELFED_TOKEN"),
}


def _fediverse(env: Dict[str, str], network: str, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Any:
    if network not in FEDIVERSE_NETWORKS:
        raise AdapterError("Неизвестная fediverse-сеть: {}".format(network))
    base_key, token_key = FEDIVERSE_NETWORKS[network]
    base = need(env, base_key).rstrip("/")
    token = need(env, token_key)
    status, text = request(
        method,
        join_url(base, path),
        headers={"Authorization": "Bearer " + token},
        json_body=body,
    )
    try:
        data = json.loads(text) if text else {}
    except ValueError:
        raise AdapterError("{}: не-JSON ответ: {}".format(network, text[:120]))
    if status >= 400:
        raise AdapterError("{}: {}".format(network, str(data)[:160]))
    return data


def verify_fediverse(env: Dict[str, str], network: str) -> Dict[str, Any]:
    account = _fediverse(env, network, "GET", "/api/v1/accounts/verify_credentials")
    return {
        "ok": True,
        "account": "@{}".format(account.get("username") or account.get("acct")),
    }


def post_fediverse(env: Dict[str, str], network: str, text: str) -> PublishResult:
    data = _fediverse(env, network, "POST", "/api/v1/statuses", {"status": text})
    return PublishResult(network, True, data.get("url") or data.get("uri") or "")


# ---------------------------------------------------------------------------
# Discord webhook (free, no bot needed)
# ---------------------------------------------------------------------------
def verify_discord(env: Dict[str, str]) -> Dict[str, Any]:
    webhook = need(env, "DISCORD_WEBHOOK_URL")
    data = request_json("GET", webhook)
    return {
        "ok": True,
        "account": "discord:{}".format(data.get("name") or data.get("channel_id") or "webhook"),
    }


def post_discord(env: Dict[str, str], text: str) -> PublishResult:
    webhook = need(env, "DISCORD_WEBHOOK_URL")
    request("POST", webhook, json_body={"content": text, "allowed_mentions": {"parse": []}})
    return PublishResult("discord", True)


# ---------------------------------------------------------------------------
# Telegraph (telegra.ph) — free no-auth page hosting for long posts
# ---------------------------------------------------------------------------
TELEGRAPH_DEFAULT_BASE = "https://api.telegra.ph"


def _telegraph_base(env: Dict[str, str]) -> str:
    return (get(env, "TELEGRAPH_API_BASE", default=TELEGRAPH_DEFAULT_BASE)).rstrip("/")


def _telegraph_token(env: Dict[str, str]) -> str:
    token = get(env, "TELEGRAPH_TOKEN")
    if token:
        return token
    data = request_json(
        "POST",
        join_url(_telegraph_base(env), "/createAccount"),
        form_body={"short_name": "affiliate-fanout", "author_name": "Affiliate Fanout"},
    )
    if not data.get("ok"):
        raise AdapterError("Telegraph createAccount: {}".format(str(data)[:160]))
    return (data.get("result") or {}).get("access_token") or ""


def verify_telegraph(env: Dict[str, str]) -> Dict[str, Any]:
    return {"ok": True, "account": "telegra.ph (без авторизации)"}


def text_to_telegraph_html(text: str) -> str:
    parts: List[str] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        escaped = html_lib.escape(line)
        for url in URL_RE.findall(line):
            safe = html_lib.escape(url)
            escaped = escaped.replace(
                safe, '<a href="{}">{}</a>'.format(safe, safe), 1
            )
        parts.append("<p>{}</p>".format(escaped))
    return "".join(parts) or "<p></p>"


def post_telegraph(env: Dict[str, str], title: str, text: str) -> PublishResult:
    token = _telegraph_token(env)
    if not token:
        raise AdapterError("Telegraph: не удалось получить access_token")
    data = request_json(
        "POST",
        join_url(_telegraph_base(env), "/createPage"),
        form_body={
            "access_token": token,
            "title": title or "Affiliate deals",
            "author_name": "Affiliate Fanout",
            "content": json.dumps([{"tag": "p", "children": [text_to_telegraph_html(text)]}]),
            "return_content": "false",
        },
    )
    if not data.get("ok"):
        raise AdapterError("Telegraph createPage: {}".format(str(data)[:160]))
    return PublishResult("telegraph", True, (data.get("result") or {}).get("url") or "")


# ---------------------------------------------------------------------------
# VK API (сообщество) — RU-native, бесплатно
# ---------------------------------------------------------------------------
VK_DEFAULT_BASE = "https://api.vk.com"


def _vk_call(env: Dict[str, str], method: str, params: Dict[str, Any]) -> Any:
    token = need(env, "VK_ACCESS_TOKEN")
    base = (get(env, "VK_API_BASE", default=VK_DEFAULT_BASE)).rstrip("/")
    payload = dict(params)
    payload.update({"access_token": token, "v": get(env, "VK_API_VERSION", default="5.199")})
    status, body = request("POST", join_url(base, "/method/" + method), form_body=payload)
    try:
        data = json.loads(body) if body else {}
    except ValueError:
        raise AdapterError("VK: не-JSON ответ: {}".format(body[:120]))
    if "error" in data:
        error = data.get("error") or {}
        raise AdapterError("VK: {}".format(error.get("error_msg") or str(data)[:160]))
    return data.get("response")


def verify_vk(env: Dict[str, str]) -> Dict[str, Any]:
    group_id = need(env, "VK_GROUP_ID")
    response = _vk_call(env, "groups.getById", {"group_id": group_id})
    groups = response.get("groups") if isinstance(response, dict) else response
    first = groups[0] if isinstance(groups, list) and groups else {}
    return {"ok": True, "account": "vk:{}".format(first.get("name") or group_id)}


def post_vk(env: Dict[str, str], text: str) -> PublishResult:
    group_id = need(env, "VK_GROUP_ID").lstrip("-")
    response = _vk_call(
        env,
        "wall.post",
        {"owner_id": "-" + group_id, "from_group": "1", "message": text},
    )
    post_id = (response or {}).get("post_id")
    url = "https://vk.com/wall-{}_{}".format(group_id, post_id) if post_id else ""
    return PublishResult("vk", True, url)


# ---------------------------------------------------------------------------
# dev.to (Forem) — статьи с canonical_url
# ---------------------------------------------------------------------------
DEVTO_DEFAULT_BASE = "https://dev.to"


def _devto_base(env: Dict[str, str]) -> str:
    return (get(env, "DEVTO_API_BASE", default=DEVTO_DEFAULT_BASE)).rstrip("/")


def verify_devto(env: Dict[str, str]) -> Dict[str, Any]:
    key = need(env, "DEVTO_API_KEY")
    data = request_json(
        "GET", join_url(_devto_base(env), "/api/users/me"), headers={"api-key": key}
    )
    return {"ok": True, "account": "dev.to:{}".format(data.get("username") or "")}


def post_devto(env: Dict[str, str], title: str, text: str) -> PublishResult:
    key = need(env, "DEVTO_API_KEY")
    data = request_json(
        "POST",
        join_url(_devto_base(env), "/api/articles"),
        headers={"api-key": key},
        json_body={
            "article": {
                "title": title or "Affiliate deal",
                "body_markdown": text,
                "published": True,
                "tags": ["travel", "deals"],
            }
        },
    )
    return PublishResult("devto", True, data.get("url") or "")


# ---------------------------------------------------------------------------
# Raindrop.io — публичная коллекция как link-hub
# ---------------------------------------------------------------------------
RAINDROP_DEFAULT_BASE = "https://api.raindrop.io"


def _raindrop_base(env: Dict[str, str]) -> str:
    return (get(env, "RAINDROP_API_BASE", default=RAINDROP_DEFAULT_BASE)).rstrip("/")


def verify_raindrop(env: Dict[str, str]) -> Dict[str, Any]:
    token = need(env, "RAINDROP_TOKEN")
    data = request_json(
        "GET",
        join_url(_raindrop_base(env), "/rest/v1/user"),
        headers={"Authorization": "Bearer " + token},
    )
    user = data.get("user") or {}
    return {"ok": True, "account": "raindrop:{}".format(user.get("fullName") or user.get("email") or "user")}


def post_raindrop(env: Dict[str, str], title: str, url: str, text: str) -> PublishResult:
    token = need(env, "RAINDROP_TOKEN")
    body: Dict[str, Any] = {"link": url, "title": title or "Affiliate deal", "excerpt": text[:500]}
    collection = get(env, "RAINDROP_COLLECTION_ID")
    if collection:
        body["collection"] = {"$id": int(collection) if collection.isdigit() else collection}
    data = request_json(
        "POST",
        join_url(_raindrop_base(env), "/rest/v1/raindrop"),
        headers={"Authorization": "Bearer " + token},
        json_body=body,
    )
    item = data.get("item") or {}
    return PublishResult("raindrop", True, item.get("link") or "")


# ---------------------------------------------------------------------------
# Slack webhook (сообщество/воркспейс)
# ---------------------------------------------------------------------------
def verify_slack(env: Dict[str, str]) -> Dict[str, Any]:
    need(env, "SLACK_WEBHOOK_URL")
    return {"ok": True, "account": "slack webhook"}


def post_slack(env: Dict[str, str], text: str) -> PublishResult:
    webhook = need(env, "SLACK_WEBHOOK_URL")
    request("POST", webhook, json_body={"text": text})
    return PublishResult("slack", True)
