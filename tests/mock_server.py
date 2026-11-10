"""Mock HTTP server emulating the free social APIs used by affiliate-fanout."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse


class MockAPIs:
    def __init__(self) -> None:
        self.requests: List[Dict[str, Any]] = []
        api = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: Any) -> None:  # silence
                pass

            def _read(self) -> Dict[str, Any]:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                ctype = self.headers.get("Content-Type") or ""
                if "json" in ctype:
                    try:
                        return json.loads(raw or b"{}")
                    except ValueError:
                        return {}
                return {k: v[0] for k, v in parse_qs(raw.decode("utf-8", "replace")).items()}

            def _send(self, status: int, payload: Any = None) -> None:
                body = b"" if payload is None else json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if body:
                    self.wfile.write(body)

            def _record(self) -> Dict[str, Any]:
                parsed = urlparse(self.path)
                body = self._read()
                entry = {
                    "method": self.command,
                    "path": parsed.path,
                    "query": {k: v[0] for k, v in parse_qs(parsed.query).items()},
                    "headers": dict(self.headers),
                    "body": body,
                }
                api.requests.append(entry)
                return entry

            def do_GET(self) -> None:  # noqa: N802
                entry = self._record()
                path = entry["path"]
                if path.endswith("/getMe"):
                    return self._send(200, {"ok": True, "result": {"id": 1, "username": "testbot", "first_name": "Test"}})
                if path.endswith("/getChat"):
                    return self._send(200, {"ok": True, "result": {"title": "Test channel", "username": "testchan"}})
                if path.endswith("/v2/user/info"):
                    return self._send(200, {"meta": {"status": 200}, "response": {"user": {"name": "tester"}}})
                if path.endswith("/api/v1/accounts/verify_credentials"):
                    return self._send(200, {"username": "tester", "acct": "tester@example.social"})
                if "/api/webhooks/" in path:
                    return self._send(200, {"name": "test-webhook", "channel_id": "1"})
                if path.endswith("/admin/links"):
                    return self._send(200, {"ok": True, "links": [{"code": "existing", "target": "https://example.com"}]})
                if path.endswith("/api/users/me"):
                    return self._send(200, {"username": "tester"})
                if path.endswith("/rest/v1/user"):
                    return self._send(200, {"user": {"fullName": "Tester"}})
                return self._send(404, {"error": "not found"})

            def do_POST(self) -> None:  # noqa: N802
                entry = self._record()
                path = entry["path"]
                body = entry["body"]
                if path.endswith("/sendMessage"):
                    return self._send(200, {"ok": True, "result": {"message_id": 42, "chat": {"username": "testchan"}}})
                if "/v2/blog/" in path and path.endswith("/post"):
                    return self._send(201, {"meta": {"status": 201}, "response": {"id": "123"}})
                if path.endswith("/xrpc/com.atproto.server.createSession"):
                    return self._send(200, {"accessJwt": "jwt", "did": "did:plc:test", "handle": "tester.bsky.social"})
                if path.endswith("/xrpc/com.atproto.repo.createRecord"):
                    return self._send(200, {"uri": "at://did:plc:test/app.bsky.feed.post/abc123"})
                if path.endswith("/api/v1/statuses"):
                    return self._send(200, {"url": "https://example.social/@tester/1", "uri": "https://example.social/users/tester/statuses/1"})
                if "/api/webhooks/" in path:
                    return self._send(204)
                if path.endswith("/createAccount"):
                    return self._send(200, {"ok": True, "result": {"access_token": "tg-token"}})
                if path.endswith("/createPage"):
                    return self._send(200, {"ok": True, "result": {"url": "https://telegra.ph/test-page"}})
                if path.endswith("/links/v1/create"):
                    links = []
                    for item in body.get("links") or []:
                        sub = item.get("sub_id") or "x"
                        links.append({"url": item.get("url"), "code": "success", "partner_url": "https://aviasales.tpk.ro/" + str(sub).upper()})
                    return self._send(200, {"result": {"marker": body.get("marker"), "trs": body.get("trs"), "shorten": True, "links": links}})
                if path.endswith("/admin/links"):
                    return self._send(200, {"ok": True, "record": {"code": body.get("code"), "target": body.get("target")}})
                if path.endswith("/method/groups.getById"):
                    return self._send(200, {"response": [{"name": "Test Group"}]})
                if path.endswith("/method/wall.post"):
                    return self._send(200, {"response": {"post_id": 7}})
                if path.endswith("/api/articles"):
                    return self._send(201, {"url": "https://dev.to/tester/deal-abc"})
                if path.endswith("/rest/v1/raindrop"):
                    return self._send(200, {"item": {"link": "https://raindrop.io/tester/collection-1"}})
                if "/services/" in path:
                    return self._send(200, {"ok": True})
                return self._send(404, {"error": "not found"})

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address[:2]
        return "http://{}:{}".format(host, port)

    def __enter__(self) -> "MockAPIs":
        self._thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def find(self, substring: str) -> Optional[Dict[str, Any]]:
        for request in reversed(self.requests):
            if substring in request["path"]:
                return request
        return None

    def count(self, substring: str) -> int:
        return sum(1 for request in self.requests if substring in request["path"])
