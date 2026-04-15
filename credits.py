import redis
import mysql.connector
import logging
# Setup logging
logging.basicConfig(level=logging.DEBUG)

# ----------------------------
# REDIS CONFIG
# ----------------------------
redis_client = redis.StrictRedis(
    host="172.17.0.2",  # Replace with your Redis instance host
    port=6379,
    password="Tsanjay212",  # Replace with your Redis password
    decode_responses=True
)

# ----------------------------
# MYSQL CONNECTION
# ----------------------------
def get_db():
    return mysql.connector.connect(
        host="flask-mariadb-db.cnwcmsquw4d7.ap-south-2.rds.amazonaws.com",   # Replace with your RDS host
        user="flaskdb",   # Replace with your RDS username
        password="Tsanjay212",  # Replace with your RDS password
        database="flaskdb"   # Replace with your database name
    )

# ----------------------------
# GET CREDITS (Redis → fallback to MySQL)
# ----------------------------
def get_credits(user_id):
    key = f"user:{user_id}:credits"
    
    # Check Redis first
    val = redis_client.get(key)
    if val is not None:
        return int(val)

    # Fallback to MySQL
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT credits FROM users WHERE id=%s", (user_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    credits = row["credits"] if row else 0

    # Sync Redis
    redis_client.set(key, credits)
    return credits

# ----------------------------
# SET CREDITS (Admin)
# ----------------------------
def set_credits(user_id, amount):
    key = f"user:{user_id}:credits"
    
    # Set Redis value
    redis_client.set(key, int(amount))

    # Update MySQL
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET credits=%s WHERE id=%s",
        (amount, user_id)
    )
    conn.commit()
    cursor.close()
    conn.close()

# ----------------------------
# ADD CREDITS
# ----------------------------
def add_credits(user_id, amount):
    current = get_credits(user_id)
    new_val = current + int(amount)
    set_credits(user_id, new_val)

# ----------------------------
# DEDUCT CREDITS
# ----------------------------
def deduct_credits(user_id, amount=1):
    current = get_credits(user_id)

    if current < amount:
        return False

    new_val = current - amount
    set_credits(user_id, new_val)
    return True