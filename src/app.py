from flask import Flask, request, jsonify, redirect
from flask_cors import CORS

import sqlite3, string, random, re, os

app = Flask(__name__)
CORS(app)

# ---- Config (env-overridable) ----
BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")
DB_PATH  = os.getenv("DB_PATH", "urls.db")
PORT     = int(os.getenv("PORT", "5000"))

# ---- DB helpers ----
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS urls(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              long_url   TEXT NOT NULL,
              short_code TEXT NOT NULL UNIQUE
            )
        """)
        conn.commit()

# ---- Utilities ----
CODE_ALPHABET = string.ascii_letters + string.digits

def gen_code(n=6):
    return ''.join(random.choice(CODE_ALPHABET) for _ in range(n))

def is_valid_url(u: str) -> bool:
    return bool(re.match(r'^https?://', (u or "").strip()))

def get_unique_short_code():
    with get_db_connection() as conn:
        while True:
            c = gen_code(6)
            cur = conn.execute("SELECT 1 FROM urls WHERE short_code=?", (c,))
            if not cur.fetchone():
                return c

# ---- API ----
@app.post("/shorten")
def shorten_url():
    data = request.get_json(silent=True) or {}
    long_url = (data.get("url") or "").strip()

    if not long_url:
        return jsonify({"error": "Missing 'url' field"}), 400
    if not is_valid_url(long_url):
        return jsonify({"error": "Invalid URL. Must start with http:// or https://"}), 400

    short_code = get_unique_short_code()
    with get_db_connection() as conn:
        conn.execute("INSERT INTO urls(long_url, short_code) VALUES(?, ?)", (long_url, short_code))
        conn.commit()

    short_url = f"{BASE_URL.rstrip('/')}/{short_code}"
    return jsonify({"short_url": short_url}), 201

# Extra alias so index.html can call /api/shorten
@app.post("/api/shorten")
def shorten_url_api():
    return shorten_url()

@app.get("/<short_code>")
def resolve(short_code):
    with get_db_connection() as conn:
        cur = conn.execute("SELECT long_url FROM urls WHERE short_code=?", (short_code,))
        row = cur.fetchone()
    if row:
        return redirect(row[0])
    return jsonify({"error": "Short code not found"}), 404

# ---- Entrypoint ----
from flask import send_from_directory

@app.get("/")
def home():
    return send_from_directory(".", "index.html")

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=PORT, debug=False)
