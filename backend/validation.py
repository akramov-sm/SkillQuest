"""Input validation. Raises ApiError(400) with per-field messages."""
from datetime import date

from . import xp as xpmod
from .errors import validation


def _has_control_chars(text, allow_whitespace):
    return any(ord(c) < 32 and not (allow_whitespace and c in "\n\r\t") or ord(c) == 127 for c in text)


def _str(data, key, errors, *, required=False, max_len=0, default="", multiline=False):
    val = data.get(key, None)
    if val is None:
        if required:
            errors[key] = "This field is required."
        return default
    if not isinstance(val, str):
        errors[key] = "Must be text."
        return default
    val = val.strip()
    if required and not val:
        errors[key] = "This field is required."
    elif len(val) > max_len:
        errors[key] = f"Must be at most {max_len} characters."
    elif _has_control_chars(val, multiline):
        errors[key] = "Contains invalid control characters."
    return val


def _int(val):
    if isinstance(val, bool):
        raise ValueError
    if isinstance(val, int):
        return val
    if isinstance(val, float) and val.is_integer():
        return int(val)
    if isinstance(val, str) and val.strip().lstrip("-").isdigit():
        return int(val.strip())
    raise ValueError


def parse_date(value):
    try:
        return date.fromisoformat(value) if isinstance(value, str) and len(value) == 10 else None
    except ValueError:
        return None


def mission_input(data, valid_categories):
    if not isinstance(data, dict):
        raise validation({"_": "Body must be a JSON object."})
    errors = {}
    title = _str(data, "title", errors, required=True, max_len=120)
    description = _str(data, "description", errors, max_len=1000, multiline=True)

    category = data.get("category")
    if category not in valid_categories:
        errors["category"] = "Choose a valid category."

    difficulty = data.get("difficulty", "medium")
    if difficulty not in xpmod.DIFFICULTIES:
        errors["difficulty"] = "Choose Easy, Medium, Hard or Epic."

    xp_val = data.get("xp")
    if xp_val in (None, ""):
        xp_val = xpmod.DIFFICULTIES.get(difficulty, 50)
    else:
        try:
            xp_val = _int(xp_val)
            if not xpmod.MIN_XP <= xp_val <= xpmod.MAX_XP:
                raise ValueError
        except ValueError:
            errors["xp"] = f"XP must be a whole number between {xpmod.MIN_XP} and {xpmod.MAX_XP}."

    due = data.get("due_date")
    if due in (None, ""):
        due = None
    elif parse_date(due) is None:
        errors["due_date"] = "Use a valid date (YYYY-MM-DD)."

    if errors:
        raise validation(errors)
    return {"title": title, "description": description, "category": category,
            "difficulty": difficulty, "xp": xp_val, "due_date": due}


def profile_input(data):
    if not isinstance(data, dict):
        raise validation({"_": "Body must be a JSON object."})
    errors = {}
    name = _str(data, "name", errors, required=True, max_len=40)
    avatar = _str(data, "avatar", errors, required=True, max_len=8)
    try:
        hue = _int(data.get("avatar_hue", 265))
        if not 0 <= hue <= 360:
            raise ValueError
    except ValueError:
        errors["avatar_hue"] = "Hue must be between 0 and 360."
        hue = 265
    if errors:
        raise validation(errors)
    return {"name": name, "avatar": avatar, "avatar_hue": hue}


def int_param(query, key, default, lo, hi):
    raw = query.get(key)
    if raw in (None, ""):
        return default
    try:
        val = _int(raw)
    except ValueError:
        raise validation({key: "Must be a whole number."})
    return max(lo, min(hi, val))
