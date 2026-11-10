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


# ===========================================================================
# Global (non-RU) free APIs: X, Reddit, Pinterest, Meta, LinkedIn, Medium,
# Blogger, WordPress. Mostly require an app + user token / OAuth review.
# ===========================================================================

def _basic_auth(username: str, password: str) -> str:
    return "Basic " + base64.b64encode("{}:{}".format(username, password).encode()).decode()


# ---------------------------------------------------------------------------
# X (Twitter) API v2 — OAuth 1.0a user context (free tier: 500 posts/month)
# ---------------------------------------------------------------------------
X_DEFAULT_BASE = "https://api.x.com"


def _x_base(env: Dict[str, str]) -> str:
    return (get(env, "X_API_BASE", default=X_DEFAULT_BASE)).rstrip("/")


def _x_auth_header(method: str, url: str, env: Dict[str, str]) -> str:
    oauth = {
        "oauth_consumer_key": need(env, "X_API_KEY"),
        "oauth_nonce": str(random.getrandbits(64)),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_version": "1.0",
        "oauth_token": need(env, "X_ACCESS_TOKEN"),
    }
    signature = _oauth1_signature(
        method, url, oauth, need(env, "X_API_SECRET"), need(env, "X_ACCESS_SECRET")
    )
    return "OAuth " + ", ".join(
        ['{}="{}"'.format(_pct(k), _pct(v)) for k, v in {**oauth, "oauth_signature": signature}.items()]
    )


def verify_x(env: Dict[str, str]) -> Dict[str, Any]:
    url = join_url(_x_base(env), "/2/users/me")
    status, body = request("GET", url, headers={"Authorization": _x_auth_header("GET", url, env)})
    data = json.loads(body) if body else {}
    user = data.get("data") or {}
    if status >= 400 or "errors" in data:
        raise AdapterError("X API: {}".format(str(data)[:160]))
    return {"ok": True, "account": "@{}".format(user.get("username") or "x")}


def post_x(env: Dict[str, str], text: str) -> PublishResult:
    url = join_url(_x_base(env), "/2/tweets")
    status, body = request(
        "POST",
        url,
        headers={"Authorization": _x_auth_header("POST", url, env)},
        json_body={"text": text},
    )
    data = json.loads(body) if body else {}
    if status >= 400 or "errors" in data:
        raise AdapterError("X API: {}".format(str(data)[:160]))
    tweet_id = (data.get("data") or {}).get("id") or ""
    return PublishResult("x", True, "https://x.com/i/web/status/{}".format(tweet_id) if tweet_id else "")


# ---------------------------------------------------------------------------
# Reddit API — OAuth2 password (script app), free non-commercial
# ---------------------------------------------------------------------------
REDDIT_DEFAULT_BASE = "https://oauth.reddit.com"


def _reddit_token(env: Dict[str, str]) -> str:
    base = get(env, "REDDIT_AUTH_BASE", default="https://www.reddit.com").rstrip("/")
    payload = {
        "grant_type": "password",
        "username": need(env, "REDDIT_USERNAME"),
        "password": need(env, "REDDIT_PASSWORD"),
    }
    status, body = request(
        "POST",
        join_url(base, "/api/v1/access_token"),
        headers={
            "Authorization": _basic_auth(
                need(env, "REDDIT_CLIENT_ID"), need(env, "REDDIT_CLIENT_SECRET")
            ),
            "User-Agent": get(env, "REDDIT_USER_AGENT", default="affiliate-fanout/0.1"),
        },
        form_body=payload,
    )
    data = json.loads(body) if body else {}
    token = data.get("access_token")
    if not token:
        raise AdapterError("Reddit OAuth: {}".format(str(data)[:160]))
    return token


def _reddit_base(env: Dict[str, str]) -> str:
    return (get(env, "REDDIT_API_BASE", default=REDDIT_DEFAULT_BASE)).rstrip("/")


def verify_reddit(env: Dict[str, str]) -> Dict[str, Any]:
    token = _reddit_token(env)
    base = _reddit_base(env)
    status, body = request(
        "GET",
        join_url(base, "/api/v1/me"),
        headers={
            "Authorization": "Bearer " + token,
            "User-Agent": get(env, "REDDIT_USER_AGENT", default="affiliate-fanout/0.1"),
        },
    )
    data = json.loads(body) if body else {}
    if status >= 400:
        raise AdapterError("Reddit: {}".format(str(data)[:160]))
    return {"ok": True, "account": "u/{}".format(data.get("name") or "reddit")}


