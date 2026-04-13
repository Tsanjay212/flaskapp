from flask import Blueprint, render_template, request, redirect, url_for, flash
from credits import update_user_credits, get_user_credits

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/credits', methods=['GET', 'POST'])
def manage_credits():
    if request.method == 'POST':
        user_id = request.form.get("user_id")
        action = request.form.get("action")
        amount = int(request.form.get("amount"))

        # Update credits using the helper function from credits.py
        update_user_credits(user_id, amount, action)

        flash(f"Credits updated for user {user_id}", "success")
        return redirect(url_for('admin.manage_credits'))

    # Fetch all users for displaying the credit management form
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, username, credits FROM users")
    users = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("admin_credits.html", users=users)
