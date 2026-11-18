"""HTTP server: JSON API + static frontend (stdlib only)."""
import base64
import hmac
import json
import mimetypes
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

from . import config, db
from .errors import ApiError
from .routes import Ctx, router

mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("image/svg+xml", ".svg")

SECURITY_HEADERS = {
    # No inline scripts anywhere; inline *styles* are needed for SVG charts / CSS variables.
    "Content-Security-Policy": ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                                "img-src 'self' data:; object-src 'none'; base-uri 'none'; "
                                "form-action 'self'; frame-ancestors 'none'"),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}
MUTATING = ("POST", "PUT", "PATCH", "DELETE")


class AuthThrottle:
    """Blocks a client after too many failed logins (in memory; resets on restart)."""

    def __init__(self, max_failures, window):
        self.max, self.window = max_failures, window
        self._fails, self._lock = {}, threading.Lock()

    def retry_after(self, key, now=None):
        now = now or time.monotonic()
        with self._lock:
            recent = [t for t in self._fails.get(key, []) if now - t < self.window]
            self._fails[key] = recent
            if len(recent) >= self.max:
                return max(1, int(self.window - (now - recent[0])))
        return 0

    def failed(self, key, now=None):
        with self._lock:
            self._fails.setdefault(key, []).append(now or time.monotonic())
            if len(self._fails) > 10_000:  # bound memory under a distributed spray
                self._fails.pop(next(iter(self._fails)))

    def succeeded(self, key):
        with self._lock:
            self._fails.pop(key, None)


def _hostname(host_header):
    host = (host_header or "").strip().lower()
    if host.startswith("["):
        return host[1:host.find("]")] if "]" in host else host
    return host.split(":")[0]


class Handler(BaseHTTPRequestHandler):
    server_version = "SkillQuest/1.0"
    protocol_version = "HTTP/1.1"
    db_path = None        # set by make_server
    allowed_hosts = None  # None = any Host header accepted
    basic_auth = ""       # "user:pass" or ""
    quiet = False
    trust_proxy = False
    throttle = None       # AuthThrottle, set by make_server
    timeout = config.REQUEST_TIMEOUT  # idle / slow clients are dropped instead of pinning a thread

    # ---- plumbing ----
    def log_message(self, fmt, *args):
        if not self.quiet and "--quiet" not in sys.argv:
            sys.stderr.write("%s  %s\n" % (self.log_date_time_string(), fmt % args))

    def end_headers(self):
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)
        super().end_headers()

    def _send(self, status, payload=None, headers=None):
        body = b"" if payload is None else json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        if payload is not None:
            self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _read_raw(self):
        """Always consume the body so keep-alive connections stay in sync."""
        if self.headers.get("Transfer-Encoding"):
            self.close_connection = True
            raise ApiError(411, "length_required", "Chunked request bodies are not supported.")
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self.close_connection = True
            raise ApiError(400, "bad_request", "Invalid Content-Length.")
        if length < 0 or length > config.MAX_BODY_BYTES:
            self.close_connection = True
            raise ApiError(413, "payload_too_large", "Request body is too large.")
        return self.rfile.read(length) if length else b""

    @staticmethod
    def _parse_json(raw):
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise ApiError(400, "invalid_json", "Request body is not valid JSON.")

    # ---- security gates ----
    def _check_host(self):
        # Blocks DNS-rebinding: a page on evil.com that resolves to 127.0.0.1 still sends Host: evil.com
        if self.allowed_hosts is not None and _hostname(self.headers.get("Host")) not in self.allowed_hosts:
            raise ApiError(403, "forbidden_host", "This Host header is not allowed.")

    def _client_ip(self):
        if self.trust_proxy:  # only behind a proxy that *overwrites* X-Forwarded-For
            fwd = self.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            if fwd:
                return fwd
        return self.client_address[0]

    def _check_auth(self, path):
        if not self.basic_auth or path == "/api/health":
            return
        ip = self._client_ip()
        wait = self.throttle.retry_after(ip) if self.throttle else 0
        if wait:
            raise ApiError(429, "too_many_attempts", f"Too many failed logins. Try again in {wait} s.")
        header = self.headers.get("Authorization", "")
        ok = False
        if header.startswith("Basic "):
            try:
                given = base64.b64decode(header[6:], validate=True)
                ok = hmac.compare_digest(given, self.basic_auth.encode())
            except ValueError:
                ok = False
        if not ok:
            if header and self.throttle:  # a bare request (browser's first try) is not a failed guess
                self.throttle.failed(ip)
            raise ApiError(401, "unauthorized", "Authentication required.")
        if self.throttle:
            self.throttle.succeeded(ip)

    def _check_origin(self):
        # CSRF defence in depth: browsers attach Origin to cross-site writes.
        origin = self.headers.get("Origin")
        if origin and self.command in MUTATING:
            netloc = urlsplit(origin).netloc.lower()
            if netloc != (self.headers.get("Host") or "").lower():
                raise ApiError(403, "forbidden_origin", "Cross-origin requests are not allowed.")

    # ---- dispatch ----
    def _handle(self):
        parts = urlsplit(self.path)
        path = unquote(parts.path)
        try:
            self._check_host()
            self._check_auth(path)
        except ApiError as e:
            headers = {"WWW-Authenticate": 'Basic realm="SkillQuest"'} if e.status == 401 else None
            if e.status == 429:
                headers = {"Retry-After": e.message.rsplit(" ", 2)[-2]}
            if self.command in MUTATING:  # unread body would desync keep-alive
                self.close_connection = True
            return self._send(e.status, e.to_dict(), headers)
        if path.startswith("/api/") or path == "/api":
            return self._api(path, dict(parse_qsl(parts.query)))
        if self.command not in ("GET", "HEAD"):
            return self._send(405, {"error": {"code": "method_not_allowed", "message": "Method not allowed."}})
        self._static(path)

    def _api(self, path, query):
        conn = None
        try:
            self._check_origin()
            raw = self._read_raw()
            handler, params = router.match(self.command, path)
            if handler is None:
                raise ApiError(404, "not_found", "Unknown API endpoint.")
            if handler == "method_not_allowed":
                raise ApiError(405, "method_not_allowed", "Method not allowed.")
            body = None
            if self.command in ("POST", "PUT", "PATCH"):
                # Requiring JSON forces a CORS preflight for cross-site pages (no "simple request" CSRF).
                if self.headers.get_content_type() != "application/json":
                    raise ApiError(415, "unsupported_media_type", "Content-Type must be application/json.")
                body = self._parse_json(raw)
            conn = db.connect(self.db_path)
            result = handler(Ctx(conn, params, query, body))
            status, payload = result if isinstance(result, tuple) else (200, result)
            self._send(status, payload)
        except ApiError as e:
            self._send(e.status, e.to_dict())
        except Exception:  # unexpected — log, don't leak internals
            traceback.print_exc()
            self._send(500, {"error": {"code": "server_error", "message": "Something went wrong on the server."}})
        finally:
            if conn:
                conn.close()

    def _static(self, path):
        root = config.FRONTEND_DIR.resolve()
        rel = "index.html" if path in ("", "/") else path.lstrip("/")
        target = (root / rel).resolve()
        if root not in target.parents and target != root or not target.is_file():
            if "." in Path(rel).name:  # missing asset
                return self._send(404, {"error": {"code": "not_found", "message": "File not found."}})
            target = root / "index.html"  # SPA fallback
        data = target.read_bytes()
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text/") or "javascript" in ctype else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = _handle


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 128  # default 5 drops connections under bursts


