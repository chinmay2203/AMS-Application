from flask import Flask, render_template, request, redirect, session, flash, jsonify
from plyer import notification
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import sys
import threading
import webview
import time
import uuid
import requests

# ================= CONFIG & PATHS (.EXE FIX) =================
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    ASSET_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    ASSET_DIR = BASE_DIR

APP_ICON = os.path.join(ASSET_DIR, "settribe.ico")
ID_FILE = os.path.join(BASE_DIR, "machine_id.txt")

AMS_URL = "http://127.0.0.1:5000/"
SERVER_URL = "https://ams-application.onrender.com"
APP_NAME = "SETTribe"

# ================= REMOTE POSTGRESQL CONFIG (RENDER) =================
DATABASE_URL = os.environ.get(
    "DATABASE_URL", 
    "postgresql://settribe_db_user:zi7Q6A4IbbztiL1u9Ab6uDcmfAFfEbyg@dpg-d75q35h5pdvs73ae1ucg-a.oregon-postgres.render.com/settribe_db"
)

def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        return conn
    except Exception as e:
        print(f"--- DATABASE CONNECTION ERROR --- \n{e}")
        return None

def init_db():
    conn = get_db_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                machine_id TEXT
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("Database Initialized Successfully.")

# ================= UNIQUE MACHINE ID =================
def get_unique_machine_id():
    if os.path.exists(ID_FILE):
        with open(ID_FILE, "r") as f:
            return f.read().strip()
    else:
        new_id = f"ST-{str(uuid.uuid4())[:8]}"
        with open(ID_FILE, "w") as f:
            f.write(new_id)
        return new_id

MY_MACHINE_ID = get_unique_machine_id()

# ================= WINDOWS FIX =================
if os.name == "nt":
    try:
        import ctypes
        myappid = 'settribe.ams.app'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception as e:
        print("AppID Error:", e)

# ================= NOTIFICATIONS QUEUE =================
notifications_queue = []

# ================= FLASK APP =================
app = Flask(__name__, 
            template_folder=os.path.join(ASSET_DIR, 'templates'),
            static_folder=os.path.join(ASSET_DIR, 'static') if os.path.exists(os.path.join(ASSET_DIR, 'static')) else None)
app.secret_key = "settribe_secure_key_123"

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

# ================= API ROUTES =================
@app.route('/api/send_notification', methods=['POST'])
def api_send():
    data = request.get_json()
    if not data: return jsonify({"status": "no data"}), 400

    new_event = {
        "id": str(uuid.uuid4()),
        "target_machine": data.get("target_machine", "ALL"),
        "title": data.get("title", "No Title"),
        "message": data.get("message", "No Message"),
        "timestamp": time.time()
    }
    notifications_queue.append(new_event)
    if len(notifications_queue) > 50: notifications_queue.pop(0)
    return jsonify({"status": "queued"})

@app.route('/api/get_notifications')
def api_get():
    machine_id = request.args.get('machine_id')
    my_notes = [n for n in notifications_queue if n['target_machine'] in [machine_id, "ALL"]]
    return jsonify(my_notes)

# ================= LOGIN & AUTO-SAVE LOGIC =================
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        if not conn:
            flash("Database Connection Failed!")
            return render_template("login.html")

        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cur.fetchone()

        if user:
            if user['password'] == password:
                session['user'] = username
                cur.execute("UPDATE users SET machine_id=%s WHERE username=%s", (MY_MACHINE_ID, username))
                conn.commit()
            else:
                flash("Invalid Password")
                cur.close()
                conn.close()
                return render_template("login.html")
        else:
            cur.execute("INSERT INTO users (username, password, machine_id) VALUES (%s, %s, %s)", 
                        (username, password, MY_MACHINE_ID))
            conn.commit()
            session['user'] = username

        # Login Notification
        try:
            requests.post(f"{SERVER_URL}/api/send_notification", json={
                "target_machine": MY_MACHINE_ID,
                "title": "Login Alert",
                "message": f"Welcome {username}! Your Device is Registered."
            }, timeout=3)
        except: 
            pass

        cur.close()
        conn.close()
        return redirect('/home')

    return render_template("login.html")

@app.route('/home')
def home():
    if 'user' not in session: return redirect('/')
    return render_template("index.html")

# ================= BACKGROUND THREADS =================
def notification_listener():
    processed_ids = set()
    while True:
        try:
            response = requests.get(f"{SERVER_URL}/api/get_notifications?machine_id={MY_MACHINE_ID}", timeout=5)
            if response.status_code == 200:
                for note in response.json():
                    if note['id'] not in processed_ids:
                        send_desktop_notification(note['title'], note['message'])
                        processed_ids.add(note['id'])
        except: 
            pass
        time.sleep(5)

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)

# ================= MAIN EXECUTION =================
if __name__ == "__main__":
    init_db()
    
    if not os.environ.get("RENDER"):
        threading.Thread(target=run_flask, daemon=True).start()
        threading.Thread(target=notification_listener, daemon=True).start()
        
        time.sleep(2)
        send_desktop_notification("SETTribe", f"System Online | ID: {MY_MACHINE_ID}")
        
        webview.create_window("SETTribe AMS Portal", AMS_URL, width=1200, height=800)
        webview.start(gui="edgechromium")
    else:
        run_flask()