"""Production-readiness tests: secrets, startup validation, auth lockout, backups, persistence, config files."""
import base64
import contextlib
import io
import json
import os
import re
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

from backend import backup, config, db, restore
from backend.server import AuthThrottle, make_server

ROOT = Path(__file__).resolve().parent.parent
GOOD_AUTH = "owner:Zq8-longRandomPassw0rd"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def basic(creds):
    return {"Authorization": "Basic " + base64.b64encode(creds.encode()).decode()}


def http(method, url, headers=None, body=None):
    h = dict(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, method=method, headers=h), timeout=5) as r:
            t = r.read()
            return r.status, (json.loads(t) if t and r.headers.get_content_type() == "application/json" else t), r.headers
    except urllib.error.HTTPError as e:
        t = e.read()
        e.close()
        try:
            return e.code, json.loads(t), e.headers
        except ValueError:
            return e.code, t, e.headers


class SecretsTest(unittest.TestCase):
    def test_env_value_and_file_value(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d, "s")
            f.write_text("  from-file:value  \n")
            with mock.patch.dict(os.environ, {"X_SECRET_FILE": str(f)}, clear=False):
                os.environ.pop("X_SECRET", None)
                self.assertEqual(config.read_secret("X_SECRET"), "from-file:value")  # whitespace stripped
                with mock.patch.dict(os.environ, {"X_SECRET": "direct:value"}):
                    self.assertEqual(config.read_secret("X_SECRET"), "direct:value")  # env wins
            with mock.patch.dict(os.environ, {"Y_SECRET_FILE": str(Path(d, "missing"))}):
                with self.assertRaises(SystemExit):
                    config.read_secret("Y_SECRET")
            self.assertEqual(config.read_secret("NOPE_NOT_SET", "dflt"), "dflt")

    def test_auth_format_rules(self):
        ok = config.check_basic_auth_format
        self.assertEqual(ok(GOOD_AUTH), [])
        self.assertTrue(ok("nocolon"))
        self.assertTrue(ok(":nouser1234567"))
        self.assertTrue(ok("user:"))
        self.assertTrue(any("12" in p for p in ok("me:short")))
        self.assertTrue(any("placeholder" in p for p in ok("CHANGE_ME_user:CHANGE_ME_generate_a_long_random_password")))
        self.assertTrue(any("ASCII" in p for p in ok("me:пароль-длинный-очень")))

    def test_startup_rules(self):
        sp = config.startup_problems
        with mock.patch.object(config, "ALLOWED_HOSTS", {"quest.example.com"}):
            self.assertEqual(sp("127.0.0.1", basic_auth="", allow_no_auth=False), ([], []))      # local: frictionless
            fatal, _ = sp("0.0.0.0", basic_auth="", allow_no_auth=False)
            self.assertTrue(fatal and "without authentication" in fatal[0])                        # exposed: needs auth
            self.assertEqual(sp("0.0.0.0", basic_auth="", allow_no_auth=True)[0], [])              # explicit opt-out
            self.assertEqual(sp("0.0.0.0", basic_auth=GOOD_AUTH, allow_no_auth=False), ([], []))
            self.assertTrue(sp("0.0.0.0", basic_auth="me:short", allow_no_auth=False)[0])          # weak → fatal when exposed
            weak_local = sp("127.0.0.1", basic_auth="me:short", allow_no_auth=False)
            self.assertEqual(weak_local[0], [])                                                    # weak → warning when local
            self.assertTrue(weak_local[1])
            self.assertTrue(sp("127.0.0.1", basic_auth="malformed", allow_no_auth=False)[0])       # unusable value is always fatal
        with mock.patch.object(config, "ALLOWED_HOSTS", set()):
            self.assertTrue(any("ALLOWED_HOSTS" in w for w in sp("0.0.0.0", basic_auth=GOOD_AUTH)[1]))


