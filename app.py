from flask import Flask, render_template, request, redirect, session, flash, jsonify
from plyer import notification
import sqlite3
import os
import threading
import webview
import time
import uuid
import requests

# ================= GLOBAL =================
CURRENT_MACHINE_ID = None

# ================= CONFIG =================
AMS_URL = "https://ams.settribe.com"
SERVER_URL = "https://ams-application.onrender.com"
APP_NAME = "SETTribe"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_ICON = os.path.join(BASE_DIR, "settribe.ico")

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

# 👉 SEND
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

        if len(notifications_queue) > 50:
            notifications_queue.pop(0)

        return jsonify({"status": "queued"})

    return jsonify({"status": "invalid_data"}), 400


# 👉 GET
@app.route('/api/get_notifications')
def api_get():
    machine_id = request.args.get('machine_id')

    my_notes = [
        n for n in notifications_queue
        if n['target_machine'] == machine_id or n['target_machine'] == "ALL"
    ]

    return jsonify(my_notes)

# ================= LOGIN =================
@app.route('/', methods=['GET', 'POST'])
def login():
    global CURRENT_MACHINE_ID

    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']
        machine_id = request.form.get('machine_id')

        db = get_db()
        cur = db.cursor()

        cur.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = cur.fetchone()

        if user:
            # ✅ Save machine_id
            cur.execute("UPDATE users SET machine_id=? WHERE username=?", (machine_id, username))
            db.commit()

            session['user'] = username
            session['machine_id'] = machine_id

            CURRENT_MACHINE_ID = machine_id

            db.close()

            # 🔔 Send notification ONLY to this machine
            try:
                requests.post(
                    f"{SERVER_URL}/api/send_notification",
                    json={
                        "target_machine": machine_id,
                        "title": "Login Successful",
                        "message": f"Hi {username}, welcome!"
                    },
                    timeout=5
                )
            except Exception as e:
                print("Send Error:", e)

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

    while True:
        try:
            if not CURRENT_MACHINE_ID:
                time.sleep(2)
                continue

            response = requests.get(
                f"{SERVER_URL}/api/get_notifications?machine_id={CURRENT_MACHINE_ID}",
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
            print("Sync Error:", e)

        time.sleep(5)

# ================= RUN =================
def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

if __name__ == "__main__":
    init_db()

    # Flask thread
    t1 = threading.Thread(target=run_flask, daemon=True)
    t1.start()

    # Listener thread
    t2 = threading.Thread(target=notification_listener, daemon=True)
    t2.start()

    time.sleep(2)

    send_desktop_notification("SETTribe", "System Ready")

    webview.create_window("SETTribe AMS Portal", AMS_URL, width=1200, height=800)
    webview.start(gui="edgechromium")