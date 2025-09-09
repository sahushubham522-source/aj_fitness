# AJ Fitness Web App - app.py (PostgreSQL with old schema consistency)

from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
import os, shutil, csv
from datetime import datetime, date, timedelta
from werkzeug.utils import secure_filename
import psycopg2
import psycopg2.extras

app = Flask(__name__)
app.secret_key = 'ajfitnesssecret'
UPLOAD_FOLDER = 'static/images'
BACKUP_FOLDER = 'backups'
EXPORT_FOLDER = 'exports'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(EXPORT_FOLDER, exist_ok=True)
os.makedirs(BACKUP_FOLDER, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL")

# Normalize for psycopg2
if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgres://", 1)

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

# ------------------- AUTH -------------------

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == 'ARajput2025' and request.form['password'] == 'Test123!':
            session['admin'] = True
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ------------------- DASHBOARD -------------------

@app.route('/dashboard')
def dashboard():
    if not session.get('admin'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    search = request.args.get('search', '').strip()
    if search:
        cur.execute("SELECT * FROM members WHERE name ILIKE %s", (f"%{search}%",))
    else:
        cur.execute("SELECT * FROM members")
    members = cur.fetchall()

    today = date.today()
    today_str = today.isoformat()

    cur.execute("SELECT COUNT(*) FROM members WHERE start_date = %s", (today_str,))
    new_joins = cur.fetchone()["count"]

    cur.execute("SELECT COUNT(*) FROM fees WHERE date = %s", (today_str,))
    new_payments = cur.fetchone()["count"]

    cur.execute("""
        SELECT COUNT(*) FROM members 
        WHERE end_date <= (CURRENT_DATE + INTERVAL '3 days') 
          AND end_date >= CURRENT_DATE
    """)
    expiring_soon = cur.fetchone()["count"]

    cur.execute("""
        SELECT * FROM members
        WHERE end_date BETWEEN (CURRENT_DATE - INTERVAL '3 days') AND (CURRENT_DATE + INTERVAL '2 days')
        ORDER BY end_date
    """)
    expiry_alerts = cur.fetchall()

    updated_members = []
    for m in members:
        m['expiring'] = (m['end_date'] <= (today + timedelta(days=3)))
        cur.execute("SELECT date FROM fees WHERE member_id = %s ORDER BY date DESC LIMIT 1", (m['id'],))
        last_fee = cur.fetchone()
        if last_fee:
            last_fee_date = last_fee["date"]
            m['overdue'] = (today - last_fee_date).days > 30
        else:
            m['overdue'] = True
        updated_members.append(m)

    cur.close()
    conn.close()
    return render_template(
        'dashboard.html',
        members=updated_members,
        new_joins=new_joins,
        new_payments=new_payments,
        expiring_soon=expiring_soon,
        expiry_alerts=expiry_alerts
    )

# ------------------- MEMBERS -------------------

@app.route('/delete-member/<int:member_id>', methods=['POST'])
def delete_member(member_id):
    if not session.get('admin'):
        return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM fees WHERE member_id = %s", (member_id,))
    cur.execute("DELETE FROM members WHERE id = %s", (member_id,))
    conn.commit()
    cur.close()
    conn.close()
    flash('Member deleted successfully.')
    return redirect(url_for('dashboard'))

@app.route('/add-member', methods=['GET', 'POST'])
def add_member():
    if request.method == 'POST':
        try:
            name = request.form['name'].strip()
            phone = request.form['phone'].strip()
            start_date = request.form['start_date']
            end_date = request.form['end_date']
            fee_amount = request.form['fee_amount']
            fee_date = request.form['fee_date']

            if not name or not phone or not start_date or not end_date:
                flash("Please fill all required fields", "error")
                return redirect(url_for('add_member'))

            photo_file = request.files['photo']
            filename = None
            if photo_file and photo_file.filename != '':
                filename = secure_filename(photo_file.filename)
                photo_file.save(os.path.join(UPLOAD_FOLDER, filename))

            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO members (name, phone, photo, start_date, end_date) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (name, phone, filename, start_date, end_date)
            )
            member_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO fees (member_id, amount, date) VALUES (%s, %s, %s)",
                (member_id, fee_amount, fee_date)
            )
            conn.commit()
            cur.close()
            conn.close()

            flash("Member added successfully!", "success")
            return redirect(url_for('dashboard'))

        except Exception as e:
            flash(f"Error adding member: {e}", "error")
            return redirect(url_for('add_member'))

    return render_template('add_member.html', today=date.today().isoformat())

# ------------------- FEES -------------------

@app.route('/record-fee/<int:member_id>', methods=['GET', 'POST'])
def record_fee(member_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM members WHERE id = %s", (member_id,))
    member = cur.fetchone()

    if request.method == 'POST':
        amount = request.form['amount']
        date_paid = request.form['date']
        cur.execute("INSERT INTO fees (member_id, amount, date) VALUES (%s, %s, %s)",
                    (member_id, amount, date_paid))
	# Update/override member expiry date
    	cur.execute("""
        UPDATE members SET end_date = %s WHERE id = %s
    	""", (new_end_date, member_id))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('dashboard'))

    cur.close()
    conn.close()
    return render_template('record_fee.html', member=member, current_date=date.today().isoformat())

@app.route('/fee-history/<int:member_id>')
def fee_history(member_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM members WHERE id = %s", (member_id,))
    member = cur.fetchone()
    cur.execute("SELECT * FROM fees WHERE member_id = %s ORDER BY date DESC", (member_id,))
    history = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('fee_history.html', member=member, history=history)

@app.route('/print-receipt/<int:fee_id>')
def print_receipt(fee_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM fees WHERE id = %s", (fee_id,))
    fee = cur.fetchone()
    cur.execute("SELECT * FROM members WHERE id = %s", (fee['member_id'],))
    member = cur.fetchone()
    cur.close()
    conn.close()
    return render_template('print_receipt.html', fee=fee, member=member)

# ------------------- EXPORT -------------------

@app.route('/export/members')
def export_members():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM members")
    members = cur.fetchall()

    file_path = os.path.join(EXPORT_FOLDER, 'members.csv')
    with open(file_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['ID', 'Name', 'Phone', 'Start Date', 'End Date', 'Total Fee Paid'])

        for m in members:
            cur.execute("SELECT SUM(amount) as total FROM fees WHERE member_id = %s", (m['id'],))
            total_fee = cur.fetchone()["total"]

            writer.writerow([
                m['id'], m['name'], m['phone'], m['start_date'], m['end_date'],
                total_fee if total_fee else 0
            ])

    cur.close()
    conn.close()
    return send_file(file_path, as_attachment=True)

@app.route('/export/fees')
def export_fees():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM fees")
    fees = cur.fetchall()

    file_path = os.path.join(EXPORT_FOLDER, 'fees.csv')
    with open(file_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['ID', 'Member ID', 'Amount', 'Date'])
        for f in fees:
            writer.writerow([f['id'], f['member_id'], f['amount'], f['date']])

    cur.close()
    conn.close()
    return send_file(file_path, as_attachment=True)

# ------------------- MAIN -------------------

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