def make_server(host=None, port=None, db_path=None, *, quiet=False, basic_auth=None, allowed_hosts=None,
                trust_proxy=None, max_auth_failures=None, lockout_seconds=None):
    """Create the HTTP server.

    allowed_hosts: iterable of accepted Host names. By default, a loopback bind accepts only
    localhost/127.0.0.1/::1 (+ SKILLQUEST_ALLOWED_HOSTS); a non-loopback bind accepts any Host
    unless SKILLQUEST_ALLOWED_HOSTS is set.
    """
    host = host or config.HOST
    db_path = db_path or config.DB_PATH
    db.init_db(db_path)
    if allowed_hosts is not None:
        hosts = {h.lower() for h in allowed_hosts}
    elif host.lower() in config.LOOPBACK:
        hosts = config.LOOPBACK | config.ALLOWED_HOSTS
    else:
        # loopback names stay allowed so the container healthcheck (Host: 127.0.0.1) keeps working
        hosts = (config.LOOPBACK | config.ALLOWED_HOSTS) if config.ALLOWED_HOSTS else None
    handler = type("BoundHandler", (Handler,), {
        "db_path": db_path, "allowed_hosts": hosts, "quiet": quiet,
        "basic_auth": config.BASIC_AUTH if basic_auth is None else basic_auth,
        "trust_proxy": config.TRUST_PROXY if trust_proxy is None else trust_proxy,
        "throttle": AuthThrottle(config.AUTH_MAX_FAILURES if max_auth_failures is None else max_auth_failures,
                                 config.AUTH_LOCKOUT_SECONDS if lockout_seconds is None else lockout_seconds)})
    srv = Server((host, config.PORT if port is None else port), handler)
    return srv
