"""Integration tests: real HTTP server + temporary SQLite database."""
import http.client
import json
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from backend import clock
from backend.server import make_server


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = str(Path(cls.tmp.name) / "t.db")
        cls.srv = make_server("127.0.0.1", 0, cls.db, quiet=True)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.tmp.cleanup()

    def setUp(self):
        clock.set_today(None)
        self.call("POST", "/api/profile/reset", {"confirm": True})

    def call(self, method, path, body=None, raw=None):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                txt = r.read()
                return r.status, (json.loads(txt) if txt else None)
        except urllib.error.HTTPError as e:
            txt = e.read()
            return e.code, (json.loads(txt) if txt else None)

    def mk(self, **kw):
        body = {"title": "Task", "category": "programming", "difficulty": "medium"}
        body.update(kw)
        st, m = self.call("POST", "/api/missions", body)
        self.assertEqual(st, 201, m)
        return m

    # ---- CRUD & validation ----
    def test_crud(self):
        m = self.mk(title="  Learn SQL  ", xp=40, due_date="2030-01-01")
        self.assertEqual(m["title"], "Learn SQL")
        self.assertEqual(m["status"], "pending")
        st, upd = self.call("PUT", f"/api/missions/{m['id']}", {**m, "title": "Learn SQL 2", "xp": 60})
        self.assertEqual((st, upd["title"], upd["xp"]), (200, "Learn SQL 2", 60))
        st, lst = self.call("GET", "/api/missions")
        self.assertEqual(len(lst["items"]), 1)
        self.assertEqual(self.call("DELETE", f"/api/missions/{m['id']}")[0], 204)
        self.assertEqual(self.call("GET", f"/api/missions/{m['id']}")[0], 404)

    def test_default_xp_from_difficulty(self):
        self.assertEqual(self.mk(difficulty="hard")["xp"], 100)

    def test_validation(self):
        st, r = self.call("POST", "/api/missions", {"title": "", "category": "nope", "difficulty": "x",
                                                    "xp": 5000, "due_date": "2024-13-40"})
        self.assertEqual(st, 400)
        self.assertEqual(set(r["error"]["fields"]), {"title", "category", "difficulty", "xp", "due_date"})
        self.assertEqual(self.call("POST", "/api/missions", raw=b"{bad")[0], 400)
        self.assertEqual(self.call("POST", "/api/missions", [1, 2])[0], 400)
        self.assertEqual(self.call("POST", "/api/missions", {"title": "x" * 121, "category": "ai"})[0], 400)

    def test_errors(self):
        self.assertEqual(self.call("GET", "/api/nothing")[0], 404)
        self.assertEqual(self.call("PATCH", "/api/dashboard")[0], 405)
        self.assertEqual(self.call("POST", "/api/missions/999/complete")[0], 404)
        self.assertEqual(self.call("GET", "/api/missions?status=bogus")[0], 400)

    # ---- XP logic ----
    def test_complete_awards_xp_and_levels(self):
        m = self.mk(xp=120)
        st, r = self.call("POST", f"/api/missions/{m['id']}/complete")
        self.assertEqual(st, 200)
        self.assertEqual(r["reward"]["base_xp"], 120)
        self.assertEqual(r["level"]["after"], 2)  # 120 XP ≥ 100
        self.assertTrue(r["level"]["leveled_up"])
        codes = {a["code"] for a in r["new_achievements"]}
        self.assertIn("first_mission", codes)
        # 120 + 25 (first_mission) + 50 (skill_level_2, skill xp=120>=50)
        self.assertEqual(r["user"]["xp"], 120 + sum(a["reward_xp"] for a in r["new_achievements"]))
        self.assertEqual(self.call("POST", f"/api/missions/{m['id']}/complete")[0], 409)

    def test_reopen_removes_xp(self):
        m = self.mk(xp=30)
        self.call("POST", f"/api/missions/{m['id']}/complete")
        st, r = self.call("POST", f"/api/missions/{m['id']}/reopen")
        self.assertEqual(st, 200)
        self.assertEqual(r["mission"]["status"], "pending")
        mission_xp = [e for e in self.call("GET", "/api/xp-history")[1]["items"] if e["source"] == "mission"]
        self.assertEqual(mission_xp, [])
        self.assertEqual(self.call("POST", f"/api/missions/{m['id']}/reopen")[0], 409)

    def test_delete_completed_keeps_xp(self):
        m = self.mk(xp=30)
        self.call("POST", f"/api/missions/{m['id']}/complete")
        before = self.call("GET", "/api/dashboard")[1]["user"]["xp"]
        self.call("DELETE", f"/api/missions/{m['id']}")
        self.assertEqual(self.call("GET", "/api/dashboard")[1]["user"]["xp"], before)

    def test_streak_and_bonus(self):
        today = date.today()
        for i in range(7, 0, -1):  # 7 consecutive days ending today
            clock.set_today(today - timedelta(days=i - 1))
            m = self.mk(xp=100)
            st, r = self.call("POST", f"/api/missions/{m['id']}/complete")
            streak_day = 8 - i
            expected_bonus = {1: 0, 2: 0, 3: 5, 4: 5, 5: 5, 6: 5, 7: 10}[streak_day]
            self.assertEqual(r["reward"]["bonus_xp"], expected_bonus, f"day {streak_day}")
        self.assertEqual(r["streak"], 7)
        self.assertIn("streak_7", {a["code"] for a in self.call("GET", "/api/achievements")[1]["items"]
                                   if a["unlocked"]})
        clock.set_today(today)
        d = self.call("GET", "/api/dashboard")[1]
        self.assertEqual((d["streak"]["current"], d["streak"]["best"]), (7, 7))

    def test_streak_breaks(self):
        today = date.today()
        for off in (5, 4, 0):
            clock.set_today(today - timedelta(days=off))
            self.call("POST", f"/api/missions/{self.mk()['id']}/complete")
        clock.set_today(today)
        s = self.call("GET", "/api/dashboard")[1]["streak"]
        self.assertEqual((s["current"], s["best"]), (1, 2))

    def test_skills_levels(self):
        m = self.mk(category="fitness", xp=160)
        self.call("POST", f"/api/missions/{m['id']}/complete")
        skills = {s["slug"]: s for s in self.call("GET", "/api/skills")[1]["items"]}
        self.assertEqual(skills["fitness"]["level"], 3)  # 160 ≥ 150
        self.assertEqual(skills["programming"]["level"], 1)
        self.assertTrue(skills["fitness"]["tiers"][1]["unlocked"])

    def test_ten_missions_and_polymath(self):
        for cat in ["programming", "ai", "english", "fitness", "finance", "personal"] * 2:
            self.call("POST", f"/api/missions/{self.mk(category=cat, xp=10)['id']}/complete")
        unlocked = {a["code"] for a in self.call("GET", "/api/achievements")[1]["items"] if a["unlocked"]}
        self.assertTrue({"first_mission", "ten_missions", "polymath"} <= unlocked)

    def test_filters(self):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        a = self.mk(title="Alpha", due_date=yesterday)
        self.mk(title="Beta", category="ai")
        self.call("POST", f"/api/missions/{a['id']}/complete")
        b = self.call("GET", "/api/missions?status=active")[1]["items"]
        self.assertEqual([m["title"] for m in b], ["Beta"])
        self.assertEqual(len(self.call("GET", "/api/missions?status=completed")[1]["items"]), 1)
        self.assertEqual(len(self.call("GET", "/api/missions?category=ai")[1]["items"]), 1)
        self.assertEqual(len(self.call("GET", "/api/missions?q=alp")[1]["items"]), 1)
        self.assertEqual(len(self.call("GET", "/api/missions?q=%25")[1]["items"]), 0)
        self.mk(title="Late", due_date=yesterday)
        self.assertEqual([m["title"] for m in self.call("GET", "/api/missions?status=overdue")[1]["items"]], ["Late"])

    # ---- analytics / profile ----
    def test_analytics(self):
        self.call("POST", f"/api/missions/{self.mk(category='ai', xp=50)['id']}/complete")
        w = self.call("GET", "/api/analytics?range=week")[1]
        self.assertEqual(len(w["series"]), 7)
        self.assertEqual(w["totals"]["missions"], 1)
        self.assertEqual(len(self.call("GET", "/api/analytics?range=month")[1]["series"]), 30)
        ai = next(c for c in w["categories"] if c["slug"] == "ai")
        self.assertEqual(ai["xp"], 50)
        self.assertAlmostEqual(ai["share"], 1.0)
        self.assertEqual(self.call("GET", "/api/analytics?range=year")[0], 400)
        h = self.call("GET", "/api/xp-history?limit=1")[1]
        self.assertEqual(len(h["items"]), 1)
        self.assertTrue(h["has_more"])

    def test_profile(self):
        st, p = self.call("PUT", "/api/profile", {"name": "Neo", "avatar": "🦊", "avatar_hue": 200})
        self.assertEqual((st, p["user"]["name"], p["user"]["avatar"]), (200, "Neo", "🦊"))
        self.assertEqual(self.call("PUT", "/api/profile", {"name": " ", "avatar": "x"})[0], 400)
        self.assertEqual(self.call("PUT", "/api/profile", {"name": "A", "avatar": "x", "avatar_hue": 999})[0], 400)
        self.assertEqual(self.call("POST", "/api/profile/reset", {})[0], 400)

    # ---- regression tests from the technical audit ----
    def test_concurrent_complete_awards_xp_once(self):
        m = self.mk(xp=100)
        codes = []

        def go():
            codes.append(self.call("POST", f"/api/missions/{m['id']}/complete")[0])
        threads = [threading.Thread(target=go) for _ in range(16)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(codes.count(200), 1, codes)
        self.assertEqual(codes.count(409), 15, codes)
        events = [e for e in self.call("GET", "/api/xp-history?limit=100")[1]["items"] if e["source"] == "mission"]
        self.assertEqual(len(events), 1)

    def test_concurrent_complete_and_reopen_keep_ledger_consistent(self):
        m = self.mk(xp=40)

        def toggle(i):
            self.call("POST", f"/api/missions/{m['id']}/" + ("complete" if i % 2 == 0 else "reopen"))
        threads = [threading.Thread(target=toggle, args=(i,)) for i in range(20)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        status = self.call("GET", f"/api/missions/{m['id']}")[1]["status"]
        events = [e for e in self.call("GET", "/api/xp-history?limit=100")[1]["items"] if e["source"] == "mission"]
        self.assertEqual(len(events), 1 if status == "completed" else 0)

    def raw_request(self, method, path, headers=None, body=None):
        c = http.client.HTTPConnection("127.0.0.1", self.srv.server_address[1], timeout=5)
        c.putrequest(method, path, skip_host=True)
        for k, v in {"Host": "localhost", **(headers or {})}.items():
            c.putheader(k, v)
        data = body.encode() if isinstance(body, str) else body
        c.putheader("Content-Length", str(len(data or b"")))
        c.endheaders(data)
        r = c.getresponse()
        payload, hdrs = r.read(), dict(r.getheaders())
        c.close()
        return r.status, hdrs, payload

    def test_csrf_content_type_required(self):
        body = '{"title":"csrf","category":"ai"}'
        st, _, _ = self.raw_request("POST", "/api/missions", {"Content-Type": "text/plain"}, body)
        self.assertEqual(st, 415)
        st, _, _ = self.raw_request("POST", "/api/missions", {"Content-Type": "application/x-www-form-urlencoded"}, "title=x")
        self.assertEqual(st, 415)
        st, _, _ = self.raw_request("POST", "/api/missions/1/complete", {}, "")
        self.assertEqual(st, 415)
        st, _, _ = self.raw_request("POST", "/api/missions", {"Content-Type": "application/json; charset=utf-8"}, body)
        self.assertEqual(st, 201)
        self.assertEqual(self.call("GET", "/api/missions")[1]["items"][0]["title"], "csrf")

    def test_origin_and_host_checks(self):
        host = f"127.0.0.1:{self.srv.server_address[1]}"
        body = '{"title":"o","category":"ai"}'
        j = {"Content-Type": "application/json"}
        self.assertEqual(self.raw_request("POST", "/api/missions", {**j, "Host": host, "Origin": "https://evil.example"}, body)[0], 403)
        self.assertEqual(self.raw_request("POST", "/api/missions", {**j, "Host": host, "Origin": "null"}, body)[0], 403)
        self.assertEqual(self.raw_request("POST", "/api/missions", {**j, "Host": host, "Origin": f"http://{host}"}, body)[0], 201)
        self.assertEqual(self.raw_request("DELETE", "/api/missions/1", {"Host": host, "Origin": "https://evil.example"})[0], 403)
        # DNS rebinding: attacker-controlled name resolving to 127.0.0.1
        self.assertEqual(self.raw_request("GET", "/api/dashboard", {"Host": "evil.example.com"})[0], 403)
        self.assertEqual(self.raw_request("GET", "/", {"Host": "evil.example.com"})[0], 403)
        self.assertEqual(self.raw_request("GET", "/api/health", {"Host": "[::1]:8000"})[0], 200)

    def test_security_headers(self):
        st, h, _ = self.raw_request("GET", "/")
        h = {k.lower(): v for k, v in h.items()}
        self.assertIn("script-src 'self'", h["content-security-policy"])
        self.assertEqual(h["x-content-type-options"], "nosniff")
        self.assertEqual(h["x-frame-options"], "DENY")
        _, h, _ = self.raw_request("GET", "/api/health")
        self.assertIn("content-security-policy", {k.lower() for k in h})

    def test_huge_or_malformed_ids_are_404_not_500(self):
        self.assertEqual(self.call("GET", "/api/missions/99999999999999999999999")[0], 404)
        self.assertEqual(self.call("POST", "/api/missions/99999999999999999999999/complete")[0], 404)
        self.assertEqual(self.call("GET", "/api/missions/abc")[0], 404)
        self.assertEqual(self.call("GET", "/api/missions/-1")[0], 404)

    def test_chunked_and_bad_content_length_rejected(self):
        st, _, _ = self.raw_request("POST", "/api/missions", {"Content-Type": "application/json", "Transfer-Encoding": "chunked"}, "0\r\n\r\n")
        self.assertIn(st, (400, 411))
        st, _, _ = self.raw_request("POST", "/api/missions", {"Content-Type": "application/json", "Content-Length": "abc"}, "")
        self.assertEqual(st, 400)
        import socket
        sock = socket.create_connection(("127.0.0.1", self.srv.server_address[1]), timeout=5)
        sock.sendall(b"POST /api/missions HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\n"
                     b"Content-Length: 5000000\r\n\r\n")  # declared size only — server must refuse before reading
        self.assertIn(b" 413 ", sock.recv(200).split(b"\r\n")[0])
        sock.close()

    def test_completed_mission_financials_are_locked(self):
        m = self.mk(category="fitness", xp=50, difficulty="medium")
        self.call("POST", f"/api/missions/{m['id']}/complete")
        st, upd = self.call("PUT", f"/api/missions/{m['id']}", {"title": "Renamed", "category": "finance",
                                                                 "difficulty": "epic", "xp": 999})
        self.assertEqual(st, 200)
        self.assertEqual((upd["title"], upd["category"], upd["xp"], upd["difficulty"]), ("Renamed", "fitness", 50, "medium"))
        skills = {s["slug"]: s for s in self.call("GET", "/api/skills")[1]["items"]}
        self.assertEqual(skills["finance"]["xp"], 0)

    def test_control_characters_rejected(self):
        self.assertEqual(self.call("POST", "/api/missions", {"title": "a\x00b", "category": "ai"})[0], 400)
        self.assertEqual(self.call("POST", "/api/missions", {"title": "a\nb", "category": "ai"})[0], 400)
        self.assertEqual(self.call("POST", "/api/missions", {"title": "ok", "description": "l1\nl2", "category": "ai"})[0], 201)
        self.assertEqual(self.call("POST", "/api/missions", {"title": "日本語 🚀", "category": "ai"})[0], 201)

    def test_analytics_category_total_matches_segments(self):
        self.call("POST", f"/api/missions/{self.mk(category='ai', xp=50)['id']}/complete")  # also unlocks achievements
        a = self.call("GET", "/api/analytics?range=month")[1]
        self.assertGreater(a["totals"]["xp"], a["totals"]["category_xp"])  # achievement bonus is not a category
        self.assertEqual(a["totals"]["category_xp"], sum(c["xp"] for c in a["categories"]))

    def test_xp_conservation(self):
        """Total XP == sum of mission XP + achievement bonuses; skill XP == mission XP only."""
        for cat in ("ai", "fitness", "ai"):
            self.call("POST", f"/api/missions/{self.mk(category=cat, xp=70)['id']}/complete")
        hist = self.call("GET", "/api/xp-history?limit=100")[1]["items"]
        total = self.call("GET", "/api/dashboard")[1]["user"]["xp"]
        self.assertEqual(total, sum(e["amount"] for e in hist))
        skills = self.call("GET", "/api/skills")[1]["items"]
        self.assertEqual(sum(s["xp"] for s in skills), sum(e["amount"] for e in hist if e["source"] == "mission"))
        self.assertEqual(len({e["id"] for e in hist}), len(hist))

    def test_list_truncation_flag(self):
        self.assertFalse(self.call("GET", "/api/missions")[1]["truncated"])

    def test_schema_version_and_foreign_keys(self):
        con = sqlite3.connect(self.db)
        self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], 1)
        self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertEqual(con.execute("PRAGMA foreign_key_check").fetchall(), [])
        con.close()

    def test_data_persists_across_server_restart(self):
        m = self.mk(title="persist me", xp=30)
        self.call("POST", f"/api/missions/{m['id']}/complete")
        before = self.call("GET", "/api/dashboard")[1]["user"]["xp"]
        srv2 = make_server("127.0.0.1", 0, self.db, quiet=True)
        threading.Thread(target=srv2.serve_forever, daemon=True).start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{srv2.server_address[1]}/api/dashboard") as r:
                self.assertEqual(json.loads(r.read())["user"]["xp"], before)
        finally:
            srv2.shutdown()
            srv2.server_close()

    def test_static(self):
        with urllib.request.urlopen(self.base + "/") as r:
            self.assertEqual(r.status, 200)
        for bad in ("/../backend/config.py", "/%2e%2e/backend/config.py"):
            try:
                with urllib.request.urlopen(self.base + bad) as r:
                    self.assertNotIn(b"MAX_BODY_BYTES", r.read())
            except urllib.error.HTTPError:
                pass


