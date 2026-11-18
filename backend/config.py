"""Application configuration. Everything sensitive comes from the environment, never from code.

Secrets can be given either directly (SKILLQUEST_BASIC_AUTH=user:pass) or as a file path
(SKILLQUEST_BASIC_AUTH_FILE=/run/secrets/...), which is the Docker/Kubernetes-secrets way and keeps the
value out of `docker inspect` and process environments.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT / "frontend"
DB_PATH = os.environ.get("SKILLQUEST_DB", str(ROOT / "data" / "skillquest.db"))
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))
MAX_BODY_BYTES = 1_000_000
LOOPBACK = {"127.0.0.1", "localhost", "::1"}

MIN_PASSWORD_LENGTH = 12
PLACEHOLDER_MARKERS = ("change-me", "change_me", "changeme", "your-password", "password123")


def _flag(name):
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def read_secret(name, default=""):
    """NAME wins; otherwise NAME_FILE is read (surrounding whitespace stripped)."""
    direct = os.environ.get(name)
    if direct:
        return direct.strip()
    path = os.environ.get(name + "_FILE")
    if path:
        try:
            return Path(path).read_text(encoding="utf-8").strip()
        except OSError as e:
            raise SystemExit(f"Cannot read {name}_FILE ({path}): {e.strerror}")
    return default


# Extra Host headers accepted (comma separated), e.g. "quest.example.com".
ALLOWED_HOSTS = {h.strip().lower() for h in os.environ.get("SKILLQUEST_ALLOWED_HOSTS", "").split(",") if h.strip()}
BASIC_AUTH = read_secret("SKILLQUEST_BASIC_AUTH")          # "user:password"
REQUEST_TIMEOUT = int(os.environ.get("SKILLQUEST_REQUEST_TIMEOUT", "30"))
TRUST_PROXY = _flag("SKILLQUEST_TRUST_PROXY")               # read client IP from X-Forwarded-For
ALLOW_NO_AUTH = _flag("SKILLQUEST_ALLOW_NO_AUTH")           # explicit opt-out for non-local binds
AUTH_MAX_FAILURES = int(os.environ.get("SKILLQUEST_AUTH_MAX_FAILURES", "10"))
AUTH_LOCKOUT_SECONDS = int(os.environ.get("SKILLQUEST_AUTH_LOCKOUT_SECONDS", "300"))


def check_basic_auth_format(value):
    """Returns a list of problems with a 'user:password' string (empty list = fine)."""
    problems = []
    user, sep, password = value.partition(":")
    if not sep or not user or not password:
        problems.append("must look like user:password")
        return problems
    if len(password) < MIN_PASSWORD_LENGTH:
        problems.append(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    if any(m in value.lower() for m in PLACEHOLDER_MARKERS):
        problems.append("still contains a placeholder from .env.example — generate a real secret")
    if any(ord(c) > 126 or ord(c) < 32 for c in value):
        problems.append("use printable ASCII characters only")
    return problems


def startup_problems(host, basic_auth=None, allow_no_auth=None):
    """(fatal, warnings) for the given bind address. Local binds stay frictionless; exposed binds are strict."""
    basic_auth = BASIC_AUTH if basic_auth is None else basic_auth
    allow_no_auth = ALLOW_NO_AUTH if allow_no_auth is None else allow_no_auth
    exposed = host.lower() not in LOOPBACK
    fatal, warnings = [], []
    if basic_auth:
        issues = check_basic_auth_format(basic_auth)
        (fatal if exposed or "user:password" in " ".join(issues) else warnings).extend(
            f"SKILLQUEST_BASIC_AUTH {i}" for i in issues)
    elif exposed and not allow_no_auth:
        fatal.append("Refusing to listen on a non-local address without authentication. Set SKILLQUEST_BASIC_AUTH "
                     "(or SKILLQUEST_BASIC_AUTH_FILE), or SKILLQUEST_ALLOW_NO_AUTH=1 if a trusted proxy already authenticates.")
    if exposed and not ALLOWED_HOSTS:
        warnings.append("SKILLQUEST_ALLOWED_HOSTS is empty: any Host header is accepted. Set it to your domain.")
    return fatal, warnings
