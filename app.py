import os
import psycopg2
from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
from datetime import datetime

app = Flask(__name__)
app.secret_key = "supersecretkey"  # replace with env var later

# ✅ Database connection
def get_db_connection():
    DATABASE_URL = os.environ.get("DATABASE_URL")

    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable not set")

    # psycopg2 expects 'postgresql://' instead of 'postgres://'
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

    conn = psycopg2.connect(DATABASE_URL)
    return conn

# ---------------- ROUTES ---------------- #

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == "ARajput2025" and password == "Test123!":
            session["user"] = username
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password", "danger")
    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, phone, fee, expiry_date FROM members ORDER BY id DESC")
    members = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("dashboard.html", members=members)


@app.route("/add_member", methods=["GET", "POST"])
def add_member():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form["name"]
        phone = request.form["phone"]
        fee = request.form["fee"]
        expiry_date = request.form["expiry_date"]

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO members (name, phone, fee, expiry_date) VALUES (%s, %s, %s, %s)",
            (name, phone, fee, expiry_date),
        )
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for("dashboard"))

    return render_template("add_member.html")


@app.route("/record_fee/<int:member_id>", methods=["GET", "POST"])
def record_fee(member_id):
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM members WHERE id = %s", (member_id,))
    member = cur.fetchone()

    if not member:
        cur.close()
        conn.close()
        flash("Member not found", "danger")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        amount = request.form["amount"]
        date = request.form["date"]
        new_expiry = request.form["expiry_date"]

        # Insert into fee history
        cur.execute(
            "INSERT INTO fees (member_id, amount, date) VALUES (%s, %s, %s)",
            (member_id, amount, date),
        )

        # Update expiry date in members table
        cur.execute(
            "UPDATE members SET expiry_date = %s WHERE id = %s",
            (new_expiry, member_id),
        )

        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for("dashboard"))

    cur.close()
    conn.close()
    current_date = datetime.now().strftime("%Y-%m-%d")
    return render_template("record_fee.html", member={"id": member[0], "name": member[1]}, current_date=current_date)


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))


# ------------- RUN APP ---------------- #
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render will set PORT
    app.run(host="0.0.0.0", port=port, debug=True)
