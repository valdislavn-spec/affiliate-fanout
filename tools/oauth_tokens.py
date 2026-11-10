#!/usr/bin/env python3
"""OAuth 2.0 helper for affiliate-fanout app review and token issuance.

Supported providers: ``meta`` (Facebook/Instagram/Threads), ``pinterest``,
``linkedin``, ``x`` (OAuth2 PKCE). Stdlib only.

Typical flow (manual copy, works with the hosted callback page):

1. Build the authorization URL and open it in a browser::

       python3 tools/oauth_tokens.py --provider pinterest \
         --client-id YOUR_ID --client-secret YOUR_SECRET --url

2. After consent the browser shows the callback page with ``code``.
   Exchange it::

       python3 tools/oauth_tokens.py --provider pinterest \
         --client-id YOUR_ID --client-secret YOUR_SECRET \
         --exchange "<code>"

The script prints the ``.env`` lines to copy. Tokens are never stored by the
script and never sent anywhere except the provider token endpoint.

For X OAuth2 the authorization URL includes PKCE; pass the same
``--code-verifier`` (printed by ``--url``) to ``--exchange``.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_REDIRECT = "https://valdislavn-spec.github.io/travel-finds/oauth-callback.html"

PROVIDERS: Dict[str, Dict[str, Any]] = {
    "meta": {
        "auth": "https://www.facebook.com/v21.0/dialog/oauth",
        "token": "https://graph.facebook.com/v21.0/oauth/access_token",
        "scopes": "pages_show_list,pages_read_engagement,pages_manage_posts,"
                  "instagram_basic,instagram_content_publish,threads_basic,threads_content_publish",
        "basic_auth": False,
        "pkce": False,
    },
    "pinterest": {
        "auth": "https://www.pinterest.com/oauth/",
        "token": "https://api.pinterest.com/v5/oauth/token",
        "scopes": "pins:read,pins:write,boards:read",
        "basic_auth": True,
        "pkce": False,
    },
    "linkedin": {
        "auth": "https://www.linkedin.com/oauth/v2/authorization",
        "token": "https://www.linkedin.com/oauth/v2/accessToken",
        "scopes": "openid profile w_member_social",
        "basic_auth": False,
        "pkce": False,
    },
    "x": {
        "auth": "https://x.com/i/oauth2/authorize",
        "token": "https://api.x.com/2/oauth2/token",
        "scopes": "tweet.read tweet.write users.read offline.access",
        "basic_auth": True,
        "pkce": True,
    },
}


def build_auth_url(
    provider: str,
    client_id: str,
    redirect_uri: str = DEFAULT_REDIRECT,
    scopes: Optional[str] = None,
    state: Optional[str] = None,
    code_challenge: Optional[str] = None,
) -> Tuple[str, str]:
    """Return ``(auth_url, state)`` for the provider."""
    config = PROVIDERS[provider]
    state = state or secrets.token_urlsafe(16)
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "state": state,
        "scope": scopes or config["scopes"],
    }
    if config["pkce"]:
        if not code_challenge:
            raise ValueError("provider x requires code_challenge")
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = "S256"
    return config["auth"] + "?" + urllib.parse.urlencode(params), state


def make_pkce() -> Tuple[str, str]:
    """Return ``(code_verifier, code_challenge)`` for PKCE S256."""
    verifier = secrets.token_urlsafe(64)[:96]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def extract_code(value: str) -> str:
    """Extract ``code`` from a callback URL or return the raw value."""
    value = (value or "").strip()
    if value.startswith("http://") or value.startswith("https://"):
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(value).query)
        return (query.get("code") or [""])[0]
    return value


def env_lines(provider: str, tokens: Dict[str, Any]) -> List[str]:
    access = tokens.get("access_token") or ""
    refresh = tokens.get("refresh_token") or ""
    lines = ["# {} — вставьте в .env".format(provider)]
    if provider == "pinterest":
        lines.append("PINTEREST_ACCESS_TOKEN={}".format(access))
        if refresh:
            lines.append("PINTEREST_REFRESH_TOKEN={}".format(refresh))
    elif provider == "linkedin":
        lines.append("LINKEDIN_ACCESS_TOKEN={}".format(access))
    elif provider == "x":
        lines.append("X_OAUTH2_ACCESS_TOKEN={}".format(access))
        if refresh:
            lines.append("X_REFRESH_TOKEN={}".format(refresh))
    elif provider == "meta":
        lines.append("FACEBOOK_PAGE_TOKEN={}".format(access))
        lines.append("INSTAGRAM_ACCESS_TOKEN={}".format(access))
        lines.append("THREADS_ACCESS_TOKEN={}".format(access))
    return lines


def _post(url: str, data: Dict[str, str], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    body = urllib.parse.urlencode(data).encode()
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            **(headers or {}),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise SystemExit("Token endpoint HTTP {}: {}".format(exc.code, detail[:400]))


def _get(url: str) -> Dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise SystemExit("Graph API HTTP {}: {}".format(exc.code, detail[:400]))


def exchange(
    provider: str,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str = DEFAULT_REDIRECT,
    code_verifier: str = "",
) -> Dict[str, Any]:
    config = PROVIDERS[provider]
    headers: Dict[str, str] = {}
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }
    if config["basic_auth"]:
        headers["Authorization"] = "Basic " + base64.b64encode(
            "{}:{}".format(client_id, client_secret).encode()
        ).decode()
        data["client_id"] = client_id
    else:
        data["client_id"] = client_id
        data["client_secret"] = client_secret
    if config["pkce"]:
        if not code_verifier:
            raise SystemExit("Для X нужен --code-verifier, который вывел --url.")
        data["code_verifier"] = code_verifier
    tokens = _post(config["token"], data, headers)

    if provider == "meta":
        short = tokens.get("access_token", "")
        if short:
            long_resp = _get(
                "https://graph.facebook.com/v21.0/oauth/access_token?"
                + urllib.parse.urlencode(
                    {
                        "grant_type": "fb_exchange_token",
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "fb_exchange_token": short,
                    }
                )
            )
            long_token = long_resp.get("access_token") or short
            tokens["access_token"] = long_token
            accounts = _get(
                "https://graph.facebook.com/v21.0/me/accounts?"
                + urllib.parse.urlencode(
                    {
                        "fields": "id,name,access_token,instagram_business_account{id,username}",
                        "access_token": long_token,
                    }
                )
            )
            pages = accounts.get("data") or []
            print("\n# Страницы и аккаунты:")
            for page in pages:
                ig = page.get("instagram_business_account") or {}
                print(
                    "  page_id={} | page_token={} | ig_id={} | ig_username={}".format(
                        page.get("id"),
                        (page.get("access_token") or "")[:12] + "…",
                        ig.get("id") or "",
                        ig.get("username") or "",
                    )
                )
            if pages:
                first = pages[0]
                tokens["page_id"] = first.get("id")
                tokens["page_token"] = first.get("access_token")
                ig = first.get("instagram_business_account") or {}
                tokens["instagram_user_id"] = ig.get("id")
            threads = _get(
                "https://graph.threads.net/v1.0/me?"
                + urllib.parse.urlencode({"fields": "id,username", "access_token": long_token})
            )
            if threads.get("id"):
                tokens["threads_user_id"] = threads.get("id")
                print("  threads_user_id={} @{}".format(threads.get("id"), threads.get("username")))
    return tokens


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="OAuth helper for affiliate-fanout")
    parser.add_argument("--provider", required=True, choices=sorted(PROVIDERS))
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--client-secret", default="")
    parser.add_argument("--redirect-uri", default=DEFAULT_REDIRECT)
    parser.add_argument("--scopes", default="")
    parser.add_argument("--url", action="store_true", help="вывести authorization URL (+PKCE)")
    parser.add_argument("--exchange", default="", help="code или полный callback URL")
    parser.add_argument("--code-verifier", default="", help="PKCE verifier (для X)")
    parser.add_argument("--refresh", default="", help="refresh_token для обновления")
    args = parser.parse_args(argv)

    if args.url:
        if PROVIDERS[args.provider]["pkce"]:
            verifier, challenge = make_pkce()
            url, state = build_auth_url(
                args.provider, args.client_id, args.redirect_uri, args.scopes or None,
                code_challenge=challenge,
            )
            print("URL:", url)
            print("STATE:", state)
            print("CODE_VERIFIER:", verifier)
        else:
            url, state = build_auth_url(
                args.provider, args.client_id, args.redirect_uri, args.scopes or None
            )
            print("URL:", url)
            print("STATE:", state)
        return 0

    if args.exchange:
        code = extract_code(args.exchange)
        if not code:
            print("Не найден code в аргументе.", file=sys.stderr)
            return 2
        if not args.client_secret:
            print("Нужен --client-secret.", file=sys.stderr)
            return 2
        tokens = exchange(
            args.provider, args.client_id, args.client_secret, code,
            args.redirect_uri, args.code_verifier,
        )
        print("\n".join(env_lines(args.provider, tokens)))
        if tokens.get("page_id"):
            print("FACEBOOK_PAGE_ID={}".format(tokens["page_id"]))
        if tokens.get("instagram_user_id"):
            print("INSTAGRAM_USER_ID={}".format(tokens["instagram_user_id"]))
        if tokens.get("threads_user_id"):
            print("THREADS_USER_ID={}".format(tokens["threads_user_id"]))
        if not tokens.get("access_token"):
            print("Ответ без access_token: {}".format(str(tokens)[:300]), file=sys.stderr)
            return 1
        return 0

    print("Укажите --url или --exchange '<code>'.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
