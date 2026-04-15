import os
import redis
from functools import wraps
from flask import session, abort, Blueprint, request, render_template, redirect, url_for, jsonify

# ----------------------------
# REDIS CONNECTION
# ----------------------------
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "172.31.0.187"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    password=os.getenv("REDIS_PASSWORD", "Tsanjay212"),
    decode_responses=True
)

# ----------------------------
# ADMIN DECORATOR (NO CIRCULAR IMPORT)
# ----------------------------
def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            return abort(403)
        return f(*args, **kwargs)
    return wrapper


# ----------------------------
# CREDIT FUNCTIONS
# ----------------------------
def get_credits(user_id):
    try:
        val = redis_client.get(f"user:{user_id}:credits")
        return int(val) if val else 0
    except:
        return 0


def set_credits(user_id, amount):
    redis_client.set(f"user:{user_id}:credits", int(amount))


def add_credits(user_id, amount):
    redis_client.incrby(f"user:{user_id}:credits", int(amount))


def deduct_credits(user_id, amount=1):
    try:
        key = f"user:{user_id}:credits"
        current = redis_client.get(key)

        current = int(current) if current else 0

        if current < amount:
            return False

        redis_client.decrby(key, amount)
        return True
    except:
        return False


def delete_credits(user_id):
    redis_client.delete(f"user:{user_id}:credits")


# ----------------------------
# ADMIN UI (OPTIONAL ROUTES)
# ----------------------------
admin_bp = Blueprint("admin_bp", __name__)


@admin_bp.route("/admin/credits", methods=["GET", "POST"])
@admin_required
def admin_credits():
    result = None

    if request.method == "POST":
        user_id = request.form.get("user_id")
        amount = request.form.get("amount")
        action = request.form.get("action")

        try:
            if action == "get":
                result = get_credits(user_id)

            elif action == "add":
                add_credits(user_id, int(amount))
                result = "Credits Added"

            elif action == "set":
                set_credits(user_id, int(amount))
                result = "Credits Set"

            elif action == "delete":
                delete_credits(user_id)
                result = "Credits Deleted"

        except Exception as e:
            result = str(e)

    return render_template("admin_credits.html", result=result)