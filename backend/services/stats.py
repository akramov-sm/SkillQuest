"""Read-side logic: user level, streaks, skills, dashboard, analytics, achievements."""
from datetime import timedelta

from .. import achievements as ach, clock, xp as xpmod


# ---------- core aggregates ----------
def total_xp(conn):
    return conn.execute("SELECT COALESCE(SUM(amount),0) FROM xp_events").fetchone()[0]


def activity_days(conn):
    return sorted({r[0] for r in conn.execute("SELECT DISTINCT day FROM xp_events WHERE source='mission'")})


def streak_info(conn, days=None, today=None):
    from datetime import date
    today = today or clock.today()
    days = activity_days(conn) if days is None else days
    ds = {date.fromisoformat(d) for d in days}
    # current streak: alive if active today or yesterday
    anchor = today if today in ds else (today - timedelta(days=1) if (today - timedelta(days=1)) in ds else None)
    current = 0
    if anchor:
        d = anchor
        while d in ds:
            current += 1
            d -= timedelta(days=1)
    best = run = 0
    prev = None
    for d in sorted(ds):
        run = run + 1 if prev and (d - prev).days == 1 else 1
        best = max(best, run)
        prev = d
    return {"current": current, "best": best, "active_today": today in ds}


def skills_state(conn):
    xp_by = {r["skill_slug"]: r["xp"] for r in conn.execute(
        "SELECT skill_slug, SUM(amount) xp FROM xp_events WHERE skill_slug IS NOT NULL GROUP BY skill_slug")}
    counts = {r["category"]: r["n"] for r in conn.execute(
        "SELECT category, COUNT(*) n FROM missions WHERE status='pending' GROUP BY category")}
    done = {r["skill_slug"]: r["n"] for r in conn.execute(
        "SELECT skill_slug, COUNT(*) n FROM xp_events WHERE source='mission' GROUP BY skill_slug")}
    out = []
    for s in conn.execute("SELECT * FROM skills ORDER BY sort_order"):
        info = xpmod.level_info(xp_by.get(s["slug"], 0), "skill")
        out.append({"slug": s["slug"], "name": s["name"], "description": s["description"],
                    "icon": s["icon"], "color": s["color"], **info,
                    "tiers": xpmod.tiers_for(info["level"]),
                    "active_missions": counts.get(s["slug"], 0),
                    "completed_missions": done.get(s["slug"], 0)})
    return out


def collect_metrics(conn):
    skills = skills_state(conn)
    total = total_xp(conn)
    return {
        "missions_completed": conn.execute("SELECT COUNT(*) FROM xp_events WHERE source='mission'").fetchone()[0],
        "longest_streak": streak_info(conn)["best"],
        "total_xp": total,
        "max_skill_level": max(s["level"] for s in skills),
        "skills_started": sum(1 for s in skills if s["xp"] > 0),
        "level": xpmod.level_info(total)["level"],
        "epic_completed": conn.execute(
            "SELECT COUNT(*) FROM xp_events WHERE source='mission' AND difficulty='epic'").fetchone()[0],
    }


def user_state(conn):
    u = conn.execute("SELECT * FROM users WHERE id=1").fetchone()
    info = xpmod.level_info(total_xp(conn))
    return {"name": u["name"], "avatar": u["avatar"], "avatar_hue": u["avatar_hue"],
            "created_at": u["created_at"], **info}


def achievements_state(conn):
    unlocked = {r["code"]: r["unlocked_at"] for r in conn.execute("SELECT * FROM user_achievements")}
    metrics = collect_metrics(conn)
    out = []
    for a in ach.ACHIEVEMENTS:
        prog = min(metrics[a["metric"]], a["target"])
        out.append({"code": a["code"], "title": a["title"], "description": a["description"],
                    "icon": a["icon"], "reward_xp": a["reward_xp"], "target": a["target"],
                    "progress": prog, "unlocked": a["code"] in unlocked,
                    "unlocked_at": unlocked.get(a["code"])})
    return out


# ---------- series ----------
def daily_series(conn, days, today=None):
    today = today or clock.today()
    start = today - timedelta(days=days - 1)
    rows = {r["day"]: r for r in conn.execute(
        "SELECT day, SUM(amount) xp, SUM(CASE WHEN source='mission' THEN 1 ELSE 0 END) missions "
        "FROM xp_events WHERE day >= ? AND day <= ? GROUP BY day", (start.isoformat(), today.isoformat()))}
    series = []
    for i in range(days):
        d = (start + timedelta(days=i)).isoformat()
        r = rows.get(d)
        series.append({"day": d, "xp": r["xp"] if r else 0, "missions": r["missions"] if r else 0})
    return series


