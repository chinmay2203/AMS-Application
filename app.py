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
    myappid = 'settribe.ams.app' 
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception as e:
    print("AppID Error:", e)



AMS_URL = "https://ams.settribe.com"
SERVER_URL = "https://ams-application.onrender.com" 
APP_NAME = "SETTribe" 

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_ICON = os.path.join(BASE_DIR, "settribe.ico")


notifications_queue = []

# ================= DESKTOP NOTIFICATION (Local UI) =================

def send_desktop_notification(title, message):
    """स्थानिक मशीनवर नोटिफिकेशन दाखवण्यासाठी"""
    print(f"Displaying: {title} - {message}")
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

# ================= FLASK APP =================

app = Flask(__name__)
app.secret_key = "settribe_secure_key_123"

# ================= DATABASE =================

def get_db():
    return sqlite3.connect("app.db")

def init_db():
    db = get_db()
    cur = db.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, password TEXT, token TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS uploads(id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT, uploaded_by TEXT)")
    db.commit()
    db.close()

# ================= API ENDPOINTS (For Broadcasting) =================

@app.route('/api/send_notification', methods=['POST'])
def api_send():
    """जेव्हा कोणी इव्हेंट करेल तेव्हा हे API कॉल होते"""
    data = request.get_json()
    if not data:
        return jsonify({"status": "no data"}), 400

    title = data.get("title", "Update")
    message = data.get("message", "")

    if title and message:
        new_event = {
            "id": str(uuid.uuid4()), 
            "title": title,
            "message": message,
            "timestamp": time.time()
        }
        notifications_queue.append(new_event)
        
        if len(notifications_queue) > 10:
            notifications_queue.pop(0)
            
        return jsonify({"status": "sent_to_queue", "id": new_event["id"]})

    return jsonify({"status": "invalid_data"}), 400

@app.route('/api/get_notifications')
def api_get():
    """सर्व क्लायंट्स हे API दर ५ सेकंदाला चेक करतात"""
    return jsonify(notifications_queue)

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

        if user:
            session['user'] = username
            db.close()

            
            try:
                requests.post(
                    f"{SERVER_URL}/api/send_notification",
                    json={
                        "title": "User Login",
                        "message": f"{username} has joined the session."
                    },
                    timeout=5
                )
            except:
                pass 

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

# ================= BACKGROUND LISTENER =================

def notification_listener():
    """बॅकग्राउंडमध्ये सर्व्हरकडून नवीन नोटिफिकेशन आहेत का ते तपासते"""
    processed_ids = set() 
    
    while True:
        try:
            
            response = requests.get(f"{SERVER_URL}/api/get_notifications", timeout=5)
            if response.status_code == 200:
                server_notes = response.json()
                
                for note in server_notes:
                    n_id = note.get("id")
                    if n_id not in processed_ids:
                       
                        send_desktop_notification(note['title'], note['message'])
                        processed_ids.add(n_id)
                        
        except Exception as e:
            print("Sync Error (Retrying...):", e)
        
        time.sleep(5)

# ================= EXECUTION =================

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    init_db()

    t1 = threading.Thread(target=run_flask, daemon=True)
    t1.start()

    t2 = threading.Thread(target=notification_listener, daemon=True)
    t2.start()

    time.sleep(2)
    send_desktop_notification("SETTribe", "System Online & Synced")

    webview.create_window("SETTribe AMS Portal", AMS_URL, width=1200, height=800)
    webview.start(gui="edgechromium")