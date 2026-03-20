from flask import Flask, request, jsonify
import sqlite3
import uuid
import time

app = Flask(__name__)

# ================= DB =================

def get_db():
    return sqlite3.connect("notifications.db")

def init_db():
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id TEXT PRIMARY KEY,
            target_machine TEXT,
            title TEXT,
            message TEXT,
            timestamp REAL
        )
    """)
    db.commit()
    db.close()

# ================= API =================

@app.route("/")
def home():
    return "Server Running ✅"

@app.route('/api/send_notification', methods=['POST'])
def send_notification():
    data = request.get_json()

    target = data.get("target_machine")
    title = data.get("title")
    message = data.get("message")

    if not target or not title:
        return jsonify({"status": "invalid"}), 400

    db = get_db()
    cur = db.cursor()

    cur.execute("""
        INSERT INTO notifications VALUES (?, ?, ?, ?, ?)
    """, (
        str(uuid.uuid4()),
        target,
        title,
        message,
        time.time()
    ))

    db.commit()
    db.close()

    return jsonify({"status": "stored"})

@app.route('/api/get_notifications')
def get_notifications():
    machine_id = request.args.get("machine_id")

    db = get_db()
    cur = db.cursor()

    cur.execute("""
        SELECT id, title, message FROM notifications
        WHERE target_machine = ?
    """, (machine_id,))

    rows = cur.fetchall()
    db.close()

    data = []
    for r in rows:
        data.append({
            "id": r[0],
            "title": r[1],
            "message": r[2]
        })

    return jsonify(data)

# ================= RUN =================

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=10000)