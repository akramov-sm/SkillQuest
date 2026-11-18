"""Mission CRUD and the complete/reopen XP workflow."""
from .. import achievements as ach, clock, validation, xp as xpmod
from ..db import transaction
from ..errors import conflict, not_found
from . import stats

LIST_LIMIT = 500
COLS = "id,title,description,category,difficulty,xp,due_date,status,created_at,updated_at,completed_at"


def row_to_dict(r):
    d = dict(r)
    d["overdue"] = bool(d["status"] == "pending" and d["due_date"] and d["due_date"] < clock.today().isoformat())
    return d


def _categories(conn):
    return {r["slug"] for r in conn.execute("SELECT slug FROM skills")}


def _get_row(conn, mission_id):
    row = conn.execute(f"SELECT {COLS} FROM missions WHERE id=?", (mission_id,)).fetchone()
    if not row:
        raise not_found("Mission")
    return row


def list_missions(conn, query):
    where, args = [], []
    today = clock.today().isoformat()
    status = query.get("status", "all")
    if status == "active":
        where.append("status='pending'")
    elif status == "completed":
        where.append("status='completed'")
    elif status == "overdue":
        where.append("status='pending' AND due_date IS NOT NULL AND due_date < ?")
        args.append(today)
    elif status != "all":
        raise validation.validation({"status": "Use all, active, completed or overdue."})
    if query.get("category"):
        where.append("category=?")
        args.append(query["category"])
    if query.get("difficulty"):
        where.append("difficulty=?")
        args.append(query["difficulty"])
    q = (query.get("q") or "").strip()
    if q:
        esc = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where.append("(title LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\')")
        args += [f"%{esc}%", f"%{esc}%"]
    order = {
        "due": "status DESC, CASE WHEN due_date IS NULL THEN 1 ELSE 0 END, due_date, id DESC",
        "newest": "id DESC",
        "xp": "xp DESC, id DESC",
    }.get(query.get("sort", "due"))
    if order is None:
        raise validation.validation({"sort": "Use due, newest or xp."})
    sql = f"SELECT {COLS} FROM missions" + (" WHERE " + " AND ".join(where) if where else "") + f" ORDER BY {order} LIMIT {LIST_LIMIT + 1}"
    rows = conn.execute(sql, args).fetchall()
    return {"items": [row_to_dict(r) for r in rows[:LIST_LIMIT]], "truncated": len(rows) > LIST_LIMIT}


def get_mission(conn, mission_id):
    return row_to_dict(_get_row(conn, mission_id))


def create_mission(conn, data):
    v = validation.mission_input(data, _categories(conn))
    ts = clock.now_iso()
    with transaction(conn):
        cur = conn.execute(
            "INSERT INTO missions(title,description,category,difficulty,xp,due_date,status,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?, 'pending', ?, ?)",
            (v["title"], v["description"], v["category"], v["difficulty"], v["xp"], v["due_date"], ts, ts))
    return get_mission(conn, cur.lastrowid)


def update_mission(conn, mission_id, data):
    v = validation.mission_input(data, _categories(conn))
    with transaction(conn):
        row = _get_row(conn, mission_id)
        if row["status"] == "completed":
            # XP was already booked to the original skill/difficulty: keep the ledger and mission consistent.
            v["category"], v["xp"], v["difficulty"] = row["category"], row["xp"], row["difficulty"]
        conn.execute(
            "UPDATE missions SET title=?,description=?,category=?,difficulty=?,xp=?,due_date=?,updated_at=? WHERE id=?",
            (v["title"], v["description"], v["category"], v["difficulty"], v["xp"], v["due_date"],
             clock.now_iso(), mission_id))
    return get_mission(conn, mission_id)


def delete_mission(conn, mission_id):
    with transaction(conn):  # earned XP stays in the ledger (mission_id → NULL)
        _get_row(conn, mission_id)
        conn.execute("DELETE FROM missions WHERE id=?", (mission_id,))


def complete_mission(conn, mission_id):
    with transaction(conn):
        m = _get_row(conn, mission_id)
        if m["status"] == "completed":
            raise conflict("This mission is already completed.")
        before_total = stats.total_xp(conn)
        before_skill = next(s for s in stats.skills_state(conn) if s["slug"] == m["category"])["level"]
        today = clock.today()
        # streak after this completion
        info = stats.streak_info(conn)
        streak_after = info["current"] if info["active_today"] else info["current"] + 1
        bonus = xpmod.streak_bonus(m["xp"], streak_after)
        ts = clock.now_iso()
        conn.execute(
            "INSERT INTO xp_events(mission_id,skill_slug,source,label,difficulty,base_xp,bonus_xp,amount,day,created_at) "
            "VALUES(?,?, 'mission', ?,?,?,?,?,?,?)",
            (m["id"], m["category"], m["title"], m["difficulty"], m["xp"], bonus, m["xp"] + bonus,
             today.isoformat(), ts))
        done = conn.execute("UPDATE missions SET status='completed', completed_at=?, updated_at=? "
                            "WHERE id=? AND status='pending'", (ts, ts, mission_id))
        if done.rowcount != 1:  # defence in depth; the IMMEDIATE lock already serialises writers
            raise conflict("This mission is already completed.")
        mid_total = stats.total_xp(conn)
        new_ach = ach.evaluate(conn, stats.collect_metrics)
        after_total = stats.total_xp(conn)
        after_skill = next(s for s in stats.skills_state(conn) if s["slug"] == m["category"])["level"]
    lvl_before = xpmod.level_info(before_total)["level"]
    lvl_after = xpmod.level_info(after_total)["level"]
    return {
        "mission": get_mission(conn, mission_id),
        "reward": {"base_xp": m["xp"], "bonus_xp": bonus, "total_xp": m["xp"] + bonus,
                   "achievement_xp": sum(a["reward_xp"] for a in new_ach), "skill": m["category"]},
        "level": {"before": lvl_before, "after": lvl_after, "leveled_up": lvl_after > lvl_before},
        "skill_level": {"before": before_skill, "after": after_skill, "leveled_up": after_skill > before_skill,
                        "slug": m["category"]},
        "streak": stats.streak_info(conn)["current"],
        "new_achievements": new_ach,
        "user": stats.user_state(conn),
    }


def reopen_mission(conn, mission_id):
    with transaction(conn):
        m = _get_row(conn, mission_id)
        if m["status"] != "completed":
            raise conflict("This mission is not completed.")
        conn.execute("DELETE FROM xp_events WHERE mission_id=? AND source='mission'", (mission_id,))
        conn.execute("UPDATE missions SET status='pending', completed_at=NULL, updated_at=? WHERE id=?",
                     (clock.now_iso(), mission_id))
    return {"mission": get_mission(conn, mission_id), "user": stats.user_state(conn)}
