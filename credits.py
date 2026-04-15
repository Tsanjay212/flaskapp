import redis
import os
from flask import Blueprint, render_template, request, session, jsonify

# ----------------------------
# REDIS CONNECTION
# ----------------------------
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "172-31-0-187"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    password=os.getenv("REDIS_PASSWORD", "Tsanjay212"),
    decode_responses=True
)

# ----------------------------
# CREDIT LOGIC
# ----------------------------
def get_credits(user_id):
    val = redis_client.get(f"user:{user_id}:credits")
    return int(val) if val else 0

def add_credits(user_id, amount):
    return redis_client.incrby(f"user:{user_id}:credits", amount)

def set_credits(user_id, amount):
    redis_client.set(f"user:{user_id}:credits", amount)

def delete_credits(user_id):
    redis_client.delete(f"user:{user_id}:credits")

def deduct_credits(user_id, amount):
    current = get_credits(user_id)
    if current < amount:
        return False
    redis_client.decrby(f"user:{user_id}:credits", amount)
    return True

# ----------------------------
# ADMIN UI (SEPARATE PAGE)
# ----------------------------
credits_bp = Blueprint("credits", __name__)

ADMIN_USERNAME = "admin"

@credits_bp.route("/admin/credits", methods=["GET", "POST"])
def admin_credits():

    # restrict to admin
    if session.get("username") != ADMIN_USERNAME:
        return "Unauthorized", 403

    result = None

    if request.method == "POST":
        user_id = request.form.get("user_id")
        action = request.form.get("action")
        amount = request.form.get("amount")

        if action == "add":
            result = add_credits(user_id, int(amount))
        elif action == "set":
            set_credits(user_id, int(amount))
            result = "Updated"
        elif action == "delete":
            delete_credits(user_id)
            result = "Deleted"
        elif action == "get":
            result = get_credits(user_id)

    return render_template("admin_credits.html", result=result)

# ----------------------------
# USER API (LIVE BALANCE)
# ----------------------------
@credits_bp.route("/user/credits")
def user_credits():
    if "user_id" not in session:
        return jsonify({"credits": 0})
    return jsonify({"credits": get_credits(session["user_id"])})