class RunPyProcessTest(unittest.TestCase):
    """Real `python run.py` subprocesses — the same entry point the container uses."""

    def start(self, extra_env=None, host="127.0.0.1", db_path=None):
        self.port = free_port()
        env = {k: v for k, v in os.environ.items() if not k.startswith("SKILLQUEST_")}
        env.update(extra_env or {})
        env["SKILLQUEST_DB"] = db_path or str(Path(self.tmp.name, "app.db"))
        return subprocess.Popen([sys.executable, "run.py", "--host", host, "--port", str(self.port), "--quiet"],
                                cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def wait_ready(self, proc):
        for _ in range(80):
            if proc.poll() is not None:
                self.fail("server exited early: " + proc.stderr.read())
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/health", timeout=1).read()
                return
            except OSError:
                time.sleep(0.1)
        self.fail("server did not become ready")

    def stop(self, proc):
        proc.send_signal(signal.SIGTERM)
        out, err = proc.communicate(timeout=10)
        return proc.returncode, out, err

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_exposed_without_auth_refuses_to_start(self):
        p = self.start(host="0.0.0.0")
        _, err = p.communicate(timeout=10)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("without authentication", err)

    def test_placeholder_secret_refuses_to_start(self):
        p = self.start({"SKILLQUEST_BASIC_AUTH": "CHANGE_ME_user:CHANGE_ME_generate_a_long_random_password"}, host="0.0.0.0")
        _, err = p.communicate(timeout=10)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("placeholder", err)
        self.assertNotIn("CHANGE_ME_generate", err.split("placeholder")[0].split("Configuration error")[0])

    def test_secret_from_file_and_clean_sigterm(self):
        f = Path(self.tmp.name, "auth.txt")
        f.write_text(GOOD_AUTH + "\n")
        p = self.start({"SKILLQUEST_BASIC_AUTH_FILE": str(f), "SKILLQUEST_ALLOWED_HOSTS": "quest.example.com"}, host="0.0.0.0")
        self.wait_ready(p)
        base = f"http://127.0.0.1:{self.port}"
        self.assertEqual(http("GET", base + "/api/dashboard")[0], 401)
        self.assertEqual(http("GET", base + "/api/dashboard", basic("owner:wrong-password-xx"))[0], 401)
        self.assertEqual(http("GET", base + "/api/dashboard", basic(GOOD_AUTH))[0], 200)
        self.assertEqual(http("GET", base + "/api/health")[0], 200)  # healthcheck: no auth, and loopback Host still allowed
        code, out, err = self.stop(p)
        self.assertEqual(code, 0, err)
        self.assertIn("Stopped", out)
        self.assertNotIn(GOOD_AUTH, out + err)  # the secret is never printed

    def test_data_survives_process_recreation(self):
        """Simulates `docker compose up --force-recreate`: new process, same /data volume. (Not a Docker run.)"""
        env = {"SKILLQUEST_BASIC_AUTH": GOOD_AUTH, "SKILLQUEST_ALLOWED_HOSTS": "quest.example.com"}
        p1 = self.start(env, host="0.0.0.0")
        self.wait_ready(p1)
        base = f"http://127.0.0.1:{self.port}"
        auth = basic(GOOD_AUTH)
        _, m, _ = http("POST", base + "/api/missions", auth, {"title": "Survive the restart", "category": "ai", "xp": 120})
        st, res, _ = http("POST", f"{base}/api/missions/{m['id']}/complete", auth, {})
        self.assertEqual(st, 200)
        xp_before = http("GET", base + "/api/dashboard", auth)[1]["user"]["xp"]
        http("PUT", base + "/api/profile", auth, {"name": "Persisted Name", "avatar": "🦊", "avatar_hue": 120})
        self.assertEqual(self.stop(p1)[0], 0)
        # brand-new process, nothing carried over except the data directory
        p2 = self.start(env, host="0.0.0.0")
        self.wait_ready(p2)
        base = f"http://127.0.0.1:{self.port}"
        dash = http("GET", base + "/api/dashboard", auth)[1]
        self.assertEqual(dash["user"]["xp"], xp_before)
        self.assertEqual(dash["user"]["name"], "Persisted Name")
        titles = [x["title"] for x in http("GET", base + "/api/missions?status=completed", auth)[1]["items"]]
        self.assertEqual(titles, ["Survive the restart"])
        self.assertEqual(http("GET", base + "/api/achievements", auth)[1]["unlocked"], len(res["new_achievements"]))
        self.assertEqual(self.stop(p2)[0], 0)
        self.assertEqual(sqlite3.connect(Path(self.tmp.name, "app.db")).execute("PRAGMA integrity_check").fetchone()[0], "ok")


class AuthLockoutTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.srv = make_server("127.0.0.1", 0, str(Path(self.tmp.name, "a.db")), quiet=True,
                               basic_auth=GOOD_AUTH, trust_proxy=True, max_auth_failures=3, lockout_seconds=60)
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.tmp.cleanup()

    def test_lockout_after_repeated_failures(self):
        bad = {**basic("owner:wrong-guess-number"), "X-Forwarded-For": "203.0.113.7"}
        good = {**basic(GOOD_AUTH), "X-Forwarded-For": "203.0.113.7"}
        for _ in range(3):
            self.assertEqual(http("GET", self.base + "/api/dashboard", bad)[0], 401)
        st, body, hdr = http("GET", self.base + "/api/dashboard", good)  # even the right password is refused while locked
        self.assertEqual(st, 429)
        self.assertTrue(0 < int(hdr["Retry-After"]) <= 60)
        # a different client is unaffected
        other = {**basic(GOOD_AUTH), "X-Forwarded-For": "198.51.100.9"}
        self.assertEqual(http("GET", self.base + "/api/dashboard", other)[0], 200)
        # health check is never locked out
        self.assertEqual(http("GET", self.base + "/api/health", bad)[0], 200)

    def test_bare_requests_and_success_do_not_count(self):
        h = {"X-Forwarded-For": "203.0.113.50"}
        for _ in range(10):  # browser's initial credential-less request
            self.assertEqual(http("GET", self.base + "/api/dashboard", h)[0], 401)
        self.assertEqual(http("GET", self.base + "/api/dashboard", {**h, **basic(GOOD_AUTH)})[0], 200)
        bad = {**h, **basic("owner:wrong-guess-number")}
        http("GET", self.base + "/api/dashboard", bad)
        http("GET", self.base + "/api/dashboard", bad)
        self.assertEqual(http("GET", self.base + "/api/dashboard", {**h, **basic(GOOD_AUTH)})[0], 200)  # success resets
        for _ in range(2):
            http("GET", self.base + "/api/dashboard", bad)
        self.assertEqual(http("GET", self.base + "/api/dashboard", {**h, **basic(GOOD_AUTH)})[0], 200)

    def test_throttle_unit(self):
        t = AuthThrottle(2, 10)
        t.failed("ip", now=100)
        self.assertEqual(t.retry_after("ip", now=101), 0)
        t.failed("ip", now=102)
        self.assertEqual(t.retry_after("ip", now=103), 7)   # window ends 10 s after the first failure (t=100)
        self.assertEqual(t.retry_after("ip", now=111), 0)   # window passed
        t.failed("ip", now=112); t.failed("ip", now=113)
        t.succeeded("ip")
        self.assertEqual(t.retry_after("ip", now=114), 0)

    def test_without_trust_proxy_forwarded_header_is_ignored(self):
        srv = make_server("127.0.0.1", 0, str(Path(self.tmp.name, "b.db")), quiet=True, basic_auth=GOOD_AUTH,
                          trust_proxy=False, max_auth_failures=2, lockout_seconds=60)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        try:
            for i in range(2):  # attacker rotates a spoofed XFF to dodge the lockout — must not work
                http("GET", base + "/api/dashboard", {**basic("owner:wrong-guess-number"), "X-Forwarded-For": f"10.0.0.{i}"})
            self.assertEqual(http("GET", base + "/api/dashboard", {**basic(GOOD_AUTH), "X-Forwarded-For": "10.9.9.9"})[0], 429)
        finally:
            srv.shutdown()
            srv.server_close()

    def test_secret_never_logged_or_echoed(self):
        srv = make_server("127.0.0.1", 0, str(Path(self.tmp.name, "c.db")), quiet=False, basic_auth=GOOD_AUTH)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        buf = io.StringIO()
        try:
            with contextlib.redirect_stderr(buf):
                _, body, hdr = http("GET", base + "/api/dashboard", basic(GOOD_AUTH))
                _, ebody, ehdr = http("GET", base + "/api/dashboard", basic("owner:wrong-guess-number"))
            blob = buf.getvalue() + json.dumps(body) + json.dumps(ebody) + str(hdr) + str(ehdr)
            self.assertNotIn("Zq8-longRandomPassw0rd", blob)
            self.assertNotIn(base64.b64encode(GOOD_AUTH.encode()).decode(), blob)
        finally:
            srv.shutdown()
            srv.server_close()

    def test_loopback_host_allowed_when_domain_configured(self):
        with mock.patch.object(config, "ALLOWED_HOSTS", {"quest.example.com"}):
            srv = make_server("0.0.0.0", 0, str(Path(self.tmp.name, "d.db")), quiet=True, basic_auth=GOOD_AUTH)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        port = srv.server_address[1]
        try:
            for host, expected in (("127.0.0.1:%d" % port, 200), ("localhost", 200), ("quest.example.com", 200), ("evil.example", 403)):
                req = urllib.request.Request(f"http://127.0.0.1:{port}/api/health", headers={"Host": host})
                try:
                    code = urllib.request.urlopen(req).status
                except urllib.error.HTTPError as e:
                    code = e.code
                self.assertEqual(code, expected, host)
        finally:
            srv.shutdown()
            srv.server_close()


class BackupRestoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.db = str(self.d / "live.db")
        db.init_db(self.db)
        con = db.connect(self.db)
        con.execute("INSERT INTO missions(title,category,difficulty,xp,status,created_at,updated_at) "
                    "VALUES('seed mission','ai','easy',20,'pending','2026-01-01 00:00:00','2026-01-01 00:00:00')")
        con.commit()
        con.close()

    def tearDown(self):
        self.tmp.cleanup()

    def count(self, path):
        c = sqlite3.connect(path)
        try:
            return c.execute("SELECT COUNT(*) FROM missions").fetchone()[0]
        finally:
            c.close()

    def test_backup_is_verified_private_single_file(self):
        path, info, _ = backup.make_backup(self.db, self.d / "bk")
        self.assertEqual(info["missions"], 1)
        self.assertEqual(oct(path.stat().st_mode & 0o777), "0o600")
        self.assertEqual(oct((self.d / "bk").stat().st_mode & 0o777), "0o700")
        self.assertEqual([p.name for p in (self.d / "bk").iterdir()], [path.name])  # no .partial / -wal / -shm leftovers
        self.assertEqual(self.count(str(path)), 1)

    def test_backup_while_writes_are_happening(self):
        stop = threading.Event()
        written = []

        def writer():
            con = db.connect(self.db)
            i = 0
            while not stop.is_set():
                i += 1
                con.execute("INSERT INTO missions(title,category,difficulty,xp,status,created_at,updated_at) "
                            "VALUES(?,'ai','easy',20,'pending','2026-01-01 00:00:00','2026-01-01 00:00:00')", (f"w{i}",))
                con.commit()
                written.append(i)
            con.close()
        t = threading.Thread(target=writer)
        t.start()
        try:
            time.sleep(0.2)
            for _ in range(5):
                path, info, _ = backup.make_backup(self.db, self.d / "bk", keep=50)
                self.assertGreaterEqual(info["missions"], 1)  # verify() already ran integrity_check on each
        finally:
            stop.set()
            t.join()
        self.assertGreater(len(written), 5)

    def test_rotation_keeps_newest_and_ignores_foreign_files(self):
        from datetime import datetime, timedelta
        out = self.d / "bk"
        out.mkdir()
        (out / "notes.txt").write_text("keep me")
        (out / "other.db").write_text("not ours")
        base = datetime(2026, 1, 1)
        for i in range(6):
            backup.make_backup(self.db, out, keep=3, now=base + timedelta(minutes=i))
        names = sorted(p.name for p in out.iterdir())
        self.assertEqual(names, ["notes.txt", "other.db", "skillquest-20260101-000300.db", "skillquest-20260101-000400.db", "skillquest-20260101-000500.db"])

    def test_same_second_backups_do_not_overwrite(self):
        from datetime import datetime
        now = datetime(2026, 5, 5, 5, 5, 5)
        a, _, _ = backup.make_backup(self.db, self.d / "bk", now=now)
        b, _, _ = backup.make_backup(self.db, self.d / "bk", now=now)
        self.assertNotEqual(a, b)

    def test_missing_db_and_cli_exit_codes(self):
        with self.assertRaises(FileNotFoundError):
            backup.make_backup(str(self.d / "nope.db"), self.d / "bk")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(backup.main(["--db", str(self.d / "nope.db"), "--dir", str(self.d / "bk")]), 1)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(backup.main(["--db", self.db, "--dir", str(self.d / "bk")]), 0)

    def test_restore_roundtrip_keeps_safety_copy_and_drops_stale_wal(self):
        path, _, _ = backup.make_backup(self.db, self.d / "bk")
        con = db.connect(self.db)  # "disaster": data changes/destroyed after the backup
        con.execute("DELETE FROM missions")
        con.commit()
        con.close()
        Path(self.db + "-wal").write_bytes(b"stale wal garbage")
        Path(self.db + "-shm").write_bytes(b"stale shm garbage")
        info, saved = restore.restore(str(path), self.db)
        self.assertEqual(info["missions"], 1)
        self.assertEqual(self.count(self.db), 1)                 # data is back
        self.assertEqual(self.count(str(saved)), 0)              # the pre-restore state is preserved, not destroyed
        self.assertFalse(Path(self.db + "-wal").exists() and Path(self.db + "-wal").read_bytes() == b"stale wal garbage")
        db.init_db(self.db)                                      # app starts on it and keeps working
        self.assertEqual(self.count(self.db), 1)

    def test_restore_rejects_bad_files_and_changes_nothing(self):
        before = Path(self.db).read_bytes()
        junk = self.d / "junk.db"
        junk.write_bytes(b"this is not sqlite at all" * 100)
        foreign = self.d / "foreign.db"
        c = sqlite3.connect(foreign)
        c.execute("CREATE TABLE other(x)")
        c.commit()
        c.close()
        good, _, _ = backup.make_backup(self.db, self.d / "bk")
        truncated = self.d / "trunc.db"
        truncated.write_bytes(good.read_bytes()[:5000])
        for bad in (junk, foreign, truncated, self.d / "missing.db"):
            with self.assertRaises((ValueError, OSError)):
                restore.restore(str(bad), self.db)
        self.assertEqual(Path(self.db).read_bytes(), before)
        self.assertEqual([p.name for p in self.d.iterdir() if "before-restore" in p.name or p.name.endswith(".restoring")], [])

    def test_restore_cli_requires_confirmation(self):
        path, _, _ = backup.make_backup(self.db, self.d / "bk")
        with self.assertRaises(SystemExit) as cm, contextlib.redirect_stdout(io.StringIO()):
            restore.main([str(path), "--db", self.db])
        self.assertIn("Dry run", str(cm.exception))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(restore.main([str(path), "--db", self.db, "--yes"]), 0)


class DeploymentFilesTest(unittest.TestCase):
    def read(self, name):
        return (ROOT / name).read_text()

    def test_env_example_has_only_placeholders(self):
        text = self.read(".env.example")
        value = re.search(r"^SKILLQUEST_BASIC_AUTH=(.+)$", text, re.M).group(1)
        self.assertTrue(config.check_basic_auth_format(value), "placeholder must be rejected by the app")
        for line in text.splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                self.assertFalse(re.search(r"(?i)(token|secret|key)", k), k)
        self.assertNotRegex(text, r"[A-Za-z0-9+/]{32,}")  # no long random-looking strings

    def test_secrets_are_ignored_by_git_and_docker(self):
        gi, di = self.read(".gitignore").split(), self.read(".dockerignore").split()
        for entry in (".env", "secrets/", "backups/"):
            self.assertIn(entry, gi)
            self.assertIn(entry, di)
        self.assertIn("!.env.example", gi)

    def test_no_secrets_baked_into_image_or_compose(self):
        dockerfile, compose = self.read("Dockerfile"), self.read("docker-compose.yml")
        self.assertNotRegex(dockerfile, r"(?i)BASIC_AUTH|PASSWORD|SECRET")
        self.assertNotRegex(compose, r"(?m)^\s*SKILLQUEST_BASIC_AUTH:\s*[^$\s]")  # only ${...} references, never a literal
        self.assertIn("${SKILLQUEST_BASIC_AUTH:?", compose)             # required: compose fails fast if unset
        self.assertNotIn(GOOD_AUTH, compose)

    def test_only_the_proxy_publishes_ports(self):
        compose = self.read("docker-compose.yml")
        self.assertEqual(compose.count("ports:"), 1)
        app_block = compose.split("  backup:")[0]
        self.assertNotIn("ports:", app_block)
        self.assertIn("expose:", app_block)

    def test_container_hardening_present(self):
        compose, dockerfile = self.read("docker-compose.yml"), self.read("Dockerfile")
        for needle in ("read_only: true", "cap_drop: [ALL]", "no-new-privileges:true", "skillquest-data:/data",
                       "restart: unless-stopped", "SKILLQUEST_TRUST_PROXY"):
            self.assertIn(needle, compose, needle)
        self.assertRegex(dockerfile, r"(?m)^USER skillquest")
        self.assertIn("HEALTHCHECK", dockerfile)

    def test_proxy_configs_overwrite_forwarded_for_and_use_tls(self):
        caddy, nginx = self.read("deploy/Caddyfile"), self.read("deploy/nginx.conf")
        self.assertIn("header_up X-Forwarded-For {remote_host}", caddy)
        self.assertIn("Strict-Transport-Security", caddy)
        self.assertIn("proxy_set_header X-Forwarded-For   $remote_addr;", nginx)
        self.assertNotIn("$proxy_add_x_forwarded_for", nginx)
        self.assertIn("return 301 https://", nginx)
        self.assertIn("ssl_protocols TLSv1.2 TLSv1.3", nginx)

    def test_yaml_is_syntactically_valid_if_ruby_is_available(self):
        import shutil
        if not shutil.which("ruby"):
            self.skipTest("ruby not available for YAML parsing")
        r = subprocess.run(["ruby", "-ryaml", "-e", "YAML.load_file('docker-compose.yml'); puts :ok"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "ok", r.stderr)


if __name__ == "__main__":
    unittest.main()
