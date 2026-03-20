from flask import Flask, render_template, request, redirect, session, flash
from plyer import notification
import ctypes
import sqlite3
import os
import threading
import webview
import time
import uuid
import requests

# ================= WINDOWS APP NAME FIX =================

try:
    myappid = 'settribe.ams.app'  # unique app id
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception as e:
    print("AppID Error:", e)

# ================= CONFIG =================

SERVER_URL = "https://ams-application.onrender.com"
AMS_URL = "https://ams.settribe.com"
APP_NAME = "SETTribe"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_ICON = os.path.join(BASE_DIR, "settribe.ico")

# ================= DEVICE ID =================

DEVICE_FILE = "device_id.txt"

def get_device_id():
    if os.path.exists(DEVICE_FILE):
        with open(DEVICE_FILE, "r") as f:
            return f.read().strip()
    else:
        new_id = str(uuid.uuid4())
        with open(DEVICE_FILE, "w") as f:
            f.write(new_id)
        return new_id

MY_DEVICE_ID = get_device_id()

# ================= NOTIFICATION =================

def send_desktop_notification(title, message):
    try:
        notification.notify(
            title=title,
            message=message,
            app_name=APP_NAME,
            app_icon=APP_ICON if os.path.exists(APP_ICON) else None,
            timeout=10
        )
    except Exception as e:
        print("Notification Error:", e)

# ================= FLASK =================

app = Flask(__name__)
app.secret_key = "secret123"

def get_db():
    return sqlite3.connect("app.db")

def init_db():
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            password TEXT
        )
    """)
    db.commit()
    db.close()

# ================= ROUTES =================

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        cur = db.cursor()

        cur.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = cur.fetchone()
        db.close()

        if user:
            session['user'] = username

            # 🔥 Send notification to THIS device
            try:
                response = requests.post(
                    f"{SERVER_URL}/api/send_notification",
                    json={
                        "target_machine": MY_DEVICE_ID,
                        "title": "Login Successful",
                        "message": f"Hi {username}, welcome!"
                    },
                    timeout=5
                )
                print("Server Response:", response.status_code)

            except Exception as e:
                print("Server Error:", e)

            return redirect('/home')
        else:
            flash("Invalid Credentials")

    return render_template("login.html")

@app.route('/home')
def home():
    if 'user' not in session:
        return redirect('/')
    return render_template("index.html")

# ================= LISTENER =================

def notification_listener():
    shown_ids = set()

    while True:
        try:
            res = requests.get(
                f"{SERVER_URL}/api/get_notifications",
                params={"machine_id": MY_DEVICE_ID},
                timeout=5
            )

            if res.status_code == 200:
                notes = res.json()

                for n in notes:
                    if n["id"] not in shown_ids:
                        send_desktop_notification(n["title"], n["message"])
                        shown_ids.add(n["id"])

        except Exception as e:
            print("Sync Error:", e)

        time.sleep(5)

# ================= RUN =================

def run_flask():
    app.run(port=5000, debug=False, use_reloader=False)

if __name__ == "__main__":
    init_db()

    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=notification_listener, daemon=True).start()

    time.sleep(2)
    send_desktop_notification("SETTribe", f"System Ready\nDevice: {MY_DEVICE_ID[:8]}")

    webview.create_window("SETTribe AMS Portal", AMS_URL, width=1200, height=800)
    webview.start()