# ---------- endpoints ----------
def dashboard(conn):
    today = clock.today().isoformat()
    cols = "id,title,description,category,difficulty,xp,due_date,status,created_at,updated_at,completed_at"
    rows = conn.execute(
        f"SELECT {cols} FROM missions WHERE (status='pending' AND (due_date IS NULL OR due_date <= ?)) "
        f"OR (status='completed' AND substr(completed_at,1,10)=?) "
        "ORDER BY status DESC, CASE WHEN due_date IS NULL THEN 1 ELSE 0 END, due_date, id LIMIT 12",
        (today, today)).fetchall()
    from .missions import row_to_dict
    week = daily_series(conn, 7)
    unlocked = [a for a in achievements_state(conn) if a["unlocked"]]
    unlocked.sort(key=lambda a: a["unlocked_at"], reverse=True)
    all_ach = len(ach.ACHIEVEMENTS)
    return {
        "user": user_state(conn),
        "streak": streak_info(conn),
        "today": [row_to_dict(r) for r in rows],
        "week": {"series": week, "xp": sum(d["xp"] for d in week),
                 "missions": sum(d["missions"] for d in week)},
        "recent_achievements": unlocked[:4],
        "achievements": {"unlocked": len(unlocked), "total": all_ach},
        "skills": skills_state(conn),
        "pending_total": conn.execute("SELECT COUNT(*) FROM missions WHERE status='pending'").fetchone()[0],
    }


def analytics(conn, range_name):
    days = 7 if range_name == "week" else 30
    today = clock.today()
    start = (today - timedelta(days=days - 1)).isoformat()
    series = daily_series(conn, days)
    cats = conn.execute(
        "SELECT s.slug, s.name, s.color, COALESCE(SUM(e.amount),0) xp, COUNT(e.id) missions "
        "FROM skills s LEFT JOIN xp_events e ON e.skill_slug=s.slug AND e.source='mission' AND e.day >= ? "
        "GROUP BY s.slug ORDER BY s.sort_order", (start,)).fetchall()
    total_cat_xp = sum(c["xp"] for c in cats)
    best = max(series, key=lambda d: d["xp"])
    xp_sum = sum(d["xp"] for d in series)
    return {
        "range": range_name, "days": days, "series": series,
        "totals": {"xp": xp_sum, "category_xp": total_cat_xp, "missions": sum(d["missions"] for d in series),
                   "avg_xp_per_day": round(xp_sum / days, 1),
                   "active_days": sum(1 for d in series if d["missions"] > 0),
                   "best_day": best if best["xp"] > 0 else None},
        "categories": [{"slug": c["slug"], "name": c["name"], "color": c["color"], "xp": c["xp"],
                        "missions": c["missions"],
                        "share": round(c["xp"] / total_cat_xp, 4) if total_cat_xp else 0} for c in cats],
        "skills": [{k: s[k] for k in ("slug", "name", "color", "level", "xp", "progress", "xp_into_level", "xp_for_next")}
                   for s in skills_state(conn)],
        "all_time": {"xp": total_xp(conn),
                     "missions": conn.execute("SELECT COUNT(*) FROM xp_events WHERE source='mission'").fetchone()[0]},
    }


def xp_history(conn, limit, offset):
    rows = conn.execute(
        "SELECT e.id, e.label, e.source, e.base_xp, e.bonus_xp, e.amount, e.day, e.created_at, "
        "e.skill_slug, s.name skill_name, s.color skill_color "
        "FROM xp_events e LEFT JOIN skills s ON s.slug=e.skill_slug "
        "ORDER BY e.id DESC LIMIT ? OFFSET ?", (limit + 1, offset)).fetchall()
    more = len(rows) > limit
    return {"items": [dict(r) for r in rows[:limit]], "has_more": more}


def profile(conn):
    st = user_state(conn)
    ach_list = achievements_state(conn)
    streak = streak_info(conn)
    unlocked = sum(1 for a in ach_list if a["unlocked"])
    missions = conn.execute("SELECT COUNT(*) FROM xp_events WHERE source='mission'").fetchone()[0]
    from datetime import date, datetime
    joined = datetime.fromisoformat(st["created_at"]).date()
    return {
        "user": st,
        "stats": {"missions_completed": missions, "best_streak": streak["best"],
                  "current_streak": streak["current"],
                  "achievements_unlocked": unlocked, "achievements_total": len(ach_list),
                  "days_with_us": (clock.today() - joined).days + 1,
                  "top_skill": max(skills_state(conn), key=lambda s: s["xp"])["name"] if total_xp(conn) else None},
        "achievements": [a for a in ach_list if a["unlocked"]],
    }
