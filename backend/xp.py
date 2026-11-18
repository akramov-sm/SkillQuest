"""Pure game-balance rules: levels, rewards, streak multipliers, skill tiers."""
import math

DIFFICULTIES = {"easy": 20, "medium": 50, "hard": 100, "epic": 200}
MIN_XP, MAX_XP = 1, 1000
MAX_SKILL_LEVEL = 50

# (min streak days, multiplier) — highest matching wins
STREAK_MULTIPLIERS = [(30, 1.20), (14, 1.15), (7, 1.10), (3, 1.05)]

TIERS = [(1, "Novice"), (2, "Apprentice"), (4, "Adept"), (6, "Expert"), (8, "Master")]


def user_xp_for_level(level: int) -> int:
    """Total XP required to reach `level` (level 1 = 0 XP)."""
    return 50 * level * (level - 1)


def skill_xp_for_level(level: int) -> int:
    return 25 * level * (level - 1)


def _level_from(xp: int, threshold, cap=None) -> int:
    xp = max(0, int(xp))
    level = max(1, int((1 + math.sqrt(1 + 0.08 * xp)) / 2) - 1)  # close guess, then correct
    while threshold(level + 1) <= xp and (cap is None or level < cap):
        level += 1
    while level > 1 and threshold(level) > xp:
        level -= 1
    return level


def level_info(xp: int, kind="user") -> dict:
    """Level, progress into level and XP needed for the next level."""
    if kind == "user":
        threshold, cap = user_xp_for_level, None
    else:
        threshold, cap = skill_xp_for_level, MAX_SKILL_LEVEL
    xp = max(0, int(xp))
    level = _level_from(xp, threshold, cap)
    start = threshold(level)
    if cap is not None and level >= cap:
        return {"level": level, "xp": xp, "xp_into_level": xp - start, "xp_for_next": 0,
                "progress": 1.0, "maxed": True}
    needed = threshold(level + 1) - start
    into = xp - start
    return {"level": level, "xp": xp, "xp_into_level": into, "xp_for_next": needed,
            "progress": round(into / needed, 4), "maxed": False}


def streak_multiplier(streak: int) -> float:
    for days, mult in STREAK_MULTIPLIERS:
        if streak >= days:
            return mult
    return 1.0


def streak_bonus(base_xp: int, streak: int) -> int:
    return int(round(base_xp * (streak_multiplier(streak) - 1)))


def tiers_for(level: int) -> list:
    return [{"name": name, "required_level": lvl, "unlocked": level >= lvl} for lvl, name in TIERS]
