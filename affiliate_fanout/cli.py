"""CLI: publish an affiliate post to all configured free platforms.

Modes
-----
``--verify``   check configured credentials/accounts (no posting)
(default)      dry-run: show the plan, no network mutation
``--execute``  create partner links and publish for real

Example
-------
::

    python -m affiliate_fanout --env ../content-factory/.env --verify

    python -m affiliate_fanout \
      --env ../content-factory/.env \
      --brand-url https://www.aviasales.com/ --trs 597672 \
      --text "Deals from Moscow: {url}" \
      --platforms telegram,tumblr,bluesky,akkoma,pixelfed,telegraph \
      --telegram-all --tracker --execute
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional, Tuple

from . import adapters
from .env import ConfigError, env_keys_with_prefix, get, load_env, need
from .links import LinkTracker, TravelpayoutsLinks

PLATFORM_LIMITS: Dict[str, int] = {
    "telegram": 4096,
    "tumblr": 20000,
    "bluesky": 300,
    "mastodon": 5000,
    "akkoma": 5000,
    "pixelfed": 2200,
    "discord": 2000,
    "telegraph": 60000,
    "vk": 4096,
    "devto": 20000,
    "raindrop": 1000,
    "slack": 2000,
    "x": 280,
    "reddit": 40000,
    "pinterest": 500,
    "facebook": 63206,
    "instagram": 2200,
    "threads": 500,
    "linkedin": 3000,
    "medium": 20000,
    "blogger": 20000,
    "wordpress": 20000,
}

DEFAULT_PLATFORMS = [
    "telegram", "vk", "tumblr", "bluesky", "mastodon", "akkoma", "pixelfed",
    "devto", "telegraph", "discord", "slack", "raindrop",
    "x", "reddit", "pinterest", "facebook", "instagram", "threads",
    "linkedin", "medium", "blogger", "wordpress",
]
DEFAULT_TEXT = "Deal: {url}"
DEFAULT_DISCLOSURE = "Ad · affiliate link"

#: Market presets. ``us`` — English, US audiences; ``latam`` — neutral Spanish
#: for Latin America. Programs and channels differ; see README.
LANG_TEXTS: Dict[str, str] = {
    "en": "Travel deal: {url}",
    "es": "Oferta de viaje: {url}",
    "ru": "Тревел-предложение: {url}",
}

MARKETS: Dict[str, Dict[str, Any]] = {
    "us": {
        "lang": "en",
        "texts": {"en": "Travel deal: cheap flights, hotels and eSIM — {url}"},
        "disclosures": {"en": "Ad · affiliate link"},
        "subid_prefix": "fanout_us",
        "platforms": [
            "telegram", "x", "pinterest", "facebook", "instagram", "threads",
            "reddit", "wordpress", "blogger", "medium", "devto", "telegraph",
        ],
    },
    "latam": {
        "lang": "es",
        "texts": {"es": "Oferta de viaje: vuelos baratos, hoteles y eSIM — {url}"},
        "disclosures": {"es": "Publicidad · enlace de afiliado"},
        "subid_prefix": "fanout_latam",
        "platforms": [
            "telegram", "instagram", "facebook", "threads", "pinterest", "x",
            "wordpress", "blogger", "telegraph", "devto",
        ],
    },
}


def resolve_market_options(
    market: str = "",
    lang: str = "",
    text: Optional[str] = None,
    disclosure: Optional[str] = None,
    subid_prefix: str = "",
) -> Dict[str, str]:
    """Resolve language/text/disclosure/sub_id defaults for a market."""
    config = MARKETS.get((market or "").strip().lower(), {})
    chosen_lang = (lang or config.get("lang") or "en").lower()
    resolved_text = (
        text
        or (config.get("texts") or {}).get(chosen_lang)
        or LANG_TEXTS.get(chosen_lang, DEFAULT_TEXT.format(url="{url}"))
    )
    resolved_disclosure = disclosure
    if resolved_disclosure is None:
        resolved_disclosure = (config.get("disclosures") or {}).get(
            chosen_lang, DEFAULT_DISCLOSURE
        )
    resolved_prefix = subid_prefix or config.get("subid_prefix") or "fanout"
    return {
        "lang": chosen_lang,
        "text": resolved_text,
        "disclosure": resolved_disclosure,
        "subid_prefix": resolved_prefix,
    }


def compose_text(template: str, url: str, disclosure: str, limit: int) -> str:
    """Render ``template`` with ``url``, keep URL/disclosure inside ``limit``."""
    template = template or DEFAULT_TEXT
    if "{url}" in template:
        rendered = template.replace("{url}", url)
    else:
        rendered = template.rstrip() + "\n" + url
    if disclosure:
        rendered = rendered.rstrip() + "\n\n" + disclosure
    if len(rendered) <= limit:
        return rendered
    url_block = "\n" + url
    disc_block = ("\n\n" + disclosure) if disclosure else ""
    body = template.replace("{url}", "").strip() if "{url}" in template else template.strip()
    room = max(0, limit - len(url_block) - len(disc_block))
    body = body[:room].rstrip()
    return (body + url_block + disc_block)[:limit]


# ---------------------------------------------------------------------------
# platform verification
# ---------------------------------------------------------------------------
def verify_platform(env: Dict[str, str], platform: str) -> Dict[str, Any]:
    try:
        if platform == "telegram":
            if not get(env, "TELEGRAM_BOT_TOKEN"):
                return {"ok": False, "detail": "нет TELEGRAM_BOT_TOKEN"}
            return adapters.verify_telegram(env)
        if platform == "tumblr":
            if not get(env, "TUMBLR_CONSUMER_KEY", "TUMBLR_OAUTH_TOKEN"):
                return {"ok": False, "detail": "нет Tumblr OAuth-ключей"}
            return adapters.verify_tumblr(env)
        if platform == "bluesky":
            if not get(env, "BLUESKY_HANDLE"):
                return {"ok": False, "detail": "нет BLUESKY_HANDLE/APP_PASSWORD"}
            return adapters.verify_bluesky(env)
        if platform in adapters.FEDIVERSE_NETWORKS:
            base_key, token_key = adapters.FEDIVERSE_NETWORKS[platform]
            if not (get(env, base_key) and get(env, token_key)):
                return {"ok": False, "detail": "нет {} / {}".format(base_key, token_key)}
            return adapters.verify_fediverse(env, platform)
        if platform == "discord":
            if not get(env, "DISCORD_WEBHOOK_URL"):
                return {"ok": False, "detail": "нет DISCORD_WEBHOOK_URL"}
            return adapters.verify_discord(env)
        if platform == "telegraph":
            return adapters.verify_telegraph(env)
        if platform == "vk":
            if not (get(env, "VK_ACCESS_TOKEN") and get(env, "VK_GROUP_ID")):
                return {"ok": False, "detail": "нет VK_ACCESS_TOKEN / VK_GROUP_ID"}
            return adapters.verify_vk(env)
        if platform == "devto":
            if not get(env, "DEVTO_API_KEY"):
                return {"ok": False, "detail": "нет DEVTO_API_KEY"}
            return adapters.verify_devto(env)
        if platform == "raindrop":
            if not get(env, "RAINDROP_TOKEN"):
                return {"ok": False, "detail": "нет RAINDROP_TOKEN"}
            return adapters.verify_raindrop(env)
        if platform == "slack":
            if not get(env, "SLACK_WEBHOOK_URL"):
                return {"ok": False, "detail": "нет SLACK_WEBHOOK_URL"}
            return adapters.verify_slack(env)
        if platform == "x":
            if not get(env, "X_API_KEY"):
                return {"ok": False, "detail": "нет X_API_KEY/ACCESS_TOKEN (OAuth1)"}
            return adapters.verify_x(env)
        if platform == "reddit":
            if not get(env, "REDDIT_CLIENT_ID"):
                return {"ok": False, "detail": "нет REDDIT_CLIENT_ID/SECRET/USERNAME"}
            return adapters.verify_reddit(env)
        if platform == "pinterest":
            if not get(env, "PINTEREST_ACCESS_TOKEN"):
                return {"ok": False, "detail": "нет PINTEREST_ACCESS_TOKEN (нужен approved app)"}
            return adapters.verify_pinterest(env)
        if platform == "facebook":
            if not get(env, "FACEBOOK_PAGE_TOKEN"):
                return {"ok": False, "detail": "нет FACEBOOK_PAGE_ID/TOKEN"}
            return adapters.verify_facebook(env)
        if platform == "instagram":
            if not get(env, "INSTAGRAM_ACCESS_TOKEN"):
                return {"ok": False, "detail": "нет INSTAGRAM_USER_ID/TOKEN"}
            return adapters.verify_instagram(env)
        if platform == "threads":
            if not get(env, "THREADS_ACCESS_TOKEN"):
                return {"ok": False, "detail": "нет THREADS_USER_ID/TOKEN"}
            return adapters.verify_threads(env)
        if platform == "linkedin":
            if not get(env, "LINKEDIN_ACCESS_TOKEN"):
                return {"ok": False, "detail": "нет LINKEDIN_ACCESS_TOKEN/AUTHOR_URN"}
            return adapters.verify_linkedin(env)
        if platform == "medium":
            if not get(env, "MEDIUM_TOKEN"):
                return {"ok": False, "detail": "нет MEDIUM_TOKEN (legacy API)"}
            return adapters.verify_medium(env)
        if platform == "blogger":
            if not get(env, "BLOGGER_REFRESH_TOKEN"):
                return {"ok": False, "detail": "нет BLOGGER_* OAuth-ключей"}
            return adapters.verify_blogger(env)
        if platform == "wordpress":
            if not (get(env, "WP_BASE_URL") or get(env, "WPCOM_ACCESS_TOKEN")):
                return {"ok": False, "detail": "нет WP_BASE_URL (self-hosted) или WPCOM_ACCESS_TOKEN"}
            return adapters.verify_wordpress(env)
        return {"ok": False, "detail": "неизвестная платформа"}
    except (ConfigError, adapters.AdapterError) as exc:
        return {"ok": False, "detail": str(exc)}
    except Exception as exc:  # noqa: BLE001 - report any transport/API error per platform
        return {"ok": False, "detail": "{}: {}".format(type(exc).__name__, exc)}


def run_verify(env: Dict[str, str], platforms: List[str]) -> Dict[str, Any]:
    report: Dict[str, Any] = {"platforms": {}, "links": {}}
    for platform in platforms:
        report["platforms"][platform] = verify_platform(env, platform)
    tp = TravelpayoutsLinks(env)
    report["links"]["travelpayouts"] = (
        {"ok": True, "detail": "token/marker/trs заданы"}
        if tp.available
        else {"ok": False, "detail": "не хватает: {}".format(", ".join(tp.missing()))}
    )
    tracker = LinkTracker(env)
    if tracker.available:
        try:
            report["links"]["tracker"] = tracker.verify()
        except Exception as exc:  # noqa: BLE001 - report as unavailable
            report["links"]["tracker"] = {"ok": False, "detail": str(exc)}
    else:
        report["links"]["tracker"] = {"ok": False, "detail": "нет LINK_TRACKER_*"}
    return report


# ---------------------------------------------------------------------------
# publishing
# ---------------------------------------------------------------------------
def _telegram_targets(args: argparse.Namespace, env: Dict[str, str]) -> List[Tuple[str, str]]:
    targets: List[Tuple[str, str]] = []
    for chat in args.telegram_chat or []:
        targets.append((chat, "chat"))
    if args.telegram_env:
        for suffix in args.telegram_env.split(","):
            suffix = suffix.strip().upper().replace("-", "_")
            key = "TELEGRAM_CHAT_ID_" + suffix
            value = get(env, key)
            if value:
                targets.append((value, key))
    if args.telegram_all:
        for key, value in env_keys_with_prefix(env, "TELEGRAM_CHAT_ID_"):
            targets.append((value, key))
    # de-duplicate while preserving order
    seen = set()
    unique = []
    for chat, label in targets:
        if chat not in seen:
            seen.add(chat)
            unique.append((chat, label))
    return unique


def _resolve_platform_links(
    env: Dict[str, str],
    platforms: List[str],
    brand_url: Optional[str],
    direct_url: Optional[str],
    trs: Optional[str],
    subid_prefix: str,
    allow_plain: bool,
) -> Dict[str, str]:
    if direct_url and not brand_url:
        return {platform: direct_url for platform in platforms}
    if not brand_url:
        raise ConfigError("Укажите --brand-url (для Travelpayouts) или --url.")
    tp = TravelpayoutsLinks(env)
    if trs:
        env["TRAVELPAYOUTS_TRS"] = trs
        tp = TravelpayoutsLinks(env)
    if not tp.available:
        if allow_plain:
            return {platform: brand_url for platform in platforms}
        raise ConfigError(
            "Нет партнёрских настроек ({}). Добавьте TRAVELPAYOUTS_TRS "
            "или флаг --allow-plain.".format(", ".join(tp.missing()))
        )
    items = [(brand_url, "{}_{}".format(subid_prefix, platform)) for platform in platforms]
    links = tp.create(items)
    return dict(zip(platforms, links))


def _publish_one(env: Dict[str, str], platform: str, url: str, text: str, title: str, telegram_targets: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    try:
        if platform == "telegram":
            if not telegram_targets:
                return [{"platform": "telegram", "ok": False, "detail": "нет целей (--telegram-chat/--telegram-env/--telegram-all)"}]
            for chat, label in telegram_targets:
                try:
                    result = adapters.post_telegram(env, chat, text)
                    item = result.as_dict()
                    item["target"] = label
                    results.append(item)
                except (ConfigError, adapters.AdapterError) as exc:
                    results.append({"platform": "telegram", "ok": False, "target": label, "detail": str(exc)})
            return results
        if platform == "tumblr":
            results.append(adapters.post_tumblr(env, title, text).as_dict())
        elif platform == "bluesky":
            results.append(adapters.post_bluesky(env, text).as_dict())
        elif platform in adapters.FEDIVERSE_NETWORKS:
            results.append(adapters.post_fediverse(env, platform, text).as_dict())
        elif platform == "discord":
            results.append(adapters.post_discord(env, text).as_dict())
        elif platform == "telegraph":
            results.append(adapters.post_telegraph(env, title, text).as_dict())
        elif platform == "vk":
            results.append(adapters.post_vk(env, text).as_dict())
        elif platform == "devto":
            results.append(adapters.post_devto(env, title, text).as_dict())
        elif platform == "raindrop":
            results.append(adapters.post_raindrop(env, title, url, text).as_dict())
        elif platform == "slack":
            results.append(adapters.post_slack(env, text).as_dict())
        elif platform == "x":
            results.append(adapters.post_x(env, text).as_dict())
        elif platform == "reddit":
            results.append(adapters.post_reddit(env, title, url).as_dict())
        elif platform == "pinterest":
            results.append(adapters.post_pinterest(env, title, url, text).as_dict())
        elif platform == "facebook":
            results.append(adapters.post_facebook(env, text, url).as_dict())
        elif platform == "instagram":
            results.append(adapters.post_instagram(env, text).as_dict())
        elif platform == "threads":
            results.append(adapters.post_threads(env, text).as_dict())
        elif platform == "linkedin":
            results.append(adapters.post_linkedin(env, text).as_dict())
        elif platform == "medium":
            results.append(adapters.post_medium(env, title, text).as_dict())
        elif platform == "blogger":
            results.append(adapters.post_blogger(env, title, text).as_dict())
        elif platform == "wordpress":
            results.append(adapters.post_wordpress(env, title, text).as_dict())
        else:
            results.append({"platform": platform, "ok": False, "detail": "неизвестная платформа"})
    except (ConfigError, adapters.AdapterError) as exc:
        results.append({"platform": platform, "ok": False, "detail": str(exc)})
    except Exception as exc:  # noqa: BLE001 - isolate platform failures
        results.append({"platform": platform, "ok": False, "detail": "{}: {}".format(type(exc).__name__, exc)})
    return results


def run_publish(
    env: Dict[str, str],
    platforms: List[str],
    brand_url: Optional[str],
    direct_url: Optional[str],
    template: str,
    title: str,
    disclosure: str,
    trs: Optional[str],
    subid_prefix: str,
    allow_plain: bool,
    use_tracker: bool,
    telegram_targets: List[Tuple[str, str]],
    execute: bool,
    resolver: bool,
) -> Dict[str, Any]:
    report: Dict[str, Any] = {"mode": "execute" if execute else "dry-run", "platforms": []}
    links = _resolve_platform_links(
        env, platforms, brand_url, direct_url, trs, subid_prefix, allow_plain or not execute and not resolver
    ) if (resolver or execute) else {}
    tracker = LinkTracker(env)
    for platform in platforms:
        url = links.get(platform) or brand_url or direct_url or ""
        limit = PLATFORM_LIMITS.get(platform, 4096)
        text = compose_text(template, url, disclosure, limit)
        item: Dict[str, Any] = {
            "platform": platform,
            "limit": limit,
            "chars": len(text),
            "url": url,
            "text_preview": text[:180],
        }
        if execute:
            if use_tracker and tracker.available and url:
                try:
                    url = tracker.wrap(url, platform)
                    item["tracked_url"] = url
                except Exception as exc:  # noqa: BLE001 - tracker is optional
                    item["tracker_error"] = str(exc)
            text = compose_text(template, url, disclosure, limit)
            item["results"] = _publish_one(env, platform, url, text, title, telegram_targets)
        else:
            item["status"] = "planned (dry-run)" if not resolver else "links resolved (dry-run)"
        report["platforms"].append(item)
    return report


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="affiliate-fanout",
        description="Публикация партнёрской ссылки во все бесплатные соцсети через API.",
    )
    parser.add_argument("--env", default="", help="путь к .env (например, ../content-factory/.env)")
    parser.add_argument("--platforms", default="all", help="список через запятую или all")
    parser.add_argument("--brand-url", default="", help="URL бренда → партнёрская ссылка (Travelpayouts)")
    parser.add_argument("--url", default="", help="готовая ссылка (без конвертации)")
    parser.add_argument(
        "--market", choices=["us", "latam", ""], default="",
        help="рынок: us (EN, США) или latam (ES, Латинская Америка)",
    )
    parser.add_argument(
        "--lang", choices=["en", "es", "ru", ""], default="",
        help="язык текста/раскрытия (по умолчанию — из рынка)",
    )
    parser.add_argument("--text", default=None, help="шаблон поста; {url} подставится (по умолчанию — под рынок)")
    parser.add_argument("--title", default="Travel deal", help="заголовок (Tumblr/Telegraph/Medium/Blogger/WordPress)")
    parser.add_argument("--disclosure", default=None, help="пометка «реклама/партнёрская ссылка» (по умолчанию — под рынок)")
    parser.add_argument("--trs", default="", help="ID проекта Travelpayouts (trs)")
    parser.add_argument("--subid-prefix", default="", help="префикс sub_id: <prefix>_<platform> (по умолчанию — под рынок)")
    parser.add_argument("--allow-plain", action="store_true", help="разрешить постинг без партнёрских ссылок")
    parser.add_argument("--tracker", action="store_true", help="обернуть ссылки в свой click-tracker")
    parser.add_argument("--telegram-chat", action="append", help="chat_id канала (можно несколько)")
    parser.add_argument("--telegram-env", default="", help="суффиксы TELEGRAM_CHAT_ID_<X> через запятую")
    parser.add_argument("--telegram-all", action="store_true", help="все TELEGRAM_CHAT_ID_* из env")
    parser.add_argument("--verify", action="store_true", help="только проверить подключения")
    parser.add_argument("--execute", action="store_true", help="реально постить (по умолчанию dry-run)")
    parser.add_argument("--resolve", action="store_true", help="в dry-run создать партнёрские ссылки")
    parser.add_argument("--json", action="store_true", help="вывести отчёт в JSON")
    return parser


def resolve_platforms(raw: str) -> List[str]:
    raw = (raw or "").strip().lower()
    if not raw or raw == "all":
        return list(DEFAULT_PLATFORMS)
    items = [item.strip() for item in raw.split(",") if item.strip()]
    unknown = [item for item in items if item not in DEFAULT_PLATFORMS]
    if unknown:
        raise ConfigError("Неизвестные платформы: {}".format(", ".join(unknown)))
    return items


def _print(report: Dict[str, Any], as_json: bool) -> None:
    print(json.dumps(report, ensure_ascii=False, indent=2) if as_json else _human(report))


def _human(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    if "platforms" in report and isinstance(report["platforms"], dict):
        lines.append("Проверка подключений:")
        for name, data in report["platforms"].items():
            mark = "OK" if data.get("ok") else "FAIL"
            account = data.get("account") or data.get("detail") or ""
            lines.append("  {:<10} {} {}".format(name, mark, account))
        for name, data in (report.get("links") or {}).items():
            mark = "OK" if data.get("ok") else "FAIL"
            detail = data.get("links")
            lines.append("  {:<10} {} {}".format(name, mark, "links={}".format(detail) if detail is not None else data.get("detail", "")))
        return "\n".join(lines)
    lines.append("Режим: {}".format(report.get("mode")))
    for item in report.get("platforms", []):
        lines.append(
            "[{}] {} chars={} url={}".format(
                item.get("platform"), item.get("status", "done"), item.get("chars"), item.get("url")
            )
        )
        for result in item.get("results") or []:
            lines.append(
                "  -> {:<8} {} {}{}".format(
                    "OK" if result.get("ok") else "FAIL",
                    result.get("platform"),
                    result.get("url") or "",
                    (" | " + result.get("detail", "")) if result.get("detail") else "",
                )
            )
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    env = load_env(args.env or None)
    resolved = resolve_market_options(
        market=args.market,
        lang=args.lang,
        text=args.text,
        disclosure=args.disclosure,
        subid_prefix=args.subid_prefix,
    )
    args.text = resolved["text"]
    args.disclosure = resolved["disclosure"]
    args.subid_prefix = resolved["subid_prefix"]
    try:
        platforms = resolve_platforms(args.platforms)
    except ConfigError as exc:
        print("Ошибка: {}".format(exc), file=sys.stderr)
        return 2
    try:
        if args.verify:
            report = run_verify(env, platforms)
            _print(report, args.json)
            ok = any(data.get("ok") for data in report["platforms"].values())
            return 0 if ok else 1
        report = run_publish(
            env=env,
            platforms=platforms,
            brand_url=args.brand_url or None,
            direct_url=args.url or None,
            template=args.text,
            title=args.title,
            disclosure=args.disclosure,
            trs=args.trs or None,
            subid_prefix=args.subid_prefix,
            allow_plain=args.allow_plain,
            use_tracker=args.tracker,
            telegram_targets=_telegram_targets(args, env),
            execute=args.execute,
            resolver=args.resolve or args.execute,
        )
        _print(report, args.json)
        if args.execute:
            failures = [r for item in report["platforms"] for r in item.get("results", []) if not r.get("ok")]
            return 1 if failures else 0
        return 0
    except ConfigError as exc:
        print("Ошибка конфигурации: {}".format(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
