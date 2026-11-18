"""Achievement definitions and evaluation."""
from . import clock, xp as xpmod

# metric names are computed in services.stats.collect_metrics
ACHIEVEMENTS = [
    {"code": "first_mission", "title": "First Blood", "description": "Complete your first mission.",
     "icon": "flag", "metric": "missions_completed", "target": 1, "reward_xp": 25},
    {"code": "ten_missions", "title": "Getting Serious", "description": "Complete 10 missions.",
     "icon": "target", "metric": "missions_completed", "target": 10, "reward_xp": 100},
    {"code": "fifty_missions", "title": "Quest Machine", "description": "Complete 50 missions.",
     "icon": "zap", "metric": "missions_completed", "target": 50, "reward_xp": 300},
    {"code": "streak_7", "title": "Week Warrior", "description": "Stay active 7 days in a row.",
     "icon": "flame", "metric": "longest_streak", "target": 7, "reward_xp": 150},
    {"code": "streak_30", "title": "Unstoppable", "description": "Stay active 30 days in a row.",
     "icon": "flame", "metric": "longest_streak", "target": 30, "reward_xp": 500},
    {"code": "xp_1000", "title": "Thousand Club", "description": "Earn 1000 XP in total.",
     "icon": "gem", "metric": "total_xp", "target": 1000, "reward_xp": 200},
    {"code": "skill_level_2", "title": "New Skill Unlocked", "description": "Raise any skill to level 2.",
     "icon": "sparkles", "metric": "max_skill_level", "target": 2, "reward_xp": 50},
    {"code": "skill_level_5", "title": "Skill Master", "description": "Raise any skill to level 5.",
     "icon": "crown", "metric": "max_skill_level", "target": 5, "reward_xp": 300},
    {"code": "polymath", "title": "Polymath", "description": "Earn XP in all 6 skills.",
     "icon": "layers", "metric": "skills_started", "target": 6, "reward_xp": 150},
    {"code": "level_5", "title": "Rising Star", "description": "Reach level 5.",
     "icon": "star", "metric": "level", "target": 5, "reward_xp": 200},
    {"code": "epic_mission", "title": "Epic Deed", "description": "Complete an Epic mission.",
     "icon": "trophy", "metric": "epic_completed", "target": 1, "reward_xp": 100},
]
BY_CODE = {a["code"]: a for a in ACHIEVEMENTS}


def evaluate(conn, collect_metrics):
    """Unlock every achievement whose condition is met; return the new ones.

    Bonus XP can itself unlock further achievements, so loop until stable.
    """
    unlocked_now = []
    while True:
        done = {r["code"] for r in conn.execute("SELECT code FROM user_achievements")}
        metrics = collect_metrics(conn)
        newly = [a for a in ACHIEVEMENTS if a["code"] not in done and metrics[a["metric"]] >= a["target"]]
        if not newly:
            return unlocked_now
        for a in newly:
            ts = clock.now_iso()
            conn.execute("INSERT INTO user_achievements(code, unlocked_at) VALUES(?,?)", (a["code"], ts))
            conn.execute(
                "INSERT INTO xp_events(mission_id, skill_slug, source, label, base_xp, bonus_xp, amount, day, created_at) "
                "VALUES(NULL, NULL, 'achievement', ?, ?, 0, ?, ?, ?)",
                (f"Achievement: {a['title']}", a["reward_xp"], a["reward_xp"],
                 clock.today().isoformat(), ts),
            )
            unlocked_now.append({"code": a["code"], "title": a["title"], "description": a["description"],
                                 "icon": a["icon"], "reward_xp": a["reward_xp"]})