def post_reddit(env: Dict[str, str], title: str, url: str) -> PublishResult:
    token = _reddit_token(env)
    payload = {
        "sr": need(env, "REDDIT_SUBREDDIT"),
        "title": title or "Deal",
        "url": url,
        "kind": "link",
        "api_type": "json",
    }
    status, body = request(
        "POST",
        join_url(_reddit_base(env), "/api/submit"),
        headers={
            "Authorization": "Bearer " + token,
            "User-Agent": get(env, "REDDIT_USER_AGENT", default="affiliate-fanout/0.1"),
        },
        form_body=payload,
    )
    data = json.loads(body) if body else {}
    if status >= 400 or (data.get("json") or {}).get("errors"):
        raise AdapterError("Reddit: {}".format(str(data)[:160]))
    url_out = ((data.get("json") or {}).get("data") or {}).get("url") or ""
    return PublishResult("reddit", True, url_out)


# ---------------------------------------------------------------------------
# Pinterest API v5 — needs image URL + approved app
# ---------------------------------------------------------------------------
PINTEREST_DEFAULT_BASE = "https://api.pinterest.com"


def _pinterest_base(env: Dict[str, str]) -> str:
    return (get(env, "PINTEREST_API_BASE", default=PINTEREST_DEFAULT_BASE)).rstrip("/")


def verify_pinterest(env: Dict[str, str]) -> Dict[str, Any]:
    token = need(env, "PINTEREST_ACCESS_TOKEN")
    status, body = request(
        "GET",
        join_url(_pinterest_base(env), "/v5/user_account"),
        headers={"Authorization": "Bearer " + token},
    )
    data = json.loads(body) if body else {}
    if status >= 400:
        raise AdapterError("Pinterest: {}".format(str(data)[:160]))
    return {"ok": True, "account": "pinterest:{}".format(data.get("username") or "user")}


def post_pinterest(env: Dict[str, str], title: str, url: str, text: str) -> PublishResult:
    token = need(env, "PINTEREST_ACCESS_TOKEN")
    board = need(env, "PINTEREST_BOARD_ID")
    image = need(env, "PINTEREST_IMAGE_URL")
    status, body = request(
        "POST",
        join_url(_pinterest_base(env), "/v5/pins"),
        headers={"Authorization": "Bearer " + token},
        json_body={
            "board_id": board,
            "title": (title or "Deal")[:100],
            "description": text[:500],
            "link": url,
            "media_source": {"source_type": "image_url", "url": image},
        },
    )
    data = json.loads(body) if body else {}
    if status >= 400:
        raise AdapterError("Pinterest: {}".format(str(data)[:160]))
    return PublishResult("pinterest", True, "https://www.pinterest.com/pin/{}/".format(data.get("id") or ""))


# ---------------------------------------------------------------------------
# Meta: Facebook Page / Instagram / Threads (Graph API, app review needed)
# ---------------------------------------------------------------------------
META_DEFAULT_BASE = "https://graph.facebook.com"
THREADS_DEFAULT_BASE = "https://graph.threads.net"


def _meta_base(env: Dict[str, str]) -> str:
    return (get(env, "META_API_BASE", default=META_DEFAULT_BASE)).rstrip("/")


def _threads_base(env: Dict[str, str]) -> str:
    return (get(env, "THREADS_API_BASE", default=THREADS_DEFAULT_BASE)).rstrip("/")


def verify_facebook(env: Dict[str, str]) -> Dict[str, Any]:
    page_id = need(env, "FACEBOOK_PAGE_ID")
    token = need(env, "FACEBOOK_PAGE_TOKEN")
    status, body = request(
        "GET", join_url(_meta_base(env), "/{}?fields=name&access_token={}".format(page_id, token))
    )
    data = json.loads(body) if body else {}
    if status >= 400:
        raise AdapterError("Facebook: {}".format(str(data)[:160]))
    return {"ok": True, "account": "facebook:{}".format(data.get("name") or page_id)}


