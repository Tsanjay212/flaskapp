from flask import Flask, render_template, request, redirect, session, url_for, flash, Response
import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import json
import os
from functools import wraps
from collections import defaultdict
import time
import csv
from io import StringIO
import socket

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "supersecretkey")

# ----------------------------
# Health check
# ----------------------------
@app.route('/health')
def health():
    return "OK", 200

# ----------------------------
# Server check
# ----------------------------
@app.route("/server")
def server():
    return f"Served from: {socket.gethostname()}"

# ----------------------------
# Database Config
# ----------------------------
DB_HOST = os.environ.get("MYSQL_HOST", "flask-mariadb-db.cnwcmsquw4d7.ap-south-2.rds.amazonaws.com")
DB_USER = os.environ.get("MYSQL_USER", "flaskdb")
DB_PASSWORD = os.environ.get("MYSQL_PASSWORD", "Tsanjay212")
DB_NAME = os.environ.get("MYSQL_DB", "sanreach")

# ✅ NEW: Create connection function
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        return conn
    except Error as e:
        print(f"DB Connection Error: {e}")
        return None

# ----------------------------
# Login Required Decorator
# ----------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# ----------------------------
# Routes
# ----------------------------
@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

# ----------------------------
# Login
# ----------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        db = get_db_connection()
        if not db:
            flash("Database connection failed", "danger")
            return redirect(url_for("login"))

        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cursor.fetchone()

        cursor.close()
        db.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials", "danger")

    return render_template("auth.html")

# ----------------------------
# Register
# ----------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        session.clear()

        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        db = get_db_connection()
        if not db:
            flash("Database connection failed", "danger")
            return redirect(url_for("register"))

        cursor = db.cursor()

        try:
            hashed_password = generate_password_hash(password)
            cursor.execute(
                "INSERT INTO users (username,email,password) VALUES (%s,%s,%s)",
                (username, email, hashed_password)
            )
            db.commit()

            flash("Account created! Please login.", "success")
            return redirect(url_for("login"))

        except mysql.connector.IntegrityError:
            flash("Username or Email already exists.", "danger")

        finally:
            cursor.close()
            db.close()

    return render_template("auth.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))

# ----------------------------
# Dashboard
# ----------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT DATE(sent_at) as day, dest, message, status, sent_at
        FROM sms_logs
        WHERE user_id = %s
        ORDER BY sent_at DESC
    """, (session["user_id"],))

    sms_data = cursor.fetchall()
    cursor.close()
    db.close()

    day_wise = defaultdict(list)
    for row in sms_data:
        day_wise[row["day"]].append(row)

    return render_template("dashboard.html", username=session.get("username"), day_wise=day_wise)

# ----------------------------
# Send SMS
# ----------------------------
@app.route("/send_sms", methods=["POST"])
@login_required
def send_sms():
    number = request.form.get("number")
    message_text = request.form.get("message")

    api_url = "https://japi.instaalerts.zone/httpapi/JsonReceiver"
    api_key = "A8CtOgAdEUfuWjFLlvwAOQ=="

    payload = {
        "ver": "1.0",
        "key": api_key,
        "encrypt": "0",
        "messages": [{"dest": [number], "text": message_text}]
    }

    headers = {"Content-Type": "application/json"}
    status = "Failed"

    try:
        response = requests.post(api_url, headers=headers, data=json.dumps(payload))
        if response.status_code == 200:
            status = "Sent"
            flash("✅ SMS sent successfully!", "success")
        else:
            flash("⚠️ SMS failed", "danger")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute(
        "INSERT INTO sms_logs (user_id, dest, message, status) VALUES (%s, %s, %s, %s)",
        (session["user_id"], number, message_text, status)
    )
    db.commit()

    cursor.close()
    db.close()

    return redirect(url_for("dashboard"))

# ----------------------------
# Run
# ----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)