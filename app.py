from flask import Flask, render_template, request, redirect, session, url_for, flash, Response
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from functools import wraps
from io import StringIO
import csv
import os, requests, json, socket

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "supersecretkey")

# Fix for ALB
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# ----------------------------
# DB Connection (FIXED)
# ----------------------------
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

# ----------------------------
# Health
# ----------------------------
@app.route('/health')
def health():
    return "OK", 200

@app.route("/server")
def server():
    return f"Served from: {socket.gethostname()}"

# ----------------------------
# Auth
# ----------------------------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

@app.route("/")
def home():
    return redirect(url_for("dashboard") if "user_id" in session else url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("dashboard"))

        flash("Invalid credentials", "danger")

    return render_template("auth.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = generate_password_hash(request.form.get("password"))

        conn = get_db()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO users (username,email,password) VALUES (%s,%s,%s)",
                (username, email, password)
            )
            conn.commit()
            flash("Account created. Please login.", "success")
            return redirect(url_for("login"))
        except:
            flash("User already exists", "danger")

        cursor.close()
        conn.close()

    return render_template("auth.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ----------------------------
# Dashboard
# ----------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", username=session.get("username"), show_section=None)

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
        "messages": [{"dest": [number], "text": message_text, "send": "KARIXM"}]
    }

    status = "Failed"

    try:
        r = requests.post(api_url, json=payload)
        if r.status_code == 200:
            status = "Sent"
    except Exception as e:
        status = str(e)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO sms_logs (user_id, dest, message, status) VALUES (%s,%s,%s,%s)",
        (session["user_id"], number, message_text, status)
    )
    conn.commit()
    cursor.close()
    conn.close()

    flash("SMS Sent!" if status == "Sent" else "SMS Failed", "success")
    return redirect(url_for("dashboard"))

# ----------------------------
# Reports (FIXED)
# ----------------------------
@app.route("/reports")
@login_required
def reports():
    start = request.args.get("start")
    end = request.args.get("end")
    export = request.args.get("export")

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT DATE(sent_at) as day, dest, COUNT(*) as sms_count
        FROM sms_logs
        WHERE user_id=%s
    """
    params = [session["user_id"]]

    if start and end:
        query += " AND DATE(sent_at) BETWEEN %s AND %s"
        params.extend([start, end])

    query += " GROUP BY day, dest ORDER BY day DESC"

    cursor.execute(query, tuple(params))
    data = cursor.fetchall()

    cursor.close()
    conn.close()

    if export == "1":
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["Date", "Recipient", "Count"])
        for row in data:
            writer.writerow([row["day"], row["dest"], row["sms_count"]])
        return Response(output.getvalue(), mimetype="text/csv")

    return render_template("dashboard.html",
                           summary_data=data,
                           username=session.get("username"),
                           show_section="report")

# ----------------------------
# No Cache
# ----------------------------
@app.after_request
def no_cache(res):
    res.headers["Cache-Control"] = "no-store"
    return res

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)