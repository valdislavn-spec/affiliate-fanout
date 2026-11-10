"""Tests for the OAuth helper (offline, no network)."""

from __future__ import annotations

import unittest

from tools.oauth_tokens import build_auth_url, env_lines, extract_code, make_pkce


class OAuthHelperTests(unittest.TestCase):
    def test_build_auth_url_pinterest(self) -> None:
        url, state = build_auth_url(
            "pinterest", "cid", "https://example.com/cb", code_challenge=None
        )
        self.assertIn("pinterest.com/oauth", url)
        self.assertIn("client_id=cid", url)
        self.assertIn("response_type=code", url)
        self.assertIn("scope=pins%3Aread", url)
        self.assertTrue(state)

    def test_build_auth_url_x_pkce(self) -> None:
        verifier, challenge = make_pkce()
        self.assertGreaterEqual(len(verifier), 43)
        url, _ = build_auth_url("x", "cid", "https://example.com/cb", code_challenge=challenge)
        self.assertIn("code_challenge=", url)
        self.assertIn("code_challenge_method=S256", url)

    def test_build_auth_url_x_requires_challenge(self) -> None:
        with self.assertRaises(ValueError):
            build_auth_url("x", "cid")

    def test_extract_code_from_callback(self) -> None:
        self.assertEqual(extract_code("https://example.com/cb?code=abc123&state=x"), "abc123")
        self.assertEqual(extract_code("plain-code"), "plain-code")
        self.assertEqual(extract_code(""), "")

    def test_env_lines(self) -> None:
        pinterest = env_lines("pinterest", {"access_token": "AT", "refresh_token": "RT"})
        self.assertIn("PINTEREST_ACCESS_TOKEN=AT", pinterest)
        self.assertIn("PINTEREST_REFRESH_TOKEN=RT", pinterest)
        linkedin = env_lines("linkedin", {"access_token": "LT"})
        self.assertIn("LINKEDIN_ACCESS_TOKEN=LT", linkedin)
        meta = env_lines("meta", {"access_token": "MT"})
        self.assertTrue(any(line.startswith("FACEBOOK_PAGE_TOKEN=") for line in meta))


if __name__ == "__main__":
    unittest.main()