def post_facebook(env: Dict[str, str], text: str, url: str) -> PublishResult:
    page_id = need(env, "FACEBOOK_PAGE_ID")
    token = need(env, "FACEBOOK_PAGE_TOKEN")
    status, body = request(
        "POST",
        join_url(_meta_base(env), "/{}/feed".format(page_id)),
        form_body={"message": text, "link": url, "access_token": token},
    )
    data = json.loads(body) if body else {}
    if status >= 400:
        raise AdapterError("Facebook: {}".format(str(data)[:160]))
    post_id = data.get("id") or ""
    return PublishResult("facebook", True, "https://www.facebook.com/{}".format(post_id) if post_id else "")


def verify_instagram(env: Dict[str, str]) -> Dict[str, Any]:
    user_id = need(env, "INSTAGRAM_USER_ID")
    token = need(env, "INSTAGRAM_ACCESS_TOKEN")
    status, body = request(
        "GET", join_url(_meta_base(env), "/{}?fields=username&access_token={}".format(user_id, token))
    )
    data = json.loads(body) if body else {}
    if status >= 400:
        raise AdapterError("Instagram: {}".format(str(data)[:160]))
    return {"ok": True, "account": "instagram:{}".format(data.get("username") or user_id)}


def post_instagram(env: Dict[str, str], text: str) -> PublishResult:
    user_id = need(env, "INSTAGRAM_USER_ID")
    token = need(env, "INSTAGRAM_ACCESS_TOKEN")
    image = need(env, "INSTAGRAM_IMAGE_URL")
    status, body = request(
        "POST",
        join_url(_meta_base(env), "/{}/media".format(user_id)),
        form_body={"image_url": image, "caption": text, "access_token": token},
    )
    creation = json.loads(body) if body else {}
    if status >= 400 or not creation.get("id"):
        raise AdapterError("Instagram media: {}".format(str(creation)[:160]))
    status, body = request(
        "POST",
        join_url(_meta_base(env), "/{}/media_publish".format(user_id)),
        form_body={"creation_id": creation["id"], "access_token": token},
    )
    data = json.loads(body) if body else {}
    if status >= 400:
        raise AdapterError("Instagram publish: {}".format(str(data)[:160]))
    return PublishResult("instagram", True)


def verify_threads(env: Dict[str, str]) -> Dict[str, Any]:
    token = need(env, "THREADS_ACCESS_TOKEN")
    status, body = request(
        "GET", join_url(_threads_base(env), "/v1.0/me?fields=id,username&access_token={}".format(token))
    )
    data = json.loads(body) if body else {}
    if status >= 400:
        raise AdapterError("Threads: {}".format(str(data)[:160]))
    return {"ok": True, "account": "threads:{}".format(data.get("username") or "user")}


def post_threads(env: Dict[str, str], text: str) -> PublishResult:
    user_id = need(env, "THREADS_USER_ID")
    token = need(env, "THREADS_ACCESS_TOKEN")
    status, body = request(
        "POST",
        join_url(_threads_base(env), "/v1.0/{}/threads".format(user_id)),
        form_body={"media_type": "TEXT", "text": text, "access_token": token},
    )
    creation = json.loads(body) if body else {}
    if status >= 400 or not creation.get("id"):
        raise AdapterError("Threads create: {}".format(str(creation)[:160]))
    status, body = request(
        "POST",
        join_url(_threads_base(env), "/v1.0/{}/threads_publish".format(user_id)),
        form_body={"creation_id": creation["id"], "access_token": token},
    )
    data = json.loads(body) if body else {}
    if status >= 400:
        raise AdapterError("Threads publish: {}".format(str(data)[:160]))
    return PublishResult("threads", True)


# ---------------------------------------------------------------------------
# LinkedIn REST Posts API (app review; w_member_social)
# ---------------------------------------------------------------------------
LINKEDIN_DEFAULT_BASE = "https://api.linkedin.com"


def _linkedin_base(env: Dict[str, str]) -> str:
    return (get(env, "LINKEDIN_API_BASE", default=LINKEDIN_DEFAULT_BASE)).rstrip("/")


