"""``coflow mcp-stdio``: forwards stdio to the loopback endpoint and never resolves the database
path, so two local AI clients share one core (spec §4.5, AT-K7).

Owned by track X (interfaces); increment I1, spec §12.2.

A local AI client starts ``coflow mcp-stdio`` as its MCP server process. The shim reads one
JSON-RPC message (or batch) per line from stdin, posts it to the core's Streamable HTTP endpoint on
loopback with the client's bearer token, and writes every JSON-RPC message of the answer to stdout,
one per line. It knows only a URL and a token: it imports nothing that can open or locate an
instance (no store, no module, no data root), so it works only while ``coflow run`` serves the
instance, and every client goes through the one writer.

- The endpoint: ``--url``, else ``COFLOW_MCP_URL``, else ``http://127.0.0.1:8741/mcp``. Only
  loopback URLs are accepted.
- The token: ``COFLOW_MCP_TOKEN`` (or ``--token-file``), from ``coflow mcp token new``. It is never
  taken from the command line, where other local users could read it.
- After ``initialize`` the negotiated protocol version (and a session id, if the core issues one)
  is sent with every later request.
- When the core is down or refuses the token, a request gets a JSON-RPC error that says what to do;
  a notification is dropped. stdout carries nothing but protocol messages.

Spec note: the spec names no port; 8741 is the default of both ``coflow run`` and the shim, and
``coflow run --port`` with ``--url`` (or ``COFLOW_MCP_URL``) moves both. Messages are forwarded one
at a time, in the order they arrive, which is enough for the read tools of I1.
"""

from __future__ import annotations

import http.client
import json
import sys
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import BinaryIO, TextIO
from urllib.parse import urlsplit

__all__ = [
    "DEFAULT_PORT",
    "DEFAULT_URL",
    "TOKEN_ENV",
    "URL_ENV",
    "Forwarder",
    "HttpPost",
    "PostResult",
    "check_loopback_url",
    "run_shim",
]

DEFAULT_PORT = 8741
DEFAULT_URL = f"http://127.0.0.1:{DEFAULT_PORT}/mcp"
TOKEN_ENV = "COFLOW_MCP_TOKEN"
URL_ENV = "COFLOW_MCP_URL"
_LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")
_CORE_DOWN = -32000


@dataclass(frozen=True, slots=True)
class PostResult:
    status: int
    content_type: str
    body: bytes
    headers: Mapping[str, str] = field(default_factory=dict)


Post = Callable[[bytes, Mapping[str, str]], PostResult]


def check_loopback_url(url: str) -> tuple[str, int, str]:
    """(host, port, path) of a loopback ``http`` URL; ``ValueError`` for anything else."""
    parts = urlsplit(url)
    if parts.scheme != "http" or parts.hostname not in _LOOPBACK_HOSTS:
        raise ValueError(f"the shim forwards to a loopback http URL only, not {url!r}")
    return parts.hostname, parts.port or 80, parts.path or "/"


class HttpPost:
    """POST to the loopback endpoint over one kept-alive ``http.client`` connection."""

    def __init__(self, url: str, *, timeout: float = 120.0) -> None:
        self.host, self.port, self.path = check_loopback_url(url)
        self.timeout = timeout
        self._conn: http.client.HTTPConnection | None = None

    def __call__(self, body: bytes, headers: Mapping[str, str]) -> PostResult:
        for attempt in (1, 2):
            conn = self._conn or http.client.HTTPConnection(
                self.host, self.port, timeout=self.timeout
            )
            self._conn = conn
            try:
                conn.request("POST", self.path, body=body, headers=dict(headers))
                response = conn.getresponse()
                data = response.read()
            except (http.client.RemoteDisconnected, BrokenPipeError, ConnectionResetError):
                self.close()
                if attempt == 2:
                    raise
                continue
            except OSError:
                self.close()
                raise
            return PostResult(
                status=response.status,
                content_type=(response.getheader("content-type") or "").lower(),
                body=data,
                headers={k.lower(): v for k, v in response.getheaders()},
            )
        raise AssertionError("unreachable")  # pragma: no cover

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None


def _sse_messages(body: bytes) -> list[str]:
    """The ``data`` payloads of a ``text/event-stream`` body, one per event."""
    out: list[str] = []
    data: list[str] = []
    for raw in body.decode("utf-8").splitlines():
        if raw == "":
            if data:
                out.append("\n".join(data))
                data = []
        elif raw.startswith("data:"):
            data.append(raw[5:].lstrip(" "))
    if data:
        out.append("\n".join(data))
    return out


