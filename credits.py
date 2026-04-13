import redis
import os

r = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=6379,
    password=os.getenv("REDIS_PASSWORD"),
    decode_responses=True
)

def get_credits(user):
    credits = r.get(f"credits:{user}")
    return int(credits) if credits else 0

def add_credits(user, amount):
    return r.incrby(f"credits:{user}", amount)

def set_credits(user, amount):
    r.set(f"credits:{user}", amount)

def deduct_credit(user, amount=1):
    current = get_credits(user)
    if current >= amount:
        r.decrby(f"credits:{user}", amount)
        return True
    return False