def _linkedin_headers(env: Dict[str, str]) -> Dict[str, str]:
    return {
        "Authorization": "Bearer " + need(env, "LINKEDIN_ACCESS_TOKEN"),
        "LinkedIn-Version": get(env, "LINKEDIN_VERSION", default="2025-01"),
        "X-Restli-Protocol-Version": "2.0.0",
    }


def verify_linkedin(env: Dict[str, str]) -> Dict[str, Any]:
    token = need(env, "LINKEDIN_ACCESS_TOKEN")
    status, body = request(
        "GET", join_url(_linkedin_base(env), "/v2/userinfo"),
        headers={"Authorization": "Bearer " + token},
    )
    data = json.loads(body) if body else {}
    if status >= 400:
        raise AdapterError("LinkedIn: {}".format(str(data)[:160]))
    return {"ok": True, "account": "linkedin:{}".format(data.get("name") or data.get("sub") or "me")}


def post_linkedin(env: Dict[str, str], text: str) -> PublishResult:
    author = need(env, "LINKEDIN_AUTHOR_URN")
    status, body = request(
        "POST",
        join_url(_linkedin_base(env), "/rest/posts"),
        headers=_linkedin_headers(env),
        json_body={
            "author": author,
            "commentary": text,
            "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED"},
            "lifecycleState": "PUBLISHED",
        },
    )
    data = json.loads(body) if body else {}
    if status >= 400:
        raise AdapterError("LinkedIn: {}".format(str(data)[:160]))
    return PublishResult("linkedin", True, "")


# ---------------------------------------------------------------------------
# Medium (legacy Integration API: новые токены не выдают, старые работают)
# ---------------------------------------------------------------------------
MEDIUM_DEFAULT_BASE = "https://api.medium.com"


def _medium_base(env: Dict[str, str]) -> str:
    return (get(env, "MEDIUM_API_BASE", default=MEDIUM_DEFAULT_BASE)).rstrip("/")


def verify_medium(env: Dict[str, str]) -> Dict[str, Any]:
    token = need(env, "MEDIUM_TOKEN")
    status, body = request(
        "GET", join_url(_medium_base(env), "/v1/me"),
        headers={"Authorization": "Bearer " + token},
    )
    data = json.loads(body) if body else {}
    if status >= 400:
        raise AdapterError("Medium: {}".format(str(data)[:160]))
    return {"ok": True, "account": "medium:{}".format((data.get("data") or {}).get("username") or "me")}


def post_medium(env: Dict[str, str], title: str, text: str) -> PublishResult:
    token = need(env, "MEDIUM_TOKEN")
    author_id = need(env, "MEDIUM_AUTHOR_ID")
    status, body = request(
        "POST",
        join_url(_medium_base(env), "/v1/users/{}/posts".format(author_id)),
        headers={"Authorization": "Bearer " + token},
        json_body={
            "title": title or "Affiliate deal",
            "contentFormat": "markdown",
            "content": text,
            "publishStatus": "public",
        },
    )
    data = json.loads(body) if body else {}
    if status >= 400:
        raise AdapterError("Medium: {}".format(str(data)[:160]))
    return PublishResult("medium", True, (data.get("data") or {}).get("url") or "")


# ---------------------------------------------------------------------------
# Blogger API v3 (Google OAuth2 refresh token)
# ---------------------------------------------------------------------------
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
BLOGGER_DEFAULT_BASE = "https://www.googleapis.com/blogger/v3"


def _blogger_token(env: Dict[str, str]) -> str:
    status, body = request(
        "POST",
        get(env, "GOOGLE_TOKEN_URL", default=GOOGLE_TOKEN_URL),
        form_body={
            "client_id": need(env, "BLOGGER_CLIENT_ID"),
            "client_secret": need(env, "BLOGGER_CLIENT_SECRET"),
            "refresh_token": need(env, "BLOGGER_REFRESH_TOKEN"),
            "grant_type": "refresh_token",
        },
    )
    data = json.loads(body) if body else {}
    token = data.get("access_token")
    if not token:
        raise AdapterError("Blogger OAuth: {}".format(str(data)[:160]))
    return token


