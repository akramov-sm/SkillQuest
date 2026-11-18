from .. import validation
from ..db import transaction
from . import stats


def get_profile(conn):
    return stats.profile(conn)


def update_profile(conn, data):
    v = validation.profile_input(data)
    with transaction(conn):
        conn.execute("UPDATE users SET name=?, avatar=?, avatar_hue=? WHERE id=1",
                     (v["name"], v["avatar"], v["avatar_hue"]))
    return stats.profile(conn)


def reset_progress(conn, data):
    if not isinstance(data, dict) or data.get("confirm") is not True:
        raise validation.validation({"confirm": "Send {\"confirm\": true} to reset all progress."})
    with transaction(conn):
        conn.execute("DELETE FROM xp_events")
        conn.execute("DELETE FROM missions")
        conn.execute("DELETE FROM user_achievements")
    return stats.profile(conn)