class LevelMathTest(unittest.TestCase):
    def test_boundaries_and_bruteforce(self):
        from backend import xp
        for xp_val, level in ((0, 1), (99, 1), (100, 2), (299, 2), (300, 3), (599, 3), (600, 4), (999, 4), (1000, 5), (4500, 10)):
            self.assertEqual(xp.level_info(xp_val)["level"], level, xp_val)
        for kind, thr in (("user", xp.user_xp_for_level), ("skill", xp.skill_xp_for_level)):
            for v in list(range(0, 5000)) + [10 ** 6, 10 ** 8]:
                info = xp.level_info(v, kind)
                if info["level"] < xp.MAX_SKILL_LEVEL or kind == "user":
                    self.assertTrue(thr(info["level"]) <= v < thr(info["level"] + 1), (kind, v))
                self.assertTrue(0 <= info["progress"] <= 1)
        self.assertTrue(xp.level_info(10 ** 9, "skill")["maxed"])

    def test_streak_bonus_table(self):
        from backend import xp
        self.assertEqual([xp.streak_bonus(100, d) for d in (1, 2, 3, 6, 7, 13, 14, 29, 30, 99)], [0, 0, 5, 5, 10, 10, 15, 15, 20, 20])


class DeploymentSecurityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.srv = make_server("127.0.0.1", 0, str(Path(self.tmp.name) / "d.db"), quiet=True,
                               basic_auth="me:s3cret", allowed_hosts=["quest.example.com"])
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.tmp.cleanup()

    def get(self, path, host="quest.example.com", auth=None):
        import base64
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        h = {"Host": host}
        if auth:
            h["Authorization"] = "Basic " + base64.b64encode(auth.encode()).decode()
        c.request("GET", path, headers=h)
        r = c.getresponse()
        r.read()
        c.close()
        return r.status, r.getheader("WWW-Authenticate")

    def test_basic_auth_and_hosts(self):
        self.assertEqual(self.get("/api/dashboard")[0], 401)
        self.assertEqual(self.get("/api/dashboard")[1], 'Basic realm="SkillQuest"')
        self.assertEqual(self.get("/api/dashboard", auth="me:wrong")[0], 401)
        self.assertEqual(self.get("/api/dashboard", auth="me:s3cret")[0], 200)
        self.assertEqual(self.get("/", auth="me:s3cret")[0], 200)
        self.assertEqual(self.get("/", auth=None)[0], 401)
        self.assertEqual(self.get("/api/health")[0], 200)  # health check stays open
        self.assertEqual(self.get("/api/dashboard", host="evil.example.com", auth="me:s3cret")[0], 403)


if __name__ == "__main__":
    unittest.main()
