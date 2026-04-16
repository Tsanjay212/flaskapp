import os
import redis
import mysql.connector
import logging

# ----------------------------
# LOGGING
# ----------------------------
logging.basicConfig(level=logging.INFO)

# ----------------------------
# REDIS CONFIG (ENV BASED)
# ----------------------------
redis_client = redis.StrictRedis(
    host=os.environ.get("REDIS_HOST", "localhost"),
    port=int(os.environ.get("REDIS_PORT", 6379)),
    password=os.environ.get("REDIS_PASSWORD"),
    decode_responses=True,
    socket_connect_timeout=2,   # 🔥 prevents hanging
    socket_timeout=2
)

# ----------------------------
# MYSQL CONFIG (ENV BASED)
# ----------------------------
def get_db():
    return mysql.connector.connect(
        host=os.environ.get("MYSQL_HOST"),
        user=os.environ.get("MYSQL_USER"),
        password=os.environ.get("MYSQL_PASSWORD"),
        database=os.environ.get("MYSQL_DB")
    )

# ----------------------------
# GET CREDITS (Redis → MySQL fallback)
# ----------------------------
def get_credits(user_id):
    key = f"user:{user_id}:credits"

    # 🔹 Try Redis
    try:
        val = redis_client.get(key)
        if val is not None:
            return int(val)
    except Exception as e:
        logging.error(f"Redis GET failed: {e}")

    # 🔹 Fallback to MySQL
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT credits FROM users WHERE id=%s", (user_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        credits = row["credits"] if row else 0

        # 🔹 Sync back to Redis (non-blocking)
        try:
            redis_client.set(key, credits)
        except Exception as e:
            logging.warning(f"Redis SET (sync) failed: {e}")

        return credits

    except Exception as e:
        logging.error(f"MySQL GET failed: {e}")
        return 0


# ----------------------------
# SET CREDITS (Admin)
# ----------------------------
def set_credits(user_id, amount):
    key = f"user:{user_id}:credits"
    amount = int(amount)

    # 🔹 Update Redis
    try:
        redis_client.set(key, amount)
    except Exception as e:
        logging.warning(f"Redis SET failed: {e}")

    # 🔹 Update MySQL
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET credits=%s WHERE id=%s",
            (amount, user_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logging.error(f"MySQL UPDATE failed: {e}")


# ----------------------------
# ADD CREDITS
# ----------------------------
def add_credits(user_id, amount):
    try:
        current = get_credits(user_id)
        new_val = current + int(amount)
        set_credits(user_id, new_val)
    except Exception as e:
        logging.error(f"Add credits failed: {e}")


# ----------------------------
# DEDUCT CREDITS
# ----------------------------
def deduct_credits(user_id, amount=1):
    try:
        current = get_credits(user_id)

        if current < amount:
            return False

        new_val = current - amount
        set_credits(user_id, new_val)
        return True

    except Exception as e:
        logging.error(f"Deduct credits failed: {e}")
        return False