import json
import os
from datetime import date, datetime

STORE_FILE = "xp_data.json"

def load_store() -> dict:
    if os.path.exists(STORE_FILE):
        try:
            with open(STORE_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_store(store: dict):
    with open(STORE_FILE, "w") as f:
        json.dump(store, f)

def load_user(username: str) -> dict:
    """Load user data by username"""
    store = load_store()
    username = username.strip().lower()
    if username in store:
        return store[username]
    return {
        "xp": 0,
        "level": 1,
        "streak_days": [],
        "last_practice": None,
        "total_solved": 0,
        "total_correct": 0,
        "max_streak": 0,
        "created": str(date.today())
    }

def save_user(username: str, data: dict):
    """Save user data"""
    store = load_store()
    username = username.strip().lower()
    store[username] = data
    save_store(store)

def apply_daily_penalty(user_data: dict, penalty_per_day: int = 20) -> dict:
    """Apply XP penalty for missed days"""
    today = str(date.today())
    last = user_data.get("last_practice")

    if last and last != today:
        last_date = date.fromisoformat(last)
        missed = (date.today() - last_date).days - 1
        if missed > 0:
            penalty = missed * penalty_per_day
            user_data["xp"] = max(0, user_data["xp"] - penalty)
            user_data["penalty_applied"] = penalty
            user_data["missed_days"] = missed
        else:
            user_data["penalty_applied"] = 0
            user_data["missed_days"] = 0
    else:
        user_data["penalty_applied"] = 0
        user_data["missed_days"] = 0

    return user_data

def get_all_users() -> list:
    """Get leaderboard data"""
    store = load_store()
    users = []
    for name, data in store.items():
        users.append({
            "username": name,
            "xp": data.get("xp", 0),
            "level": data.get("level", 1),
            "total_solved": data.get("total_solved", 0),
            "streak": len(data.get("streak_days", []))
        })
    return sorted(users, key=lambda x: x["xp"], reverse=True)
