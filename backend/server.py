from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import random
import string
import time
import psycopg2
import traceback

try:
    from supabase import create_client
    SUPABASE_ENABLED = True
except ImportError:
    SUPABASE_ENABLED = False
    print("WARNING: supabase package not installed")

app = Flask(__name__)
CORS(app, origins="*", supports_credentials=True,
     allow_headers=["Content-Type"], methods=["GET","POST","OPTIONS"])

DATABASE_URL = os.environ.get("DATABASE_URL")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
BUCKET = "webshare"

def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def gen_token():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

def init_db():
    conn = get_conn(); cur = conn.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY, password TEXT NOT NULL)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS ideas (
        id SERIAL PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL,
        author TEXT NOT NULL, votes INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS projects (
        id SERIAL PRIMARY KEY, title TEXT NOT NULL, link TEXT,
        description TEXT NOT NULL, author TEXT NOT NULL, votes INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS idea_votes (
        username TEXT NOT NULL, idea_id INTEGER NOT NULL, vote INTEGER NOT NULL,
        PRIMARY KEY (username, idea_id))""")

    cur.execute("""CREATE TABLE IF NOT EXISTS project_votes (
        username TEXT NOT NULL, project_id INTEGER NOT NULL, vote INTEGER NOT NULL,
        PRIMARY KEY (username, project_id))""")

    cur.execute("""CREATE TABLE IF NOT EXISTS idea_comments (
        id SERIAL PRIMARY KEY, idea_id INTEGER NOT NULL, author TEXT NOT NULL,
        content TEXT NOT NULL, votes INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS project_comments (
        id SERIAL PRIMARY KEY, project_id INTEGER NOT NULL, author TEXT NOT NULL,
        content TEXT NOT NULL, votes INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS idea_comment_votes (
        username TEXT NOT NULL, comment_id INTEGER NOT NULL, vote INTEGER NOT NULL,
        PRIMARY KEY (username, comment_id))""")

    cur.execute("""CREATE TABLE IF NOT EXISTS project_comment_votes (
        username TEXT NOT NULL, comment_id INTEGER NOT NULL, vote INTEGER NOT NULL,
        PRIMARY KEY (username, comment_id))""")

    cur.execute("""CREATE TABLE IF NOT EXISTS qa (
        id SERIAL PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL,
        author TEXT NOT NULL, votes INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS qa_answers (
        id SERIAL PRIMARY KEY, qa_id INTEGER NOT NULL, author TEXT NOT NULL,
        content TEXT NOT NULL, votes INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS qa_votes (
        username TEXT NOT NULL, qa_id INTEGER NOT NULL, vote INTEGER NOT NULL,
        PRIMARY KEY (username, qa_id))""")

    cur.execute("""CREATE TABLE IF NOT EXISTS qa_answer_votes (
        username TEXT NOT NULL, answer_id INTEGER NOT NULL, vote INTEGER NOT NULL,
        PRIMARY KEY (username, answer_id))""")

    cur.execute("""CREATE TABLE IF NOT EXISTS upgrades (
        id SERIAL PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL,
        code TEXT NOT NULL, language TEXT NOT NULL, author TEXT NOT NULL,
        votes INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS upgrade_versions (
        id SERIAL PRIMARY KEY, upgrade_id INTEGER NOT NULL, author TEXT NOT NULL,
        code TEXT NOT NULL, explanation TEXT NOT NULL, votes INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS upgrade_votes (
        username TEXT NOT NULL, upgrade_id INTEGER NOT NULL, vote INTEGER NOT NULL,
        PRIMARY KEY (username, upgrade_id))""")

    cur.execute("""CREATE TABLE IF NOT EXISTS upgrade_version_votes (
        username TEXT NOT NULL, version_id INTEGER NOT NULL, vote INTEGER NOT NULL,
        PRIMARY KEY (username, version_id))""")

    cur.execute("""CREATE TABLE IF NOT EXISTS share_sessions (
        token TEXT PRIMARY KEY, creator TEXT NOT NULL,
        created_at BIGINT NOT NULL, expires_at BIGINT NOT NULL,
        total_size BIGINT DEFAULT 0)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS share_files (
        id SERIAL PRIMARY KEY, token TEXT NOT NULL,
        filename TEXT NOT NULL, storage_path TEXT NOT NULL,
        uploader TEXT NOT NULL, size BIGINT NOT NULL,
        mime_type TEXT, uploaded_at BIGINT NOT NULL)""")

    conn.commit(); cur.close(); conn.close()

# ---- helpers ----
def do_vote(cur, table, pk_col, id_val, username, val):
    cur.execute(f"SELECT vote FROM {table} WHERE username=%s AND {pk_col}=%s", (username, id_val))
    row = cur.fetchone()
    existing = row[0] if row else 0
    if existing == val:
        delta = -val; new_vote = 0
        if existing != 0:
            cur.execute(f"DELETE FROM {table} WHERE username=%s AND {pk_col}=%s", (username, id_val))
    else:
        delta = val - existing; new_vote = val
        cur.execute(f"""INSERT INTO {table} (username, {pk_col}, vote) VALUES (%s,%s,%s)
            ON CONFLICT (username, {pk_col}) DO UPDATE SET vote=%s""", (username, id_val, val, val))
    return delta, new_vote

def require_login(data):
    username = data.get("username", "").strip()
    if not username or username == "Guest":
        return None, jsonify({"status": "error", "message": "Login required"})
    return username, None

def cleanup_session(token, cur, sb):
    cur.execute("SELECT storage_path FROM share_files WHERE token=%s", (token,))
    paths = [r[0] for r in cur.fetchall()]
    if paths:
        try: sb.storage.from_(BUCKET).remove(paths)
        except: pass
    cur.execute("DELETE FROM share_files WHERE token=%s", (token,))
    cur.execute("DELETE FROM share_sessions WHERE token=%s", (token,))

def check_expired(token, cur, sb):
    cur.execute("SELECT expires_at FROM share_sessions WHERE token=%s", (token,))
    row = cur.fetchone()
    if not row: return True
    if int(time.time()) > row[0]:
        cleanup_session(token, cur, sb)
        return True
    return False

# ===== AUTH =====
@app.route("/signup", methods=["POST"])
def signup():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return jsonify({"status": "error", "message": "Missing fields"})
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT username FROM users WHERE username=%s", (username,))
        if cur.fetchone():
            cur.close(); conn.close()
            return jsonify({"status": "error", "message": "User already exists"})
        cur.execute("INSERT INTO users (username,password) VALUES (%s,%s)", (username, password))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"status": "ok", "message": "Account created"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "")
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT password FROM users WHERE username=%s", (username,))
        row = cur.fetchone(); cur.close(); conn.close()
        if not row: return jsonify({"status": "error", "message": "User not found"})
        if row[0] != password: return jsonify({"status": "error", "message": "Wrong password"})
        return jsonify({"status": "ok", "message": f"Welcome {username}"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# ===== IDEAS =====
@app.route("/ideas", methods=["GET"])
def get_ideas():
    username = request.args.get("username", "")
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT id,title,description,author,votes FROM ideas ORDER BY created_at DESC")
        rows = cur.fetchall()
        uv = {}
        if username:
            cur.execute("SELECT idea_id,vote FROM idea_votes WHERE username=%s", (username,))
            for r in cur.fetchall(): uv[r[0]] = r[1]
        cur.close(); conn.close()
        return jsonify({"status":"ok","ideas":[{"id":r[0],"title":r[1],"desc":r[2],"author":r[3],"votes":r[4],"uservote":uv.get(r[0],0)} for r in rows]})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)})

@app.route("/ideas", methods=["POST"])
def post_idea():
    data = request.get_json()
    username, err = require_login(data)
    if err: return err
    title = data.get("title","").strip(); desc = data.get("desc","").strip()
    if not title or not desc: return jsonify({"status":"error","message":"Missing fields"})
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("INSERT INTO ideas (title,description,author) VALUES (%s,%s,%s)", (title,desc,username))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"status":"ok"})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)})

@app.route("/ideas/vote", methods=["POST"])
def vote_idea():
    data = request.get_json()
    username, err = require_login(data)
    if err: return err
    try:
        conn = get_conn(); cur = conn.cursor()
        delta, new_vote = do_vote(cur, "idea_votes", "idea_id", data["id"], username, data["val"])
        cur.execute("UPDATE ideas SET votes=votes+%s WHERE id=%s", (delta, data["id"]))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"status":"ok","uservote":new_vote})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)})

@app.route("/ideas/<int:idea_id>/comments", methods=["GET"])
def get_idea_comments(idea_id):
    username = request.args.get("username","")
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT id,author,content,votes FROM idea_comments WHERE idea_id=%s ORDER BY votes DESC, created_at ASC", (idea_id,))
        rows = cur.fetchall()
        uv = {}
        if username:
            cur.execute("SELECT comment_id,vote FROM idea_comment_votes WHERE username=%s", (username,))
            for r in cur.fetchall(): uv[r[0]] = r[1]
        cur.close(); conn.close()
        return jsonify({"status":"ok","comments":[{"id":r[0],"author":r[1],"content":r[2],"votes":r[3],"uservote":uv.get(r[0],0)} for r in rows]})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)})

@app.route("/ideas/<int:idea_id>/comments", methods=["POST"])
def post_idea_comment(idea_id):
    data = request.get_json()
    username, err = require_login(data)
    if err: return err
    content = data.get("content","").strip()
    if not content: return jsonify({"status":"error","message":"Empty comment"})
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("INSERT INTO idea_comments (idea_id,author,content) VALUES (%s,%s,%s)", (idea_id,username,content))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"status":"ok"})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)})

@app.route("/ideas/comments/vote", methods=["POST"])
def vote_idea_comment():
    data = request.get_json()
    username, err = require_login(data)
    if err: return err
    try:
        conn = get_conn(); cur = conn.cursor()
        delta, new_vote = do_vote(cur, "idea_comment_votes", "comment_id", data["id"], username, data["val"])
        cur.execute("UPDATE idea_comments SET votes=votes+%s WHERE id=%s", (delta, data["id"]))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"status":"ok","uservote":new_vote})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)})

# ===== PROJECTS =====
@app.route("/projects", methods=["GET"])
def get_projects():
    username = request.args.get("username","")
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT id,title,link,description,author,votes FROM projects ORDER BY created_at DESC")
        rows = cur.fetchall()
        uv = {}
        if username:
            cur.execute("SELECT project_id,vote FROM project_votes WHERE username=%s", (username,))
            for r in cur.fetchall(): uv[r[0]] = r[1]
        cur.close(); conn.close()
        return jsonify({"status":"ok","projects":[{"id":r[0],"title":r[1],"link":r[2],"desc":r[3],"author":r[4],"votes":r[5],"uservote":uv.get(r[0],0)} for r in rows]})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)})

@app.route("/projects", methods=["POST"])
def post_project():
    data = request.get_json()
    username, err = require_login(data)
    if err: return err
    title = data.get("title","").strip(); link = data.get("link","").strip(); desc = data.get("desc","").strip()
    if not title or not desc: return jsonify({"status":"error","message":"Missing fields"})
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("INSERT INTO projects (title,link,description,author) VALUES (%s,%s,%s,%s)", (title,link,desc,username))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"status":"ok"})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)})

@app.route("/projects/vote", methods=["POST"])
def vote_project():
    data = request.get_json()
    username, err = require_login(data)
    if err: return err
    try:
        conn = get_conn(); cur = conn.cursor()
        delta, new_vote = do_vote(cur, "project_votes", "project_id", data["id"], username, data["val"])
        cur.execute("UPDATE projects SET votes=votes+%s WHERE id=%s", (delta, data["id"]))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"status":"ok","uservote":new_vote})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)})

@app.route("/projects/<int:project_id>/comments", methods=["GET"])
def get_project_comments(project_id):
    username = request.args.get("username","")
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT id,author,content,votes FROM project_comments WHERE project_id=%s ORDER BY votes DESC, created_at ASC", (project_id,))
        rows = cur.fetchall()
        uv = {}
        if username:
            cur.execute("SELECT comment_id,vote FROM project_comment_votes WHERE username=%s", (username,))
            for r in cur.fetchall(): uv[r[0]] = r[1]
        cur.close(); conn.close()
        return jsonify({"status":"ok","comments":[{"id":r[0],"author":r[1],"content":r[2],"votes":r[3],"uservote":uv.get(r[0],0)} for r in rows]})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)})

@app.route("/projects/<int:project_id>/comments", methods=["POST"])
def post_project_comment(project_id):
    data = request.get_json()
    username, err = require_login(data)
    if err: return err
    content = data.get("content","").strip()
    if not content: return jsonify({"status":"error","message":"Empty comment"})
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("INSERT INTO project_comments (project_id,author,content) VALUES (%s,%s,%s)", (project_id,username,content))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"status":"ok"})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)})

@app.route("/projects/comments/vote", methods=["POST"])
def vote_project_comment():
    data = request.get_json()
    username, err = require_login(data)
    if err: return err
    try:
        conn = get_conn(); cur = conn.cursor()
        delta, new_vote = do_vote(cur, "project_comment_votes", "comment_id", data["id"], username, data["val"])
        cur.execute("UPDATE project_comments SET votes=votes+%s WHERE id=%s", (delta, data["id"]))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"status":"ok","uservote":new_vote})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)})

# ===== Q&A =====
@app.route("/qa", methods=["GET"])
def get_qa():
    username = request.args.get("username","")
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT id,title,description,author,votes FROM qa ORDER BY created_at DESC")
        rows = cur.fetchall()
        uv = {}
        if username:
            cur.execute("SELECT qa_id,vote FROM qa_votes WHERE username=%s", (username,))
            for r in cur.fetchall(): uv[r[0]] = r[1]
        cur.close(); conn.close()
        return jsonify({"status":"ok","questions":[{"id":r[0],"title":r[1],"desc":r[2],"author":r[3],"votes":r[4],"uservote":uv.get(r[0],0)} for r in rows]})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)})

@app.route("/qa", methods=["POST"])
def post_qa():
    data = request.get_json()
    username, err = require_login(data)
    if err: return err
    title = data.get("title","").strip(); desc = data.get("desc","").strip()
    if not title or not desc: return jsonify({"status":"error","message":"Missing fields"})
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("INSERT INTO qa (title,description,author) VALUES (%s,%s,%s)", (title,desc,username))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"status":"ok"})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)})

@app.route("/qa/vote", methods=["POST"])
def vote_qa():
    data = request.get_json()
    username, err = require_login(data)
    if err: return err
    try:
        conn = get_conn(); cur = conn.cursor()
        delta, new_vote = do_vote(cur, "qa_votes", "qa_id", data["id"], username, data["val"])
        cur.execute("UPDATE qa SET votes=votes+%s WHERE id=%s", (delta, data["id"]))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"status":"ok","uservote":new_vote})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)})

@app.route("/qa/<int:qa_id>/answers", methods=["GET"])
def get_answers(qa_id):
    username = request.args.get("username","")
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT id,author,content,votes FROM qa_answers WHERE qa_id=%s ORDER BY votes DESC, created_at ASC", (qa_id,))
        rows = cur.fetchall()
        uv = {}
        if username:
            cur.execute("SELECT answer_id,vote FROM qa_answer_votes WHERE username=%s", (username,))
            for r in cur.fetchall(): uv[r[0]] = r[1]
        cur.close(); conn.close()
        return jsonify({"status":"ok","answers":[{"id":r[0],"author":r[1],"content":r[2],"votes":r[3],"uservote":uv.get(r[0],0)} for r in rows]})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)})

@app.route("/qa/<int:qa_id>/answers", methods=["POST"])
def post_answer(qa_id):
    data = request.get_json()
    username, err = require_login(data)
    if err: return err
    content = data.get("content","").strip()
    if not content: return jsonify({"status":"error","message":"Empty answer"})
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("INSERT INTO qa_answers (qa_id,author,content) VALUES (%s,%s,%s)", (qa_id,username,content))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"status":"ok"})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)})

@app.route("/qa/answers/vote", methods=["POST"])
def vote_answer():
    data = request.get_json()
    username, err = require_login(data)
    if err: return err
    try:
        conn = get_conn(); cur = conn.cursor()
        delta, new_vote = do_vote(cur, "qa_answer_votes", "answer_id", data["id"], username, data["val"])
        cur.execute("UPDATE qa_answers SET votes=votes+%s WHERE id=%s", (delta, data["id"]))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"status":"ok","uservote":new_vote})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)})

# ===== UPGRADES =====
@app.route("/upgrades", methods=["GET"])
def get_upgrades():
    username = request.args.get("username","")
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT id,title,description,code,language,author,votes FROM upgrades ORDER BY created_at DESC")
        rows = cur.fetchall()
        uv = {}
        if username:
            cur.execute("SELECT upgrade_id,vote FROM upgrade_votes WHERE username=%s", (username,))
            for r in cur.fetchall(): uv[r[0]] = r[1]
        cur.close(); conn.close()
        return jsonify({"status":"ok","upgrades":[{"id":r[0],"title":r[1],"desc":r[2],"code":r[3],"language":r[4],"author":r[5],"votes":r[6],"uservote":uv.get(r[0],0)} for r in rows]})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)})

@app.route("/upgrades", methods=["POST"])
def post_upgrade():
    data = request.get_json()
    username, err = require_login(data)
    if err: return err
    title = data.get("title","").strip(); desc = data.get("desc","").strip()
    code = data.get("code","").strip(); lang = data.get("language","plaintext").strip()
    if not title or not code: return jsonify({"status":"error","message":"Missing fields"})
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("INSERT INTO upgrades (title,description,code,language,author) VALUES (%s,%s,%s,%s,%s)", (title,desc,code,lang,username))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"status":"ok"})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)})

@app.route("/upgrades/vote", methods=["POST"])
def vote_upgrade():
    data = request.get_json()
    username, err = require_login(data)
    if err: return err
    try:
        conn = get_conn(); cur = conn.cursor()
        delta, new_vote = do_vote(cur, "upgrade_votes", "upgrade_id", data["id"], username, data["val"])
        cur.execute("UPDATE upgrades SET votes=votes+%s WHERE id=%s", (delta, data["id"]))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"status":"ok","uservote":new_vote})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)})

@app.route("/upgrades/<int:upgrade_id>/versions", methods=["GET"])
def get_versions(upgrade_id):
    username = request.args.get("username","")
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT id,author,code,explanation,votes FROM upgrade_versions WHERE upgrade_id=%s ORDER BY votes DESC, created_at ASC", (upgrade_id,))
        rows = cur.fetchall()
        uv = {}
        if username:
            cur.execute("SELECT version_id,vote FROM upgrade_version_votes WHERE username=%s", (username,))
            for r in cur.fetchall(): uv[r[0]] = r[1]
        cur.close(); conn.close()
        return jsonify({"status":"ok","versions":[{"id":r[0],"author":r[1],"code":r[2],"explanation":r[3],"votes":r[4],"uservote":uv.get(r[0],0)} for r in rows]})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)})

@app.route("/upgrades/<int:upgrade_id>/versions", methods=["POST"])
def post_version(upgrade_id):
    data = request.get_json()
    username, err = require_login(data)
    if err: return err
    code = data.get("code","").strip(); explanation = data.get("explanation","").strip()
    if not code: return jsonify({"status":"error","message":"Missing code"})
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("INSERT INTO upgrade_versions (upgrade_id,author,code,explanation) VALUES (%s,%s,%s,%s)", (upgrade_id,username,code,explanation))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"status":"ok"})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)})

@app.route("/upgrades/versions/vote", methods=["POST"])
def vote_version():
    data = request.get_json()
    username, err = require_login(data)
    if err: return err
    try:
        conn = get_conn(); cur = conn.cursor()
        delta, new_vote = do_vote(cur, "upgrade_version_votes", "version_id", data["id"], username, data["val"])
        cur.execute("UPDATE upgrade_versions SET votes=votes+%s WHERE id=%s", (delta, data["id"]))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"status":"ok","uservote":new_vote})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)})

# ===== MONTHLY =====
@app.route("/monthly", methods=["GET"])
def get_monthly():
    try:
        conn = get_conn(); cur = conn.cursor()
        results = {}
        for table, key in [("ideas","idea"),("projects","project"),("qa","question"),("upgrades","upgrade")]:
            cur.execute(f"SELECT id,title,description,author,votes FROM {table} ORDER BY votes DESC LIMIT 1")
            r = cur.fetchone()
            if r: results[key] = {"id":r[0],"title":r[1],"desc":r[2],"author":r[3],"votes":r[4]}
            else: results[key] = None
        cur.close(); conn.close()
        return jsonify({"status":"ok","monthly":results})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)})

# ===== WEB SHARE =====
@app.route("/share/create", methods=["POST", "OPTIONS"])
def create_share():
    if request.method == "OPTIONS":
        return "", 200
    data = request.get_json()
    creator = data.get("username", "Guest")
    now = int(time.time())
    expires = now + 3600
    try:
        conn = get_conn(); cur = conn.cursor()
        token = gen_token()
        for _ in range(10):
            cur.execute("SELECT token FROM share_sessions WHERE token=%s", (token,))
            if not cur.fetchone(): break
            token = gen_token()
        cur.execute("INSERT INTO share_sessions (token,creator,created_at,expires_at,total_size) VALUES (%s,%s,%s,%s,0)",
            (token, creator, now, expires))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"status":"ok","token":token,"expires_at":expires})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)})

@app.route("/share/<token>", methods=["GET"])
def get_share(token):
    try:
        conn = get_conn(); cur = conn.cursor()
        sb = get_supabase()
        if check_expired(token, cur, sb):
            conn.commit(); cur.close(); conn.close()
            return jsonify({"status":"error","message":"Session expired or not found"})
        cur.execute("SELECT creator,expires_at,total_size FROM share_sessions WHERE token=%s", (token,))
        sess = cur.fetchone()
        cur.execute("SELECT id,filename,uploader,size,mime_type,uploaded_at FROM share_files WHERE token=%s ORDER BY uploaded_at ASC", (token,))
        files = [{"id":r[0],"filename":r[1],"uploader":r[2],"size":r[3],"mime_type":r[4],"uploaded_at":r[5]} for r in cur.fetchall()]
        cur.close(); conn.close()
        return jsonify({"status":"ok","creator":sess[0],"expires_at":sess[1],"total_size":sess[2],"files":files})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)})

@app.route("/share/<token>/upload", methods=["POST", "OPTIONS"])
def upload_file(token):
    if request.method == "OPTIONS":
        return "", 200
    try:
        conn = get_conn(); cur = conn.cursor()
        sb = get_supabase()
        if check_expired(token, cur, sb):
            conn.commit(); cur.close(); conn.close()
            return jsonify({"status":"error","message":"Session expired"})
        f = request.files.get("file")
        uploader = request.form.get("username", "Guest")
        if not f: return jsonify({"status":"error","message":"No file"})
        data = f.read(); size = len(data)
        if size > 100*1024*1024: return jsonify({"status":"error","message":"File too large (max 100MB)"})
        cur.execute("SELECT total_size FROM share_sessions WHERE token=%s", (token,))
        total = cur.fetchone()[0]
        if total + size > 500*1024*1024: return jsonify({"status":"error","message":"Session storage full (max 500MB)"})
        path = f"{token}/{int(time.time())}_{f.filename}"
        sb.storage.from_(BUCKET).upload(path, data, {"content-type": f.content_type or "application/octet-stream"})
        now = int(time.time())
        cur.execute("INSERT INTO share_files (token,filename,storage_path,uploader,size,mime_type,uploaded_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (token, f.filename, path, uploader, size, f.content_type, now))
        cur.execute("UPDATE share_sessions SET total_size=total_size+%s WHERE token=%s", (size, token))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"status":"ok"})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)})

@app.route("/share/<token>/download/<int:file_id>", methods=["GET"])
def download_file(token, file_id):
    try:
        conn = get_conn(); cur = conn.cursor()
        sb = get_supabase()
        if check_expired(token, cur, sb):
            conn.commit(); cur.close(); conn.close()
            return jsonify({"status":"error","message":"Session expired"})
        cur.execute("SELECT storage_path,filename FROM share_files WHERE id=%s AND token=%s", (file_id, token))
        row = cur.fetchone(); cur.close(); conn.close()
        if not row: return jsonify({"status":"error","message":"File not found"})
        res = sb.storage.from_(BUCKET).create_signed_url(row[0], 60)
        url = res.get("signedURL") or res.get("signedUrl") or res
        return jsonify({"status":"ok","url":url,"filename":row[1]})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)})

@app.route("/share/<token>/end", methods=["POST", "OPTIONS"])
def end_share(token):
    if request.method == "OPTIONS":
        return "", 200
    try:
        conn = get_conn(); cur = conn.cursor()
        sb = get_supabase()
        cur.execute("SELECT creator FROM share_sessions WHERE token=%s", (token,))
        if not cur.fetchone():
            return jsonify({"status":"error","message":"Session not found"})
        cleanup_session(token, cur, sb)
        conn.commit(); cur.close(); conn.close()
        return jsonify({"status":"ok"})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)})

# ===== RUN =====
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

init_db()
