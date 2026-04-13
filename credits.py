import redis
import mysql.connector
import os

# Redis connection setup
redis_host = os.getenv("REDIS_HOST", "172.31.0.187")
redis_port = os.getenv("REDIS_PORT", 6379)
redis_password = os.getenv("REDIS_PASSWORD", "Tsanjay212")
redis_client = redis.StrictRedis(host=redis_host, port=redis_port, password=redis_password, decode_responses=True)

# Database connection setup
DB_HOST = os.environ.get("MYSQL_HOST", "flask-mariadb-db.cnwcmsquw4d7.ap-south-2.rds.amazonaws.com")
DB_USER = os.environ.get("MYSQL_USER", "flaskdb")
DB_PASSWORD = os.environ.get("MYSQL_PASSWORD", "Tsanjay212")
DB_NAME = os.environ.get("MYSQL_DB", "sanreach")

def get_db():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )

def get_user_credits(user_id):
    """
    Get user credits from Redis, if not found in Redis, query the DB.
    """
    credits = redis_client.get(f"user_credits:{user_id}")
    if credits is None:
        # If not found in Redis, get it from the database and store in Redis
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT credits FROM users WHERE id=%s", (user_id,))
        user = cursor.fetchone()
        credits = user['credits'] if user else 0
        redis_client.set(f"user_credits:{user_id}", credits)  # Cache in Redis
        cursor.close()
        conn.close()
    return int(credits)

def update_user_credits(user_id, amount, action):
    """
    Update user credits in the database and Redis.
    :param user_id: User's ID
    :param amount: Amount to add or set
    :param action: 'add', 'update', or 'delete'
    """
    conn = get_db()
    cursor = conn.cursor()

    if action == "add":
        cursor.execute("UPDATE users SET credits = credits + %s WHERE id=%s", (amount, user_id))
    elif action == "update":
        cursor.execute("UPDATE users SET credits = %s WHERE id=%s", (amount, user_id))
    elif action == "delete":
        cursor.execute("UPDATE users SET credits = 0 WHERE id=%s", (user_id,))

    conn.commit()
    cursor.close()
    conn.close()

    # Clear the Redis cache for the user after updating the DB
    redis_client.delete(f"user_credits:{user_id}")