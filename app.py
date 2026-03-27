from flask import Flask, render_template, request, redirect, session, url_for, flash, Response
import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from functools import wraps
from collections import defaultdict
from io import StringIO
import csv
import os, time, requests, json, socket

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "supersecretkey")

# Fix for ALB / reverse proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# ----------------------------
# Health & Server Info
# ----------------------------
@app.route('/health')
def health():
    return "OK", 200

@app.route("/server")
def server():
    return f"Served from: {socket.gethostname()}"

# ----------------------------
# Database connection
# ----------------------------
DB_HOST = os.environ.get("MYSQL_HOST", "flask-mariadb-db.cnwcmsquw4d7.ap-south-2.rds.amazonaws.com")
DB_USER = os.environ.get("MYSQL_USER", "flaskdb")
DB_PASSWORD = os.environ.get("MYSQL_PASSWORD", "Tsanjay212")
DB_NAME = os.environ.get("MYSQL_DB", "sanreach")

db = None
for i in range(10):
    try:
        db = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        print("✅ DB connected")
        break
    except Error as e:
        print(f"⚠️ DB connection failed, retrying... ({i+1}/10) - {e}")
        time.sleep(3)

if db is None:
    raise Exception("❌ Could not connect to the database after 10 retries")

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
# Auth Routes
# ----------------------------
@app.route("/", methods=["GET"])
def home():
    return redirect(url_for("dashboard") if "user_id" in session else url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Username and password are required.", "danger")
            return redirect(url_for("login"))

        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cursor.fetchone()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials", "danger")
    return render_template("auth.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        session.clear()
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)
        cursor = db.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username,email,password) VALUES (%s,%s,%s)",
                (username, email, hashed_password)
            )
            db.commit()
            flash("Account created successfully! Please login.", "success")
            return redirect(url_for("login"))
        except mysql.connector.IntegrityError:
            flash("Username or Email already exists.", "danger")
            return redirect(url_for("register"))
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
    return render_template("dashboard.html", username=session.get("username"), show_section=None)

# ----------------------------
# Send SMS Route
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
        "messages": [{"dest": [number], "text": message_text, "send": "KARIXM","vp":30,"cust_ref":"cust_ref","lang":"PM"}]
    }

    headers = {"Content-Type": "application/json"}
    status = "Failed"
    message_flash = ""

    try:
        response = requests.post(api_url, headers=headers, data=json.dumps(payload))
        if response.status_code == 200:
            status = "Sent"
            message_flash = "✅ SMS sent successfully!"
        else:
            status = f"Error: {response.text}"
            message_flash = f"⚠️ Failed to send SMS: {response.text}"
    except Exception as e:
        status = f"Exception: {str(e)}"
        message_flash = f"⚠️ Error sending SMS: {str(e)}"

    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO sms_logs (user_id, dest, message, status) VALUES (%s, %s, %s, %s)",
        (session["user_id"], number, message_text, status)
    )
    db.commit()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return {"status": status, "message": message_flash}

    flash(message_flash)
    return redirect(url_for("dashboard"))

# ----------------------------
# Reports Route (summary)
# ----------------------------
@app.route("/reports")
@login_required
def reports():
    start_date = request.args.get("start")
    end_date = request.args.get("end")
    export_csv = request.args.get("export")

    cursor = db.cursor(dictionary=True)

    if start_date and end_date:
        cursor.execute("""
            SELECT DATE(sent_at) as day, dest, COUNT(*) as sms_count
            FROM sms_logs
            WHERE user_id=%s AND DATE(sent_at) BETWEEN %s AND %s
            GROUP BY day, dest
            ORDER BY day DESC
        """, (session["user_id"], start_date, end_date))
    else:
        cursor.execute("""
            SELECT DATE(sent_at) as day, dest, COUNT(*) as sms_count
            FROM sms_logs
            WHERE user_id=%s
            GROUP BY day, dest
            ORDER BY day DESC
        """, (session["user_id"],))
    
    summary_data = cursor.fetchall()

    # CSV export
    if export_csv == "1":
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["Date", "Recipient", "SMS Count"])
        for row in summary_data:
            writer.writerow([row["day"], row["dest"], row["sms_count"]])
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=sms_summary.csv"}
        )

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        # Return simple summary table
        table_html = "<table><thead><tr><th>Date</th><th>Recipient</th><th>SMS Count</th></tr></thead><tbody>"
        for row in summary_data:
            table_html += f"<tr><td>{row['day']}</td><td>{row['dest']}</td><td>{row['sms_count']}</td></tr>"
        if not summary_data:
            table_html += "<tr><td colspan='3'>No SMS records found.</td></tr>"
        table_html += "</tbody></table>"
        return table_html

    return render_template("dashboard.html", summary_data=summary_data, username=session.get("username"), show_section="report")

# ----------------------------
# SMS Templates Feature
# ----------------------------

@app.route("/templates")
@login_required
def templates():
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, name, message, created_at 
        FROM sms_templates 
        WHERE user_id=%s 
        ORDER BY id DESC
    """, (session["user_id"],))
    templates = cursor.fetchall()
    return render_template(
        "dashboard.html",
        templates=templates,
        username=session.get("username"),
        show_section="template-section"
    )


@app.route("/add_template", methods=["POST"])
@login_required
def add_template():
    name = request.form.get("name")
    message = request.form.get("message")

    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO sms_templates (user_id, name, message) 
        VALUES (%s, %s, %s)
    """, (session["user_id"], name, message))
    db.commit()

    return redirect(url_for("templates"))


@app.route("/update_template/<int:id>", methods=["POST"])
@login_required
def update_template(id):
    name = request.form.get("name")
    message = request.form.get("message")

    cursor = db.cursor()
    cursor.execute("""
        UPDATE sms_templates 
        SET name=%s, message=%s 
        WHERE id=%s AND user_id=%s
    """, (name, message, id, session["user_id"]))
    db.commit()

    return redirect(url_for("templates"))


@app.route("/delete_template/<int:id>")
@login_required
def delete_template(id):
    cursor = db.cursor()
    cursor.execute("""
        DELETE FROM sms_templates 
        WHERE id=%s AND user_id=%s
    """, (id, session["user_id"]))
    db.commit()

    return redirect(url_for("templates"))

# ----------------------------
# Run Flask
# ----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)