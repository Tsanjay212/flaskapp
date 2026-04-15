import os
import redis
from app import get_db

# ----------------------------
# REDIS CONNECTION
# ----------------------------
redis_client = redis.Redis(
    host=os.environ.get("REDIS_HOST", "172.31.0.187"),
    port=6379,
    password=os.environ.get("REDIS_PASSWORD", "yourpassword"),
    decode_responses=True
)

# ----------------------------
# GET CREDITS
# ----------------------------
def get_credits(username):
    key = f"credits:{username}"

    val = redis_client.get(key)

    if val is None:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT credits FROM users WHERE username=%s",
            (username,)
        )
        row = cursor.fetchone()

        cursor.close()
        conn.close()

        if row:
            val = row["credits"]
            redis_client.set(key, val)

    return int(val or 0)


# ----------------------------
# SET CREDITS (ADMIN)
# ----------------------------
def set_credits(username, credits):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET credits=%s WHERE username=%s",
        (credits, username)
    )

    conn.commit()
    cursor.close()
    conn.close()

    redis_client.set(f"credits:{username}", int(credits))


# ----------------------------
# DEDUCT CREDITS (SMS FLOW)
# ----------------------------
def deduct_credits(username, amount=1):
    current = get_credits(username)

    if current < amount:
        return False

    new_value = current - amount
    set_credits(username, new_value)

    return True


# ----------------------------
# SYNC ALL USERS (OPTIONAL ADMIN TOOL)
# ----------------------------
def sync_all_users():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT username, credits FROM users")
    users = cursor.fetchall()

    cursor.close()
    conn.close()

    for u in users:
        redis_client.set(f"credits:{u['username']}", u["credits"])