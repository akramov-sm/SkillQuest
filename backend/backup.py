"""SQLite backups.

    python3 -m backend.backup                       # one backup into ./backups, keep the newest 14
    python3 -m backend.backup --dir /b --keep 30
    python3 -m backend.backup --loop 86400          # daemon mode: a backup every 24 h (used by docker-compose)

Uses SQLite's online backup API, so it is consistent and safe while the server is running
(including WAL contents). Every backup is integrity-checked before it replaces a temporary
file, and only then given its final name — a half-written backup never looks valid.
"""
import argparse
import os
import re
import signal
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

from . import config

PREFIX = "skillquest-"
NAME_RE = re.compile(r"^skillquest-\d{8}-\d{6}(-\d+)?\.db$")
REQUIRED_TABLES = {"users", "skills", "missions", "xp_events", "user_achievements"}


def verify(path):
    """Raise ValueError unless `path` is a healthy SkillQuest database. Returns a summary dict."""
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as e:
        raise ValueError(f"cannot open: {e}")
    try:
        try:
            if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("integrity_check failed")
            if con.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("foreign_key_check failed")
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not REQUIRED_TABLES <= tables:
                raise ValueError("not a SkillQuest database (missing tables: %s)" % ", ".join(sorted(REQUIRED_TABLES - tables)))
            return {
                "missions": con.execute("SELECT COUNT(*) FROM missions").fetchone()[0],
                "xp": con.execute("SELECT COALESCE(SUM(amount),0) FROM xp_events").fetchone()[0],
                "schema_version": con.execute("PRAGMA user_version").fetchone()[0],
            }
        except sqlite3.DatabaseError as e:
            raise ValueError(f"not a valid SQLite database: {e}")
    finally:
        con.close()


def snapshot(src, dest):
    """Consistent copy of `src` into the new file `dest` (online backup API)."""
    s = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    d = sqlite3.connect(dest)
    try:
        s.backup(d)
        d.execute("PRAGMA journal_mode = DELETE")  # one self-contained file, no -wal/-shm sidecars
    finally:
        d.close()
        s.close()


def make_backup(db_path=None, backup_dir="backups", keep=14, now=None):
    db_path = db_path or config.DB_PATH
    if not os.path.isfile(db_path):
        raise FileNotFoundError(f"database not found: {db_path}")
    out_dir = Path(backup_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(out_dir, 0o700)
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    final = out_dir / f"{PREFIX}{stamp}.db"
    n = 1
    while final.exists():  # two backups within one second
        final = out_dir / f"{PREFIX}{stamp}-{n}.db"
        n += 1
    tmp = out_dir / (final.name + ".partial")
    try:
        snapshot(db_path, str(tmp))
        info = verify(str(tmp))
        os.chmod(tmp, 0o600)
        os.replace(tmp, final)
    finally:
        if tmp.exists():
            tmp.unlink()
    removed = prune(out_dir, keep)
    return final, info, removed


def list_backups(backup_dir):
    p = Path(backup_dir)
    return sorted((f for f in p.iterdir() if NAME_RE.match(f.name)), key=lambda f: f.name) if p.is_dir() else []


def prune(backup_dir, keep):
    """Delete all but the newest `keep` backups (only files matching our naming scheme)."""
    if keep < 1:
        return []
    old = list_backups(backup_dir)[:-keep]
    for f in old:
        f.unlink()
    return old


def main(argv=None):
    ap = argparse.ArgumentParser(description="Back up the SkillQuest SQLite database.")
    ap.add_argument("--db", default=config.DB_PATH)
    ap.add_argument("--dir", default=os.environ.get("SKILLQUEST_BACKUP_DIR", "backups"))
    ap.add_argument("--keep", type=int, default=int(os.environ.get("SKILLQUEST_BACKUP_KEEP", "14")))
    ap.add_argument("--loop", type=int, default=0, metavar="SECONDS", help="repeat every N seconds")
    args = ap.parse_args(argv)
    if args.keep < 1:
        sys.exit("--keep must be at least 1")

    stop = []
    signal.signal(signal.SIGTERM, lambda *_: stop.append(1))
    while True:
        try:
            path, info, removed = make_backup(args.db, args.dir, args.keep)
            print(f"{datetime.now():%Y-%m-%d %H:%M:%S} backup ok: {path} "
                  f"({info['missions']} missions, {info['xp']} XP); pruned {len(removed)}", flush=True)
        except (OSError, ValueError, sqlite3.Error) as e:
            print(f"backup FAILED: {e}", file=sys.stderr, flush=True)
            if not args.loop:
                return 1
        if not args.loop:
            return 0
        for _ in range(args.loop):  # sleep in 1 s steps so SIGTERM stops us promptly
            if stop:
                return 0
            time.sleep(1)
        if stop:
            return 0


if __name__ == "__main__":
    sys.exit(main())
