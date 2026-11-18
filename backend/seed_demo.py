"""Optional demo data:  python3 -m backend.seed_demo  (refuses to touch a non-empty database)."""
import random
import sys
from datetime import timedelta

from . import clock, config, db
from .services import missions

IDEAS = {
    "programming": ["Solve 3 LeetCode problems", "Build a REST endpoint", "Refactor legacy module", "Read the SQLite docs", "Write unit tests"],
    "ai": ["Watch a neural nets lecture", "Fine-tune a small model", "Read a research paper", "Prompt engineering practice"],
    "english": ["30 min of listening practice", "Learn 20 new words", "Write a short essay", "Speaking session"],
    "fitness": ["Morning run 5 km", "Strength workout", "Stretch & mobility", "10k steps"],
    "finance": ["Review monthly budget", "Read about index funds", "Track expenses"],
    "personal": ["Read 30 pages", "Meditate 10 minutes", "Plan the week", "Journal"],
}


def main():
    db.init_db()
    conn = db.connect()
    if conn.execute("SELECT COUNT(*) FROM missions").fetchone()[0]:
        sys.exit("Database already has missions — refusing to add demo data.")
    rnd = random.Random(7)
    real_today = clock.today()
    diffs = ["easy", "easy", "medium", "medium", "hard", "epic"]
    for back in range(20, 0, -1):
        if back in (9, 10):  # a gap, so the streak shows both current and best
            continue
        clock.set_today(real_today - timedelta(days=back - 1))
        for _ in range(rnd.randint(1, 3)):
            cat = rnd.choice(list(IDEAS))
            m = missions.create_mission(conn, {"title": rnd.choice(IDEAS[cat]), "category": cat,
                                               "difficulty": rnd.choice(diffs)})
            missions.complete_mission(conn, m["id"])
    clock.set_today(real_today)
    for title, cat, diff, off in [("Ship the SkillQuest MVP", "programming", "epic", 3),
                                  ("Read 'Atomic Habits' ch. 4", "personal", "easy", 0),
                                  ("Leg day workout", "fitness", "medium", 0),
                                  ("Pay quarterly taxes", "finance", "hard", -2),
                                  ("Practice IELTS speaking", "english", "medium", 1)]:
        missions.create_mission(conn, {"title": title, "category": cat, "difficulty": diff,
                                       "due_date": (real_today + timedelta(days=off)).isoformat()})
    print("Demo data created in", config.DB_PATH)


if __name__ == "__main__":
    main()
