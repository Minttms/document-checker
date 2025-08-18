import os
import sqlite3
import time
from flask_mail import Mail, Message
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'uploads'

# ตั้งค่า Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = "your_email@gmail.com"   # ใส่อีเมลผู้ส่ง
app.config['MAIL_PASSWORD'] = "your_app_password"      # ใส่ App Password
mail = Mail(app)

# ฟังก์ชันสร้างฐานข้อมูล
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        organization TEXT,
        email TEXT,
        filename TEXT,
        status TEXT DEFAULT 'รอตรวจ',
        comment TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT
    )''')
    c.execute("INSERT OR IGNORE INTO admins (id, username, password) VALUES (1, 'admin', 'admin123')")
    conn.commit()
    conn.close()

init_db()

# ----------- หน้าอัปโหลดเอกสาร -----------
@app.route('/', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        name = request.form['name']
        organization = request.form['organization']
        email = request.form['email']
        file = request.files['file']

        if not file or file.filename == '':
            flash('ไม่ได้เลือกไฟล์', 'danger')
            return redirect(request.url)

        # ใช้ secure filename และเพิ่ม timestamp
        filename = secure_filename(file.filename)
        filename = f"{int(time.time())}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file.save(filepath)

        # บันทึกลงฐานข้อมูล
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("INSERT INTO documents (name, organization, email, filename) VALUES (?, ?, ?, ?)",
                  (name, organization, email, filename))
        conn.commit()
        conn.close()

        # ส่งอีเมลแจ้งผู้ตรวจสอบ
        try:
            msg = Message("📄 เอกสารใหม่จากนิสิต",
                          sender=app.config['MAIL_USERNAME'],
                          recipients=["sirinthipmint@gmail.com"])  # อีเมลผู้ตรวจสอบ
            msg.body = f"มีเอกสารใหม่จากนิสิต: {filename}"
            with app.open_resource(filepath) as fp:
                msg.attach(filename, "application/octet-stream", fp.read())
            mail.send(msg)
            flash('ส่งเอกสารเรียบร้อยแล้ว และแจ้งผู้ตรวจสอบแล้ว!', 'success')
        except Exception as e:
            flash(f'ส่งอีเมลไม่สำเร็จ: {e}', 'danger')

        return redirect(request.url)

    return render_template('upload.html')

# ----------- หน้าเข้าสู่ระบบ admin -----------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM admins WHERE username=? AND password=?", (username, password))
        admin = c.fetchone()
        conn.close()
        if admin:
            session['admin'] = username
            return redirect('/admin')
        else:
            flash('เข้าสู่ระบบไม่สำเร็จ', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect('/login')

# ----------- หน้า admin ตรวจเอกสาร -----------
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('admin'):
        return redirect('/login')

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    if request.method == 'POST':
        doc_id = request.form['doc_id']
        status = request.form['status']
        comment = request.form['comment']
        c.execute("UPDATE documents SET status=?, comment=? WHERE id=?", (status, comment, doc_id))
        conn.commit()

        # ส่งอีเมลแจ้งผู้ใช้
        c.execute("SELECT email, filename FROM documents WHERE id=?", (doc_id,))
        doc = c.fetchone()
        if doc:
            to_email = doc[0]
            filename = doc[1]
            subject = "แจ้งผลการตรวจเอกสาร"
            body = f"ไฟล์: {filename}\nสถานะ: {status}\nหมายเหตุ: {comment}"
            try:
                msg = Message(subject, sender=app.config['MAIL_USERNAME'], recipients=[to_email])
                msg.body = body
                mail.send(msg)
            except Exception as e:
                flash(f'ส่งอีเมลไม่สำเร็จ: {e}', 'danger')

    c.execute("SELECT * FROM documents")
    docs = c.fetchall()
    conn.close()
    return render_template('admin.html', documents=docs)

# ----------- ตรวจสอบสถานะเอกสาร -----------
@app.route('/status', methods=['GET', 'POST'])
def status():
    results = []
    if request.method == 'POST':
        name = request.form['name']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM documents WHERE name=?", (name,))
        results = c.fetchall()
        conn.close()
    return render_template('status.html', documents=results)

# ----------- ดาวน์โหลดไฟล์ -----------
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ----------- รันแอป -----------
if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)