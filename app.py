from flask import Flask, render_template, request, redirect, session, url_for, flash, Response, jsonify
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from functools import wraps
from io import StringIO
import csv
import os, requests, socket
import random, string

# ----------------------------
# Redis Configuration
# ----------------------------
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "yourRedisPassword")

r = redis.Redis(
    host=172.31.0.187,
    port=6379,
    password=Tsanjay212,
    decode_responses=True
)
# ----------------------------
# Admin Credentials
# ----------------------------
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Tsanjay@212"
# ----------------------------
# App Setup
# ----------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "supersecretkey")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# ----------------------------
# DB Configuration
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
# Redis Credit Management
# ----------------------------
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

# ----------------------------
# Utilities
# ----------------------------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def generate_dlt_id():
    """Generate a 10-digit DLT ID starting with 212"""
    return "212" + "".join(str(random.randint(0, 9)) for _ in range(7))



# ----------------------------
# Auth Routes
# ----------------------------
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
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # Only fetch templates for the logged-in user
    cursor.execute(
        "SELECT * FROM templates WHERE user_id=%s ORDER BY id DESC LIMIT 5",
        (session["user_id"],)
    )
    last_templates = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template(
        "dashboard.html",
        username=session.get("username"),
        show_section="send-section",
        templates=last_templates,
        total=len(last_templates),
        per_page=5
    )

# ----------------------------
# Send SMS
# ----------------------------
@app.route("/send_sms", methods=["POST"])
@login_required
def send_sms():
    number = request.form.get("number")
    message_text = request.form.get("message")
    template_id = request.form.get("template_id")

    user = session["username"]

    # Check if the user has enough credits before sending SMS
    if not deduct_credit(user, 1):
        return "❌ Not enough credits", 403

    if template_id:
        try:
            conn = get_db()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT content FROM templates WHERE id=%s", (template_id,))
            tpl = cursor.fetchone()
            cursor.close()
            conn.close()

            if tpl and tpl.get("content"):
                message_text = tpl["content"]
        except:
            pass  # fail silently to avoid breaking SMS flow

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

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"status": status, "message": f"SMS {status} to {number}"})
    else:
        flash("SMS Sent!" if status == "Sent" else "SMS Failed", "success")
        return redirect(url_for("dashboard"))

# ----------------------------
# Admin Routes (Credits Management)
# ----------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect("/admin/dashboard")
        else:
            flash("Invalid credentials", "danger")

    return render_template("admin_login.html")

@app.route("/admin/dashboard")
def admin_dashboard():
    if not admin_required():
        return redirect("/admin/login")
    return render_template("admin_credits.html")

@app.route("/admin/add_credits", methods=["POST"])
def admin_add_credits():
    if not admin_required():
        return redirect("/admin/login")

    user = request.form["username"]
    amount = int(request.form["amount"])

    add_credits(user, amount)
    return f"Added {amount} credits to {user}"

@app.route("/admin/set_credits", methods=["POST"])
def admin_set_credits():
    if not admin_required():
        return redirect("/admin/login")

    user = request.form["username"]
    amount = int(request.form["amount"])

    set_credits(user, amount)
    return f"Set {user} credits to {amount}"
# ----------------------------
# Reports
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
        writer.writerow(["Date", "Recipient", "SMS Count"])
        for row in data:
            writer.writerow([row["day"], row["dest"], row["sms_count"]])
        return Response(output.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=sms_summary.csv"})

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        table_html = "<table><thead><tr><th>Date</th><th>Recipient</th><th>SMS Count</th></tr></thead><tbody>"
        if data:
            for row in data:
                table_html += f"<tr><td>{row['day']}</td><td>{row['dest']}</td><td>{row['sms_count']}</td></tr>"
        else:
            table_html += "<tr><td colspan='3'>No SMS records found.</td></tr>"
        table_html += "</tbody></table>"
        return table_html

    return render_template("dashboard.html", summary_data=data, username=session.get("username"), show_section="report", total=len(data), per_page=5)

# ----------------------------
# Templates CRUD
# ----------------------------
@app.route("/templates")
@login_required
def templates():
    search = request.args.get("search", "")
    page = int(request.args.get("page", 1))
    per_page = 5
    offset = (page - 1) * per_page

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    base_query = "FROM templates WHERE user_id=%s"
    params = [session["user_id"]]

    if search:
        base_query += " AND (name LIKE %s OR dlt_template_id LIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])

    cursor.execute("SELECT COUNT(*) as total " + base_query, tuple(params))
    total = cursor.fetchone()["total"]

    cursor.execute(
        "SELECT * " + base_query + " ORDER BY id DESC LIMIT %s OFFSET %s",
        tuple(params + [per_page, offset])
    )
    data = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template(
        "dashboard.html",
        templates=data,
        total=total,
        page=page,
        per_page=per_page,
        search=search,
        username=session.get("username"),
        show_section="template-section"
    )

@app.route("/templates/create", methods=["POST"])
@login_required
def create_template():
    name = request.form.get("name")
    content = request.form.get("content")
    dlt_id = generate_dlt_id()  # 10-digit starting with 212

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO templates (user_id, name, content, dlt_template_id) VALUES (%s,%s,%s,%s)",
        (session["user_id"], name, content, dlt_id)
    )
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for("templates"))

@app.route("/templates/update/<int:id>", methods=["POST"])
@login_required
def update_template(id):
    name = request.form.get("name")
    content = request.form.get("content")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE templates SET name=%s, content=%s WHERE id=%s AND user_id=%s",
        (name, content, id, session["user_id"])
    )
    conn.commit()
    cursor.close()
    conn.close()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({
            "status": "success",
            "message": "Template updated",
            "id": id,
            "name": name,
            "content": content
        })
    return redirect(url_for("templates"))

@app.route("/templates/delete/<int:id>", methods=["POST"])
@login_required
def delete_template(id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM templates WHERE id=%s AND user_id=%s", (id, session["user_id"]))
    conn.commit()
    cursor.close()
    conn.close()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"status": "success", "message": "Template deleted", "id": id})
    return redirect(url_for("templates"))

# ----------------------------
# Health & Server
# ----------------------------
@app.route("/health")
def health():
    return "OK", 200

@app.route("/server")
def server():
    return f"Served from: {socket.gethostname()}"

# ----------------------------
# No Cache
# ----------------------------
@app.after_request
def no_cache(res):
    res.headers["Cache-Control"] = "no-store"
    return res

# ----------------------------
# Run App
# ----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)