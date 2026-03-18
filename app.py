from flask import Flask, render_template, request, redirect, session, flash, jsonify
from plyer import notification
import sqlite3
import os
import threading
import webview
import time
import uuid
import requests
import ctypes  


try:
    myappid = 'settribe ams' 
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception as e:
    print("AppID Error:", e)

# ================= CONFIG =================

AMS_URL = "https://ams.settribe.com"
SERVER_URL = "https://ams-application.onrender.com"

APP_NAME = "SETTribe" 

# absolute icon path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_ICON = os.path.join(BASE_DIR, "settribe.ico")

# ================= GLOBAL STORAGE =================

latest_notification = {
    "title": "System Ready",
    "message": "Notification Service Started"
}

# ================= DESKTOP NOTIFICATION =================

def send_notification(title, message):
    print("Notification:", title, message)

    try:
        icon_path = APP_ICON if os.path.exists(APP_ICON) else None

        notification.notify(
            title=title,
            message=message,
            app_name=APP_NAME,  
            app_icon=icon_path,
            timeout=10
        )
        return True

    except Exception as e:
        print("Notification Error:", e)
        return False


# ================= APP =================

app = Flask(__name__)
app.secret_key = "secret123"

UPLOAD_FOLDER = "uploads"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ================= DATABASE =================

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
    token TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS uploads(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT,
    uploaded_by TEXT
    )
    """)
    db.commit()
    db.close()

# ================= API SEND =================

@app.route('/api/send_notification', methods=['POST'])
def api_send():
    global latest_notification
    data = request.get_json()

    if not data:
        return jsonify({"status": "no data"})

    title = data.get("title", "")
    message = data.get("message", "")

    if title and message:
        latest_notification["title"] = title
        latest_notification["message"] = message

        if send_notification(title, message):
            return jsonify({"status": "sent"})
        else:
            return jsonify({"status": "failed"})

    return jsonify({"status": "invalid"})


# ================= API GET =================

@app.route('/api/get_notification')
def api_get():
    return jsonify(latest_notification)


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
            token = str(uuid.uuid4())
            cur.execute("UPDATE users SET token=? WHERE username=?", (token, username))
            db.commit()
            db.close()

            session['user'] = username

            send_notification("SETTribe Login", f"Hi {username}, Welcome")

            try:
                requests.post(
                    f"{SERVER_URL}/api/send_notification",
                    json={
                        "title": "SETTribe Login",
                        "message": f"Hi {username}, Welcome"
                    }
                )
            except Exception as e:
                print("API Error:", e)

            return redirect('/home')
        else:
            flash("Invalid Login")
            db.close()

    return render_template("login.html")


# ================= HOME =================

@app.route('/home')
def home():
    if 'user' not in session:
        return redirect('/')
    return render_template("index.html")


# ================= CLIENT LISTENER =================

def notification_client():
    last = ""
    while True:
        try:
            r = requests.get(f"{SERVER_URL}/api/get_notification")
            data = r.json()
            title = data.get("title", "")
            message = data.get("message", "")

            if title and message:
                msg = f"{title}|{message}"
                if msg != last:
                    last = msg
                    send_notification(title, message)
        except Exception as e:
            print("Listener Error:", e)
        
        time.sleep(3)


# ================= RUN FLASK =================

def run_flask():
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


# ================= MAIN =================

if __name__ == "__main__":
    init_db()

    t1 = threading.Thread(target=run_flask)
    t1.daemon = True
    t1.start()

    t2 = threading.Thread(target=notification_client)
    t2.daemon = True
    t2.start()

    time.sleep(2)

    send_notification("SETTribe", "Application Started")

    webview.create_window(
        "SETTribe AMS Portal",
        AMS_URL,
        width=1200,
        height=800
    )
    webview.start(gui="edgechromium")