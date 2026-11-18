"""Restore the SkillQuest database from a backup.

    python3 -m backend.restore backups/skillquest-20261118-030000.db --yes

STOP THE SERVER FIRST. The restore:
  1. verifies the backup (integrity check, expected tables) — a bad file is rejected, nothing is touched;
  2. saves the current database next to it as <db>.before-restore-<timestamp> (never silently destroyed);
  3. replaces the database atomically and removes stale -wal/-shm files.
"""
import argparse
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

from . import config
from .backup import snapshot, verify


def restore(backup_path, db_path=None):
    db_path = db_path or config.DB_PATH
    info = verify(backup_path)  # raises ValueError for corrupt / foreign files
    db = Path(db_path)
    db.parent.mkdir(parents=True, exist_ok=True)
    saved = None
    if db.exists():
        saved = db.with_name(f"{db.name}.before-restore-{datetime.now():%Y%m%d-%H%M%S}")
        snapshot(str(db), str(saved))  # online-safe copy incl. WAL contents
        os.chmod(saved, 0o600)
    tmp = db.with_name(db.name + ".restoring")
    try:
        shutil.copyfile(backup_path, tmp)
        os.chmod(tmp, 0o600)
        verify(str(tmp))
        for suffix in ("-wal", "-shm"):  # stale WAL from the old DB would corrupt the restored one
            Path(str(db) + suffix).unlink(missing_ok=True)
        os.replace(tmp, db)
    finally:
        if tmp.exists():
            tmp.unlink()
    return info, saved


def main(argv=None):
    ap = argparse.ArgumentParser(description="Restore the SkillQuest database from a backup file.")
    ap.add_argument("backup")
    ap.add_argument("--db", default=config.DB_PATH)
    ap.add_argument("--yes", action="store_true", help="confirm that the server is stopped and the data may be replaced")
    args = ap.parse_args(argv)
    try:
        info = verify(args.backup)
    except (ValueError, OSError) as e:
        sys.exit(f"Refusing to restore: {args.backup}: {e}")
    print(f"Backup OK: {info['missions']} missions, {info['xp']} XP.")
    if not args.yes:
        sys.exit(f"Dry run only. Stop the server, then re-run with --yes to replace {args.db}.")
    _, saved = restore(args.backup, args.db)
    print(f"Restored {args.db}." + (f" Previous database kept as {saved}." if saved else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
