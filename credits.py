import redis
import os

# ----------------------------
# Redis Connection
# ----------------------------
REDIS_HOST = os.environ.get("REDIS_HOST", "172.31.0.187")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", "Tsanjay212")

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5
)

# ----------------------------
# CORE FUNCTIONS
# ----------------------------

def get_credits(user_id):
    try:
        val = redis_client.get(f"user:{user_id}:credits")
        return int(val) if val else 0
    except Exception as e:
        print("get_credits error:", e)
        return 0


def set_credits(user_id, credits):
    try:
        redis_client.set(f"user:{user_id}:credits", int(credits))
        return True
    except Exception as e:
        print("set_credits error:", e)
        return False


def add_credits(user_id, credits):
    try:
        key = f"user:{user_id}:credits"
        current = redis_client.get(key)
        current = int(current) if current else 0

        new_val = current + int(credits)
        redis_client.set(key, new_val)
        return new_val
    except Exception as e:
        print("add_credits error:", e)
        return 0


def deduct_credits(user_id, credits=1):
    try:
        key = f"user:{user_id}:credits"
        current = redis_client.get(key)
        current = int(current) if current else 0

        if current < credits:
            return False

        redis_client.set(key, current - credits)
        return True

    except Exception as e:
        print("deduct_credits error:", e)
        return False