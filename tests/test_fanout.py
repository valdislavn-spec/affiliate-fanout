"""Tests for adapters, links, text composition and the publishing pipeline."""

from __future__ import annotations

import unittest

from affiliate_fanout import adapters
from affiliate_fanout.cli import compose_text, resolve_market_options, run_publish, run_verify
from affiliate_fanout.env import load_env
from affiliate_fanout.links import LinkTracker, TravelpayoutsLinks

from mock_server import MockAPIs


class FanoutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.api = MockAPIs()
        self.api.__enter__()
        base = self.api.base_url
        self.env = {
            "TELEGRAM_BOT_TOKEN": "123:test",
            "TELEGRAM_API_BASE": base,
            "TELEGRAM_CHAT_ID_ALPHA": "-1001",
            "TELEGRAM_CHAT_ID_BETA": "-1002",
            "TUMBLR_CONSUMER_KEY": "ck",
            "TUMBLR_CONSUMER_SECRET": "cs",
            "TUMBLR_OAUTH_TOKEN": "tk",
            "TUMBLR_OAUTH_TOKEN_SECRET": "ts",
            "TUMBLR_BLOG": "vlad-007",
            "TUMBLR_API_BASE": base,
            "BLUESKY_HANDLE": "tester.bsky.social",
            "BLUESKY_APP_PASSWORD": "app-password",
            "BLUESKY_BASE_URL": base,
            "MASTODON_BASE_URL": base,
            "MASTODON_TOKEN": "masto-token",
            "AKKOMA_BASE_URL": base,
            "AKKOMA_TOKEN": "akkoma-token",
            "PIXELFED_BASE_URL": base,
            "PIXELFED_TOKEN": "pixelfed-token",
            "DISCORD_WEBHOOK_URL": base + "/api/webhooks/1/token",
            "TELEGRAPH_API_BASE": base,
            "TRAVELPAYOUTS_TOKEN": "tp-token",
            "TRAVELPAYOUTS_MARKER": "674170",
            "TRAVELPAYOUTS_TRS": "597672",
            "TRAVELPAYOUTS_API_BASE": base,
            "LINK_TRACKER_BASE": base,
            "LINK_TRACKER_ADMIN_TOKEN": "tracker-token",
            "VK_ACCESS_TOKEN": "vk-token",
            "VK_GROUP_ID": "123",
            "VK_API_BASE": base,
            "DEVTO_API_KEY": "devto-key",
            "DEVTO_API_BASE": base,
            "RAINDROP_TOKEN": "rd-token",
            "RAINDROP_API_BASE": base,
            "SLACK_WEBHOOK_URL": base + "/services/T/B/X",
            "X_API_KEY": "x-key", "X_API_SECRET": "x-secret",
            "X_ACCESS_TOKEN": "x-token", "X_ACCESS_SECRET": "x-access-secret",
            "X_API_BASE": base,
            "REDDIT_CLIENT_ID": "rd-id", "REDDIT_CLIENT_SECRET": "rd-secret",
            "REDDIT_USERNAME": "rd-user", "REDDIT_PASSWORD": "rd-pass",
            "REDDIT_SUBREDDIT": "testsub",
            "REDDIT_AUTH_BASE": base, "REDDIT_API_BASE": base,
            "PINTEREST_ACCESS_TOKEN": "pin-token", "PINTEREST_BOARD_ID": "board-1",
            "PINTEREST_IMAGE_URL": "https://example.com/pin.jpg",
            "PINTEREST_API_BASE": base,
            "FACEBOOK_PAGE_ID": "page123", "FACEBOOK_PAGE_TOKEN": "fb-token",
            "META_API_BASE": base,
            "INSTAGRAM_USER_ID": "ig123", "INSTAGRAM_ACCESS_TOKEN": "ig-token",
            "INSTAGRAM_IMAGE_URL": "https://example.com/ig.jpg",
            "THREADS_USER_ID": "thread123", "THREADS_ACCESS_TOKEN": "th-token",
            "THREADS_API_BASE": base,
            "LINKEDIN_ACCESS_TOKEN": "li-token", "LINKEDIN_AUTHOR_URN": "urn:li:person:abc",
            "LINKEDIN_API_BASE": base,
            "MEDIUM_TOKEN": "med-token", "MEDIUM_AUTHOR_ID": "med-123",
            "MEDIUM_API_BASE": base,
            "BLOGGER_CLIENT_ID": "g-id", "BLOGGER_CLIENT_SECRET": "g-secret",
            "BLOGGER_REFRESH_TOKEN": "g-refresh", "BLOGGER_BLOG_ID": "123",
            "GOOGLE_TOKEN_URL": base + "/token", "BLOGGER_API_BASE": base,
            "WP_BASE_URL": base,
            "WP_USERNAME": "wp-user", "WP_APP_PASSWORD": "wp-pass",
        }

    def tearDown(self) -> None:
        self.api.__exit__(None, None, None)

    # ------------------------------------------------------------- adapters
    def test_verify_all_platforms(self) -> None:
        report = run_verify(
            self.env,
            [
                "telegram", "vk", "tumblr", "bluesky", "mastodon", "akkoma",
                "pixelfed", "devto", "discord", "telegraph", "slack", "raindrop",
                "x", "reddit", "pinterest", "facebook", "instagram", "threads",
                "linkedin", "medium", "blogger", "wordpress",
            ],
        )
        for platform, data in report["platforms"].items():
            self.assertTrue(data.get("ok"), "{}: {}".format(platform, data))
        self.assertTrue(report["links"]["travelpayouts"]["ok"])
        self.assertTrue(report["links"]["tracker"]["ok"])

    def test_telegram_post(self) -> None:
        result = adapters.post_telegram(self.env, "-1001", "hello https://example.com")
        self.assertTrue(result.ok)
        self.assertEqual(result.url, "https://t.me/testchan")
        request = self.api.find("/sendMessage")
        self.assertEqual(request["body"]["chat_id"], "-1001")

    def test_tumblr_post_signs_oauth(self) -> None:
        result = adapters.post_tumblr(self.env, "Deal", "body text")
        self.assertTrue(result.ok)
        self.assertIn("tumblr.com/post/123", result.url)
        request = self.api.find("/post")
        self.assertIn("OAuth", request["headers"]["Authorization"])
        self.assertEqual(request["body"]["type"], "text")

    def test_bluesky_post_has_link_facet(self) -> None:
        text = "Deal: https://aviasales.tpk.ro/ABC123"
        result = adapters.post_bluesky(self.env, text)
        self.assertTrue(result.ok)
        self.assertIn("bsky.app/profile/tester.bsky.social/post/abc123", result.url)
        request = self.api.find("createRecord")
        record = request["body"]["record"]
        self.assertEqual(record["text"], text)
        self.assertTrue(record["facets"])
        index = record["facets"][0]["index"]
        url = "https://aviasales.tpk.ro/ABC123"
        self.assertEqual(record["text"][index["byteStart"]:index["byteEnd"]], url)

    def test_fediverse_posts(self) -> None:
        for network in ("mastodon", "akkoma", "pixelfed"):
            result = adapters.post_fediverse(self.env, network, "hi")
            self.assertTrue(result.ok, network)
            self.assertEqual(result.url, "https://example.social/@tester/1")

    def test_discord_post(self) -> None:
        result = adapters.post_discord(self.env, "hello")
        self.assertTrue(result.ok)
        request = self.api.find("/api/webhooks/")
        self.assertEqual(request["body"]["content"], "hello")

    def test_telegraph_post(self) -> None:
        result = adapters.post_telegraph(self.env, "Title", "Line one\nhttps://example.com")
        self.assertTrue(result.ok)
        self.assertEqual(result.url, "https://telegra.ph/test-page")
        page = self.api.find("/createPage")
        self.assertEqual(page["body"]["title"], "Title")
        content = page["body"]["content"]
        self.assertIn("Line one", content if isinstance(content, str) else str(content))

    def test_vk_post(self) -> None:
        verify = adapters.verify_vk(self.env)
        self.assertTrue(verify["ok"])
        self.assertIn("Test Group", verify["account"])
        result = adapters.post_vk(self.env, "hello vk")
        self.assertTrue(result.ok)
        self.assertEqual(result.url, "https://vk.com/wall-123_7")
        request = self.api.find("wall.post")
        self.assertEqual(request["body"]["owner_id"], "-123")

    def test_devto_post(self) -> None:
        verify = adapters.verify_devto(self.env)
        self.assertEqual(verify["account"], "dev.to:tester")
        result = adapters.post_devto(self.env, "Deal title", "post body")
        self.assertTrue(result.ok)
        self.assertIn("dev.to/tester", result.url)

    def test_raindrop_post(self) -> None:
        verify = adapters.verify_raindrop(self.env)
        self.assertTrue(verify["ok"])
        result = adapters.post_raindrop(self.env, "Deal", "https://aviasales.tpk.ro/ABC", "text")
        self.assertTrue(result.ok)
        self.assertIn("raindrop.io", result.url)

    def test_slack_post(self) -> None:
        verify = adapters.verify_slack(self.env)
        self.assertTrue(verify["ok"])
        result = adapters.post_slack(self.env, "hello slack")
        self.assertTrue(result.ok)
        request = self.api.find("/services/")
        self.assertEqual(request["body"]["text"], "hello slack")

    def test_global_adapters_post(self) -> None:
        self.assertTrue(adapters.post_x(self.env, "hello x").ok)
        self.assertTrue(adapters.post_reddit(self.env, "Deal", "https://example.com").ok)
        self.assertTrue(adapters.post_pinterest(self.env, "Deal", "https://example.com", "text").ok)
        self.assertTrue(adapters.post_facebook(self.env, "text", "https://example.com").ok)
        self.assertTrue(adapters.post_instagram(self.env, "caption").ok)
        self.assertTrue(adapters.post_threads(self.env, "thread text").ok)
        self.assertTrue(adapters.post_linkedin(self.env, "linkedin text").ok)
        medium = adapters.post_medium(self.env, "Title", "body")
        self.assertTrue(medium.ok)
        self.assertIn("medium.com", medium.url)
        blogger = adapters.post_blogger(self.env, "Title", "body")
        self.assertTrue(blogger.ok)
        self.assertIn("blogspot.com", blogger.url)
        wordpress = adapters.post_wordpress(self.env, "Title", "body")
        self.assertTrue(wordpress.ok)
        self.assertIn("test.blog", wordpress.url)

    def test_x_oauth_header_present(self) -> None:
        result = adapters.post_x(self.env, "hello x")
        self.assertTrue(result.ok)
        request = self.api.find("/2/tweets")
        self.assertIn("OAuth", request["headers"]["Authorization"])
        self.assertEqual(request["body"]["text"], "hello x")

    def test_market_presets_us(self) -> None:
        resolved = resolve_market_options(market="us")
        self.assertEqual(resolved["lang"], "en")
        self.assertIn("Ad", resolved["disclosure"])
        self.assertEqual(resolved["subid_prefix"], "fanout_us")
        self.assertIn("flights", resolved["text"])

    def test_market_presets_latam(self) -> None:
        resolved = resolve_market_options(market="latam")
        self.assertEqual(resolved["lang"], "es")
        self.assertIn("Publicidad", resolved["disclosure"])
        self.assertEqual(resolved["subid_prefix"], "fanout_latam")
        self.assertIn("vuelos", resolved["text"])

    def test_market_lang_override_and_explicit_text(self) -> None:
        override = resolve_market_options(market="latam", lang="en")
        self.assertIn("Travel deal", override["text"])
        explicit = resolve_market_options(
            market="us", text="Custom {url}", disclosure="Ad", subid_prefix="custom"
        )
        self.assertEqual(explicit["text"], "Custom {url}")
        self.assertEqual(explicit["disclosure"], "Ad")
        self.assertEqual(explicit["subid_prefix"], "custom")

    # ---------------------------------------------------------------- links
    def test_travelpayouts_creates_links_with_subids(self) -> None:
        tp = TravelpayoutsLinks(self.env)
        urls = tp.create(
            [
                ("https://www.aviasales.com/", "fanout_telegram"),
                ("https://www.aviasales.com/", "fanout_tumblr"),
            ]
        )
        self.assertEqual(urls, ["https://aviasales.tpk.ro/FANOUT_TELEGRAM", "https://aviasales.tpk.ro/FANOUT_TUMBLR"])
        request = self.api.find("/links/v1/create")
        self.assertEqual(request["body"]["trs"], 597672)
        self.assertEqual(request["body"]["marker"], 674170)
        self.assertEqual(request["body"]["links"][0]["sub_id"], "fanout_telegram")

    def test_travelpayouts_unsubscribed_brand_raises(self) -> None:
        from affiliate_fanout.env import ConfigError
        tp = TravelpayoutsLinks(self.env)
        with self.assertRaises(ConfigError) as caught:
            tp.create([("https://www.unsubscribed.example/", "fanout_us_x")])
        self.assertIn("Links API", str(caught.exception))

    def test_tracker_wrap(self) -> None:
        tracker = LinkTracker(self.env)
        url = tracker.wrap("https://aviasales.tpk.ro/ABC", "telegram")
        self.assertIn("/r/fanout-telegram-", url)
        request = self.api.find("/admin/links")
        self.assertEqual(request["body"]["network"], "telegram")
        self.assertEqual((request["headers"].get("x-token") or request["headers"].get("X-Token")), "tracker-token")

    # ---------------------------------------------------------------- text
    def test_compose_truncates_bluesky(self) -> None:
        long_text = "x" * 500 + " {url}"
        text = compose_text(long_text, "https://aviasales.tpk.ro/ABC", "Ad · affiliate link", 300)
        self.assertLessEqual(len(text), 300)
        self.assertIn("https://aviasales.tpk.ro/ABC", text)
        self.assertIn("Ad · affiliate link", text)

    def test_compose_without_placeholder_appends_url(self) -> None:
        text = compose_text("Just a deal", "https://example.com/x", "", 4096)
        self.assertIn("https://example.com/x", text)

    # ---------------------------------------------------------------- pipeline
    def test_dry_run_does_not_post(self) -> None:
        report = run_publish(
            env=self.env,
            platforms=["telegram", "bluesky"],
            brand_url="https://www.aviasales.com/",
            direct_url=None,
            template="Deal: {url}",
            title="Deals",
            disclosure="Ad · affiliate link",
            trs=None,
            subid_prefix="fanout",
            allow_plain=False,
            use_tracker=False,
            telegram_targets=[("-1001", "alpha")],
            execute=False,
            resolver=False,
        )
        self.assertEqual(report["mode"], "dry-run")
        self.assertEqual(self.api.count("/sendMessage"), 0)
        self.assertEqual(self.api.count("/createRecord"), 0)

    def test_execute_publishes_everywhere(self) -> None:
        report = run_publish(
            env=self.env,
            platforms=["telegram", "tumblr", "bluesky", "akkoma", "pixelfed", "telegraph", "discord"],
            brand_url="https://www.aviasales.com/",
            direct_url=None,
            template="Cheap flights: {url}",
            title="Deals",
            disclosure="Ad · affiliate link",
            trs=None,
            subid_prefix="fanout",
            allow_plain=False,
            use_tracker=False,
            telegram_targets=[("-1001", "alpha"), ("-1002", "beta")],
            execute=True,
            resolver=True,
        )
        results = [r for item in report["platforms"] for r in item.get("results", [])]
        self.assertTrue(results)
        self.assertTrue(all(r.get("ok") for r in results), results)
        self.assertEqual(self.api.count("/sendMessage"), 2)  # two Telegram chats
        self.assertEqual(self.api.count("/links/v1/create"), 1)  # batched partner links
        for suffix in ("/post", "createRecord", "/api/v1/statuses", "/createPage", "/api/webhooks/"):
            self.assertGreaterEqual(self.api.count(suffix), 1, suffix)

    def test_missing_platform_config_isolated(self) -> None:
        env = dict(self.env)
        env.pop("BLUESKY_HANDLE", None)
        report = run_publish(
            env=env,
            platforms=["bluesky", "telegraph"],
            brand_url=None,
            direct_url="https://example.com/aff",
            template="Deal: {url}",
            title="Deals",
            disclosure="",
            trs=None,
            subid_prefix="fanout",
            allow_plain=True,
            use_tracker=False,
            telegram_targets=[],
            execute=True,
            resolver=True,
        )
        by_platform = {item["platform"]: item for item in report["platforms"]}
        bluesky = by_platform["bluesky"]["results"][0]
        telegraph = by_platform["telegraph"]["results"][0]
        self.assertFalse(bluesky["ok"])
        self.assertTrue(telegraph["ok"])

    def test_env_loading(self) -> None:
        env = load_env(None, extra={"A": "1"})
        self.assertEqual(env.get("A"), "1")


if __name__ == "__main__":
    unittest.main()
