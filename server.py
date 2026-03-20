from flask import Flask, request, jsonify
import sqlite3
import uuid
import time
import os

app = Flask(__name__)

# ================= DB =================

def get_db():
    return sqlite3.connect("notifications.db", check_same_thread=False)

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

# ✅ IMPORTANT: CALL HERE (NOT decorator)
init_db()

# ================= ROUTES =================

@app.route("/")
def home():
    return "Server Running ✅"

@app.route('/api/send_notification', methods=['POST'])
def send_notification():
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "Invalid JSON"}), 400

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

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/get_notifications')
def get_notifications():
    try:
        machine_id = request.args.get("machine_id")

        if not machine_id:
            return jsonify({"error": "machine_id required"}), 400

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

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ================= RUN =================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))