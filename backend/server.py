from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import os
 
app = Flask(__name__)
CORS(app, origins="*")
 
DATABASE_URL = os.environ.get("DATABASE_URL")
 
def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")
 
def init_db():
    conn = get_conn()
    cur = conn.cursor()
 
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    """)
 
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ideas (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            author TEXT NOT NULL,
            votes INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
 
    cur.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            link TEXT,
            description TEXT NOT NULL,
            author TEXT NOT NULL,
            votes INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
 
    conn.commit()
    cur.close()
    conn.close()
 
# ===== Signup =====
@app.route("/signup", methods=["POST"])
def signup():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "")
 
    if not username or not password:
        return jsonify({"status": "error", "message": "Missing fields"})
 
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT username FROM users WHERE username = %s", (username,))
        if cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"status": "error", "message": "User already exists"})
 
        cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "ok", "message": "Account created"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
 
# ===== Login =====
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "")
 
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT password FROM users WHERE username = %s", (username,))
        row = cur.fetchone()
        cur.close()
        conn.close()
 
        if not row:
            return jsonify({"status": "error", "message": "User not found"})
        if row[0] != password:
            return jsonify({"status": "error", "message": "Wrong password"})
 
        return jsonify({"status": "ok", "message": f"Welcome {username}"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
 
# ===== Get all ideas =====
@app.route("/ideas", methods=["GET"])
def get_ideas():
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, title, description, author, votes FROM ideas ORDER BY created_at DESC")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        ideas = [{"id": r[0], "title": r[1], "desc": r[2], "author": r[3], "votes": r[4]} for r in rows]
        return jsonify({"status": "ok", "ideas": ideas})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
 
# ===== Submit idea =====
@app.route("/ideas", methods=["POST"])
def post_idea():
    data = request.get_json()
    title = data.get("title", "").strip()
    desc = data.get("desc", "").strip()
    author = data.get("author", "Guest").strip()
 
    if not title or not desc:
        return jsonify({"status": "error", "message": "Missing fields"})
 
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("INSERT INTO ideas (title, description, author) VALUES (%s, %s, %s)", (title, desc, author))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "ok", "message": "Idea submitted"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
 
# ===== Vote idea =====
@app.route("/ideas/vote", methods=["POST"])
def vote_idea():
    data = request.get_json()
    idea_id = data.get("id")
    val = data.get("val", 0)
 
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE ideas SET votes = votes + %s WHERE id = %s", (val, idea_id))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
 
# ===== Get all projects =====
@app.route("/projects", methods=["GET"])
def get_projects():
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, title, link, description, author, votes FROM projects ORDER BY created_at DESC")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        projects = [{"id": r[0], "title": r[1], "link": r[2], "desc": r[3], "author": r[4], "votes": r[5]} for r in rows]
        return jsonify({"status": "ok", "projects": projects})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
 
# ===== Submit project =====
@app.route("/projects", methods=["POST"])
def post_project():
    data = request.get_json()
    title = data.get("title", "").strip()
    link = data.get("link", "").strip()
    desc = data.get("desc", "").strip()
    author = data.get("author", "Guest").strip()
 
    if not title or not desc:
        return jsonify({"status": "error", "message": "Missing fields"})
 
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("INSERT INTO projects (title, link, description, author) VALUES (%s, %s, %s, %s)", (title, link, desc, author))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "ok", "message": "Project submitted"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
 
# ===== Vote project =====
@app.route("/projects/vote", methods=["POST"])
def vote_project():
    data = request.get_json()
    project_id = data.get("id")
    val = data.get("val", 0)
 
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE projects SET votes = votes + %s WHERE id = %s", (val, project_id))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
 
# ===== Run =====
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
 
init_db()
