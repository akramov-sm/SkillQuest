"""SQLite access: connection factory, schema, seed data."""
import os
import sqlite3
from contextlib import contextmanager

from . import clock, config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT NOT NULL,
    avatar TEXT NOT NULL DEFAULT '🚀',
    avatar_hue INTEGER NOT NULL DEFAULT 265,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS skills (
    slug TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    icon TEXT NOT NULL,
    color TEXT NOT NULL,
    sort_order INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS missions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL REFERENCES skills(slug),
    difficulty TEXT NOT NULL CHECK (difficulty IN ('easy','medium','hard','epic')),
    xp INTEGER NOT NULL CHECK (xp BETWEEN 1 AND 1000),
    due_date TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','completed')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_missions_status ON missions(status);
CREATE INDEX IF NOT EXISTS idx_missions_due ON missions(due_date);
CREATE TABLE IF NOT EXISTS xp_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id INTEGER REFERENCES missions(id) ON DELETE SET NULL,
    skill_slug TEXT REFERENCES skills(slug),
    source TEXT NOT NULL CHECK (source IN ('mission','achievement')),
    label TEXT NOT NULL,
    difficulty TEXT,
    base_xp INTEGER NOT NULL,
    bonus_xp INTEGER NOT NULL DEFAULT 0,
    amount INTEGER NOT NULL,
    day TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_day ON xp_events(day);
CREATE INDEX IF NOT EXISTS idx_events_skill ON xp_events(skill_slug);
CREATE TABLE IF NOT EXISTS user_achievements (
    code TEXT PRIMARY KEY,
    unlocked_at TEXT NOT NULL
);
"""

SKILLS = [
    ("programming", "Programming", "Write code, build projects, ship features.", "code", "#8b5cf6"),
    ("ai", "Artificial Intelligence", "Machine learning, LLMs and data science.", "cpu", "#3b82f6"),
    ("english", "English", "Speaking, reading, listening and writing.", "languages", "#22d3ee"),
    ("fitness", "Fitness", "Workouts, sport, sleep and health habits.", "dumbbell", "#34d399"),
    ("finance", "Finance", "Budgeting, saving, investing knowledge.", "wallet", "#fbbf24"),
    ("personal", "Personal Development", "Reading, mindset, productivity and habits.", "sparkles", "#f472b6"),
]


SCHEMA_VERSION = 1


def connect(path=None):
    conn = sqlite3.connect(path or config.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def transaction(conn):
    """Write transaction. BEGIN IMMEDIATE takes the write lock *before* any read inside the
    block, so check-then-write sequences (e.g. 'is the mission still pending?') are race-free.
    Commits on success, rolls back on any exception."""
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise


def init_db(path=None):
    path = path or config.DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = connect(path)
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
        if conn.execute("PRAGMA user_version").fetchone()[0] == 0:
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")  # room for future migrations
        for i, (slug, name, desc, icon, color) in enumerate(SKILLS):
            conn.execute(
                "INSERT INTO skills(slug,name,description,icon,color,sort_order) VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(slug) DO UPDATE SET name=excluded.name, description=excluded.description, "
                "icon=excluded.icon, color=excluded.color, sort_order=excluded.sort_order",
                (slug, name, desc, icon, color, i),
            )
        conn.execute(
            "INSERT OR IGNORE INTO users(id,name,avatar,avatar_hue,created_at) VALUES(1,'Adventurer','🚀',265,?)",
            (clock.now_iso(),),
        )
        conn.commit()
    finally:
        conn.close()