def _ids(message: object) -> list[object]:
    """The ids of the requests in a message or batch (notifications have none)."""
    items = message if isinstance(message, list) else [message]
    return [m["id"] for m in items if isinstance(m, dict) and m.get("id") is not None]


def _error(request_id: object, code: int, message: str) -> bytes:
    body = {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
    return json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _compact(text: str) -> bytes:
    """One JSON message on one line (stdio framing is newline-delimited)."""
    return json.dumps(json.loads(text), ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class Forwarder:
    """Turns one stdin line into the stdout lines of its answer."""

    def __init__(self, url: str, token: str, *, post: Post | None = None) -> None:
        check_loopback_url(url)
        if not token:
            raise ValueError(f"no client token: set {TOKEN_ENV} (see coflow mcp token new)")
        self.url = url
        self.token = token
        self.post = post or HttpPost(url)
        self.protocol_version: str | None = None
        self.session_id: str | None = None

    def _headers(self) -> dict[str, str]:
        headers = {
            "content-type": "application/json",
            "accept": "application/json, text/event-stream",
            "authorization": f"Bearer {self.token}",
        }
        if self.protocol_version:
            headers["mcp-protocol-version"] = self.protocol_version
        if self.session_id:
            headers["mcp-session-id"] = self.session_id
        return headers

    def _remember(self, sent: object, answers: Iterable[object]) -> None:
        sent_items = sent if isinstance(sent, list) else [sent]
        init_ids = {
            m.get("id")
            for m in sent_items
            if isinstance(m, dict) and m.get("method") == "initialize"
        }
        if not init_ids:
            return
        for answer in answers:
            if isinstance(answer, dict) and answer.get("id") in init_ids:
                result = answer.get("result")
                if isinstance(result, dict) and isinstance(result.get("protocolVersion"), str):
                    self.protocol_version = result["protocolVersion"]

    def forward(self, line: bytes) -> list[bytes]:
        text = line.decode("utf-8").strip()
        if not text:
            return []
        try:
            message = json.loads(text)
        except ValueError:
            return [_error(None, -32700, "parse error: one JSON-RPC message per line")]
        ids = _ids(message)
        body = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        try:
            result = self.post(body, self._headers())
        except OSError as exc:
            note = f"CoFlow core is not reachable at {self.url} ({exc}); start it with: coflow run"
            return [_error(i, _CORE_DOWN, note) for i in ids]
        if result.headers.get("mcp-session-id"):
            self.session_id = result.headers["mcp-session-id"]
        if result.status == 202 or not result.body.strip():
            return [] if result.status < 400 else self._http_error(ids, result)
        texts = (
            _sse_messages(result.body)
            if "text/event-stream" in result.content_type
            else [result.body.decode("utf-8")]
        )
        try:
            lines = [_compact(t) for t in texts if t.strip()]
            parsed = [json.loads(t) for t in texts if t.strip()]
        except ValueError:
            return self._http_error(ids, result)
        if result.status >= 400 and not any(isinstance(p, dict) and "jsonrpc" in p for p in parsed):
            return self._http_error(ids, result)
        self._remember(message, parsed)
        return lines

    def _http_error(self, ids: list[object], result: PostResult) -> list[bytes]:
        if result.status == 401:
            note = (
                f"the core refused the client token (HTTP 401): set {TOKEN_ENV} to a token "
                "from: coflow mcp token new --client NAME --scope read"
            )
        else:
            detail = result.body[:300].decode("utf-8", "replace")
            note = f"the core answered HTTP {result.status}: {detail}"
        return [_error(i, _CORE_DOWN, note) for i in ids]


def run_shim(
    url: str,
    token: str,
    *,
    stdin: BinaryIO | None = None,
    stdout: BinaryIO | None = None,
    stderr: TextIO | None = None,
    post: Post | None = None,
) -> int:
    """Forward until stdin closes; the exit code is 0, or 2 for a bad URL or a missing token."""
    err = stderr or sys.stderr
    try:
        forwarder = Forwarder(url, token, post=post)
    except ValueError as exc:
        print(f"coflow mcp-stdio: {exc}", file=err)
        return 2
    source = stdin or sys.stdin.buffer
    sink = stdout or sys.stdout.buffer
    for line in source:
        for answer in forwarder.forward(line):
            sink.write(answer + b"\n")
        sink.flush()
    if isinstance(forwarder.post, HttpPost):
        forwarder.post.close()
    return 0
