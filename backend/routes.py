"""HTTP layer: thin handlers that delegate to services."""
from . import validation
from .errors import validation as validation_error
from .router import Router
from .services import missions, profile, stats

router = Router()


class Ctx:
    def __init__(self, conn, params, query, body):
        self.conn, self.params, self.query, self.body = conn, params, query, body


@router.route("GET", "/api/health")
def health(c):
    return {"status": "ok"}


@router.route("GET", "/api/dashboard")
def dashboard(c):
    return stats.dashboard(c.conn)


@router.route("GET", "/api/missions")
def list_missions(c):
    return missions.list_missions(c.conn, c.query)


@router.route("POST", "/api/missions")
def create_mission(c):
    return 201, missions.create_mission(c.conn, c.body)


@router.route("GET", "/api/missions/{id}")
def get_mission(c):
    return missions.get_mission(c.conn, c.params["id"])


@router.route("PUT", "/api/missions/{id}")
def update_mission(c):
    return missions.update_mission(c.conn, c.params["id"], c.body)


@router.route("DELETE", "/api/missions/{id}")
def delete_mission(c):
    missions.delete_mission(c.conn, c.params["id"])
    return 204, None


@router.route("POST", "/api/missions/{id}/complete")
def complete(c):
    return missions.complete_mission(c.conn, c.params["id"])


@router.route("POST", "/api/missions/{id}/reopen")
def reopen(c):
    return missions.reopen_mission(c.conn, c.params["id"])


@router.route("GET", "/api/skills")
def skills(c):
    return {"items": stats.skills_state(c.conn), "user": stats.user_state(c.conn)}


@router.route("GET", "/api/achievements")
def achievements(c):
    items = stats.achievements_state(c.conn)
    return {"items": items, "unlocked": sum(1 for a in items if a["unlocked"]), "total": len(items)}


@router.route("GET", "/api/analytics")
def analytics(c):
    rng = c.query.get("range", "week")
    if rng not in ("week", "month"):
        raise validation_error({"range": "Use week or month."})
    return stats.analytics(c.conn, rng)


@router.route("GET", "/api/xp-history")
def xp_history(c):
    limit = validation.int_param(c.query, "limit", 20, 1, 100)
    offset = validation.int_param(c.query, "offset", 0, 0, 1_000_000)
    return stats.xp_history(c.conn, limit, offset)


@router.route("GET", "/api/profile")
def get_profile(c):
    return profile.get_profile(c.conn)


@router.route("PUT", "/api/profile")
def put_profile(c):
    return profile.update_profile(c.conn, c.body)


@router.route("POST", "/api/profile/reset")
def reset(c):
    return profile.reset_progress(c.conn, c.body)
