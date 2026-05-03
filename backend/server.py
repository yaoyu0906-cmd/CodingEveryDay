from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os

app = Flask(__name__)
CORS(app)

DB_FILE = "users.json"

# ===== Load users =====
def load_users():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r") as f:
        return json.load(f)

# ===== Save users =====
def save_users(users):
    with open(DB_FILE, "w") as f:
        json.dump(users, f, indent=4)

# ===== Signup =====
@app.route("/signup", methods=["POST"])
def signup():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    users = load_users()

    if username in users:
        return jsonify({"status": "error", "message": "User already exists"})

    users[username] = {
        "password": password
    }

    save_users(users)

    return jsonify({"status": "ok", "message": "Account created"})

# ===== Login =====
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    users = load_users()

    if username not in users:
        return jsonify({"status": "error", "message": "User not found"})

    if users[username]["password"] != password:
        return jsonify({"status": "error", "message": "Wrong password"})

    return jsonify({"status": "ok", "message": f"Welcome {username}"})

# ===== Run =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