def verify_blogger(env: Dict[str, str]) -> Dict[str, Any]:
    token = _blogger_token(env)
    blog_id = need(env, "BLOGGER_BLOG_ID")
    base = (get(env, "BLOGGER_API_BASE", default=BLOGGER_DEFAULT_BASE)).rstrip("/")
    status, body = request(
        "GET", join_url(base, "/blogs/{}".format(blog_id)),
        headers={"Authorization": "Bearer " + token},
    )
    data = json.loads(body) if body else {}
    if status >= 400:
        raise AdapterError("Blogger: {}".format(str(data)[:160]))
    return {"ok": True, "account": "blogger:{}".format(data.get("name") or blog_id)}


def post_blogger(env: Dict[str, str], title: str, text: str) -> PublishResult:
    token = _blogger_token(env)
    blog_id = need(env, "BLOGGER_BLOG_ID")
    base = (get(env, "BLOGGER_API_BASE", default=BLOGGER_DEFAULT_BASE)).rstrip("/")
    content = "<p>{}</p>".format(html_lib.escape(text).replace("\n", "<br/>"))
    status, body = request(
        "POST",
        join_url(base, "/blogs/{}/posts/".format(blog_id)),
        headers={"Authorization": "Bearer " + token},
        json_body={"kind": "blogger#post", "title": title or "Affiliate deal", "content": content},
    )
    data = json.loads(body) if body else {}
    if status >= 400:
        raise AdapterError("Blogger: {}".format(str(data)[:160]))
    return PublishResult("blogger", True, data.get("url") or "")


# ---------------------------------------------------------------------------
# WordPress: self-hosted (Application Password) и WordPress.com (OAuth2)
# ---------------------------------------------------------------------------
def verify_wordpress(env: Dict[str, str]) -> Dict[str, Any]:
    if get(env, "WP_BASE_URL"):
        auth = _basic_auth(need(env, "WP_USERNAME"), need(env, "WP_APP_PASSWORD"))
        status, body = request(
            "GET", join_url(env["WP_BASE_URL"].rstrip("/"), "/wp-json/wp/v2/users/me"),
            headers={"Authorization": auth},
        )
        data = json.loads(body) if body else {}
        if status >= 400:
            raise AdapterError("WordPress: {}".format(str(data)[:160]))
        return {"ok": True, "account": "wordpress:{}".format(data.get("name") or "me")}
    site = need(env, "WPCOM_SITE")
    token = need(env, "WPCOM_ACCESS_TOKEN")
    status, body = request(
        "GET", "https://public-api.wordpress.com/rest/v1.1/sites/{}".format(site),
        headers={"Authorization": "Bearer " + token},
    )
    data = json.loads(body) if body else {}
    if status >= 400:
        raise AdapterError("WordPress.com: {}".format(str(data)[:160]))
    return {"ok": True, "account": "wordpress.com:{}".format(data.get("name") or site)}


def post_wordpress(env: Dict[str, str], title: str, text: str) -> PublishResult:
    content = "<p>{}</p>".format(html_lib.escape(text).replace("\n", "<br/>"))
    if get(env, "WP_BASE_URL"):
        base = env["WP_BASE_URL"].rstrip("/")
        auth = _basic_auth(need(env, "WP_USERNAME"), need(env, "WP_APP_PASSWORD"))
        status, body = request(
            "POST", join_url(base, "/wp-json/wp/v2/posts"),
            headers={"Authorization": auth},
            json_body={"title": title or "Affiliate deal", "content": content, "status": "publish"},
        )
        data = json.loads(body) if body else {}
        if status >= 400:
            raise AdapterError("WordPress: {}".format(str(data)[:160]))
        return PublishResult("wordpress", True, data.get("link") or "")
    site = need(env, "WPCOM_SITE")
    token = need(env, "WPCOM_ACCESS_TOKEN")
    status, body = request(
        "POST", "https://public-api.wordpress.com/rest/v1.1/sites/{}/posts/new".format(site),
        headers={"Authorization": "Bearer " + token},
        json_body={"title": title or "Affiliate deal", "content": content, "status": "publish"},
    )
    data = json.loads(body) if body else {}
    if status >= 400:
        raise AdapterError("WordPress.com: {}".format(str(data)[:160]))
    return PublishResult("wordpress", True, data.get("URL") or "")
