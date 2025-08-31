# AJ Fitness Desktop App - app.py

from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
import sqlite3, os, shutil, csv
from datetime import datetime, date, timedelta
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'ajfitnesssecret'
UPLOAD_FOLDER = 'static/images'
DB_PATH = 'database/aj_fitness.db'
BACKUP_FOLDER = 'backups'
EXPORT_FOLDER = 'exports'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(EXPORT_FOLDER, exist_ok=True)
os.makedirs(BACKUP_FOLDER, exist_ok=True)
os.makedirs('database', exist_ok=True)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    with open('init.sql', 'r') as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == 'ARajput2025' and request.form['password'] == 'Test123!':
            session['admin'] = True
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if not session.get('admin'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    search = request.args.get('search', '').strip()

    if search:
        members = conn.execute("SELECT * FROM members WHERE name LIKE ?", ('%' + search + '%',)).fetchall()
    else:
        members = conn.execute("SELECT * FROM members").fetchall()

    today = date.today()
    today_str = today.isoformat()

    new_joins = conn.execute("SELECT COUNT(*) FROM members WHERE start_date = ?", (today_str,)).fetchone()[0]
    new_payments = conn.execute("SELECT COUNT(*) FROM fees WHERE date = ?", (today_str,)).fetchone()[0]
    expiring_soon = conn.execute("SELECT COUNT(*) FROM members WHERE end_date <= date('now', '+3 days') AND end_date >= date('now')").fetchone()[0]

    # New: Select members with expiry between -3 and +2 days
    expiry_alerts = conn.execute("""
        SELECT * FROM members
        WHERE end_date BETWEEN date('now', '-3 day') AND date('now', '+2 day')
        ORDER BY end_date
    """).fetchall()

    updated_members = []
    for m in members:
        m = dict(m)
        m['expiring'] = (m['end_date'] <= (today + timedelta(days=3)).isoformat())
        last_fee = conn.execute("SELECT date FROM fees WHERE member_id = ? ORDER BY date DESC LIMIT 1", (m['id'],)).fetchone()
        if last_fee:
            last_fee_date = datetime.strptime(last_fee['date'], "%Y-%m-%d").date()
            m['overdue'] = (today - last_fee_date).days > 30
        else:
            m['overdue'] = True
        updated_members.append(m)

    conn.close()
    return render_template(
        'dashboard.html',
        members=updated_members,
        new_joins=new_joins,
        new_payments=new_payments,
        expiring_soon=expiring_soon,
        expiry_alerts=expiry_alerts
    )

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/delete-member/<int:member_id>', methods=['POST'])
def delete_member(member_id):
    if not session.get('admin'):
        return redirect(url_for('login'))
    conn = get_db_connection()
    # Delete fees first (foreign key constraint)
    conn.execute("DELETE FROM fees WHERE member_id = ?", (member_id,))
    # Delete member
    conn.execute("DELETE FROM members WHERE id = ?", (member_id,))
    conn.commit()
    conn.close()
    flash('Member deleted successfully.')
    return redirect(url_for('dashboard'))


@app.route('/add-member', methods=['GET', 'POST'])
def add_member():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        fee_amount = request.form['fee_amount']
        fee_date = request.form['fee_date']
        photo = request.files['photo']

        filename = None
        if photo:
            filename = secure_filename(photo.filename)
            photo.save(os.path.join(UPLOAD_FOLDER, filename))

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO members (name, phone, photo, start_date, end_date) VALUES (?, ?, ?, ?, ?)",
                    (name, phone, filename, start_date, end_date))
        member_id = cur.lastrowid
        cur.execute("INSERT INTO fees (member_id, amount, date) VALUES (?, ?, ?)",
                    (member_id, fee_amount, fee_date))
        conn.commit()
        conn.close()
        return redirect(url_for('dashboard'))

    return render_template('add_member.html', today=date.today().isoformat())

@app.route('/record-fee/<int:member_id>', methods=['GET', 'POST'])
def record_fee(member_id):
    conn = get_db_connection()
    member = conn.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone()
    if request.method == 'POST':
        amount = request.form['amount']
        date_paid = request.form['date']
        conn.execute("INSERT INTO fees (member_id, amount, date) VALUES (?, ?, ?)", (member_id, amount, date_paid))
        conn.commit()
        conn.close()
        return redirect(url_for('dashboard'))

    return render_template('record_fee.html', member=member, current_date=date.today().isoformat())

@app.route('/fee-history/<int:member_id>')
def fee_history(member_id):
    conn = get_db_connection()
    member = conn.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone()
    history = conn.execute("SELECT * FROM fees WHERE member_id = ? ORDER BY date DESC", (member_id,)).fetchall()
    conn.close()
    return render_template('fee_history.html', member=member, history=history)

@app.route('/print-receipt/<int:fee_id>')
def print_receipt(fee_id):
    conn = get_db_connection()
    fee = conn.execute("SELECT * FROM fees WHERE id = ?", (fee_id,)).fetchone()
    member = conn.execute("SELECT * FROM members WHERE id = ?", (fee['member_id'],)).fetchone()
    conn.close()
    return render_template('print_receipt.html', fee=fee, member=member)

@app.route('/backup')
def backup():
    if not session.get('admin'):
        return redirect(url_for('login'))
    now = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = os.path.join(BACKUP_FOLDER, f"backup_{now}.db")
    shutil.copy(DB_PATH, backup_file)
    return send_file(backup_file, as_attachment=True)

@app.route('/export/members')
def export_members():
    conn = get_db_connection()
    members = conn.execute('SELECT * FROM members').fetchall()

    file_path = os.path.join(EXPORT_FOLDER, 'members.csv')
    with open(file_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        # Add Total Fee column
        writer.writerow(['ID', 'Name', 'Phone', 'Start Date', 'End Date', 'Total Fee Paid'])

        for m in members:
            # Get total fee for this member
            total_fee = conn.execute(
                "SELECT SUM(amount) as total FROM fees WHERE member_id = ?",
                (m['id'],)
            ).fetchone()['total']

            writer.writerow([
                m['id'], m['name'], m['phone'], m['start_date'], m['end_date'],
                total_fee if total_fee else 0
            ])

    conn.close()
    return send_file(file_path, as_attachment=True)


@app.route('/export/fees')
def export_fees():
    conn = get_db_connection()
    fees = conn.execute('SELECT * FROM fees').fetchall()
    file_path = os.path.join(EXPORT_FOLDER, 'fees.csv')
    with open(file_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['ID', 'Member ID', 'Amount', 'Date'])
        for f in fees:
            writer.writerow([f['id'], f['member_id'], f['amount'], f['date']])
    conn.close()
    return send_file(file_path, as_attachment=True)

if __name__ == '__main__':
    if not os.path.exists(DB_PATH):
        init_db()
    app.run(debug=True)
