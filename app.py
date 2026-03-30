from flask import Flask, render_template, request, redirect, session, flash, jsonify
from plyer import notification
import sqlite3
import os
import threading
import webview
import time
import uuid
import requests
import socket

# ================= CONFIG & PATHS =================
AMS_URL = "https://ams.settribe.com"
SERVER_URL = "https://ams-application.onrender.com"
APP_NAME = "SETTribe"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_ICON = os.path.join(BASE_DIR, "settribe.ico")
ID_FILE = os.path.join(BASE_DIR, "machine_id.txt")

# ================= UNIQUE MACHINE ID LOGIC =================
def get_unique_machine_id():
    """प्रत्येक मशीनसाठी एक कायमस्वरूपी युनिक आयडी जनरेट किंवा रीड करतो."""
    if os.path.exists(ID_FILE):
        with open(ID_FILE, "r") as f:
            return f.read().strip()
    else:
        # नवीन आयडी तयार करा (उदा: ST-a1b2c3d4)
        new_id = f"ST-{str(uuid.uuid4())[:8]}"
        with open(ID_FILE, "w") as f:
            f.write(new_id)
        return new_id

MY_MACHINE_ID = get_unique_machine_id()
print(f"--- SYSTEM READY ---")
print(f"Machine ID: {MY_MACHINE_ID}")
print(f"Hostname: {socket.gethostname()}")

# ================= WINDOWS FIX =================
if os.name == "nt":
    try:
        import ctypes
        myappid = 'settribe.ams.app'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception as e:
        print("AppID Error:", e)

# ================= MEMORY STORAGE =================
notifications_queue = []

# ================= FLASK =================
app = Flask(__name__)
app.secret_key = "settribe_secure_key_123"

# ================= DB =================
def get_db():
    return sqlite3.connect("app.db")

def init_db():
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            password TEXT,
            machine_id TEXT
        )
    """)
    db.commit()
    db.close()

# ================= DESKTOP NOTIFICATION =================
def send_desktop_notification(title, message):
    print(f"Showing Notification: {title} - {message}")
    try:
        icon_path = APP_ICON if os.path.exists(APP_ICON) else None
        notification.notify(
            title=title,
            message=message,
            app_name=APP_NAME,
            app_icon=icon_path,
            timeout=10
        )
    except Exception as e:
        print("Notification Error:", e)

# ================= API =================

@app.route('/api/send_notification', methods=['POST'])
def api_send():
    data = request.get_json()
    if not data:
        return jsonify({"status": "no data"}), 400

    title = data.get("title")
    message = data.get("message")
    target = data.get("target_machine", "ALL")

    if title and message:
        new_event = {
            "id": str(uuid.uuid4()),
            "target_machine": target,
            "title": title,
            "message": message,
            "timestamp": time.time()
        }
        notifications_queue.append(new_event)
        
        # जास्तीत जास्त ५० मेसेज मेमरीमध्ये ठेवा
        if len(notifications_queue) > 50:
            notifications_queue.pop(0)

        return jsonify({"status": "queued", "machine_target": target})
    return jsonify({"status": "invalid_data"}), 400

@app.route('/api/get_notifications')
def api_get():
    machine_id = request.args.get('machine_id')
    # फक्त या मशीनसाठी किंवा 'ALL' साठी असलेले मेसेज फिल्टर करा
    my_notes = [
        n for n in notifications_queue
        if n['target_machine'] == machine_id or n['target_machine'] == "ALL"
    ]
    return jsonify(my_notes)

# ================= LOGIN =================
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        cur = db.cursor()

        cur.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = cur.fetchone()

        if user:
            session['user'] = username

            # ✅ युनिक मशीन आयडी डेटाबेसमध्ये सेव्ह करा
            cur.execute("UPDATE users SET machine_id=? WHERE username=?",
                        (MY_MACHINE_ID, username))
            db.commit()
            db.close()

            # 🔔 फक्त याच मशीनला लॉगिन नोटिफिकेशन पाठवा
            try:
                requests.post(
                    f"{SERVER_URL}/api/send_notification",
                    json={
                        "target_machine": MY_MACHINE_ID,
                        "title": "Login Successful",
                        "message": f"Hi {username}, welcome to SETTribe on {MY_MACHINE_ID}!"
                    },
                    timeout=5
                )
            except Exception as e:
                print("API Send Error:", e)

            return redirect('/home')
        else:
            flash("Invalid Credentials")
            db.close()

    return render_template("login.html")

@app.route('/home')
def home():
    if 'user' not in session:
        return redirect('/')
    return render_template("index.html")

# ================= LISTENER =================
def notification_listener():
    processed_ids = set()
    print(f"Listener started for Machine ID: {MY_MACHINE_ID}")

    while True:
        try:
            # सर्व्हरकडून या मशीनचे नोटिफिकेशन्स ओढा (Pull)
            response = requests.get(
                f"{SERVER_URL}/api/get_notifications?machine_id={MY_MACHINE_ID}",
                timeout=5
            )

            if response.status_code == 200:
                server_notes = response.json()
                for note in server_notes:
                    n_id = note.get("id")
                    if n_id not in processed_ids:
                        send_desktop_notification(note['title'], note['message'])
                        processed_ids.add(n_id)
        except Exception as e:
            pass # नेट नसेल तर एरर प्रिंट टाळा किंवा लॉग करा

        time.sleep(5)

# ================= RUN =================
def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

if __name__ == "__main__":
    init_db()

    # Flask background thread
    threading.Thread(target=run_flask, daemon=True).start()

    # Listener background thread
    threading.Thread(target=notification_listener, daemon=True).start()

    time.sleep(2)
    send_desktop_notification("SETTribe", f"ID: {MY_MACHINE_ID} is Online")

    webview.create_window("SETTribe AMS Portal", AMS_URL, width=1200, height=800)
    webview.start(gui="edgechromium")