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
    decode_responses=True
)

# ----------------------------
# CORE FUNCTIONS
# ----------------------------

def get_credits(user_id):
    """
    Get user credits from Redis
    """
    try:
        val = redis_client.get(f"user:{user_id}:credits")
        return int(val) if val else 0
    except Exception as e:
        print("Redis get_credits error:", e)
        return 0


def set_credits(user_id, credits):
    """
    Set absolute credits (Admin use)
    """
    try:
        redis_client.set(f"user:{user_id}:credits", int(credits))
        return True
    except Exception as e:
        print("Redis set_credits error:", e)
        return False


def add_credits(user_id, credits):
    """
    Add credits to existing balance
    """
    try:
        key = f"user:{user_id}:credits"
        current = redis_client.get(key)
        current = int(current) if current else 0

        new_balance = current + int(credits)
        redis_client.set(key, new_balance)
        return new_balance
    except Exception as e:
        print("Redis add_credits error:", e)
        return 0


def deduct_credits(user_id, credits=1):
    """
    Deduct credits before sending SMS
    Returns True if successful, False if insufficient credits
    """
    try:
        key = f"user:{user_id}:credits"
        current = redis_client.get(key)
        current = int(current) if current else 0

        if current < credits:
            return False

        new_balance = current - credits
        redis_client.set(key, new_balance)
        return True

    except Exception as e:
        print("Redis deduct_credits error:", e)
        return False