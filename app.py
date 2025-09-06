# app.py
import os
import json
import re
from functools import wraps
from io import BytesIO

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image, ImageOps
import pytesseract

import psycopg2
import psycopg2.extras

# ---------------- Config ----------------
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = os.environ.get("DATABASE_URL")  # e.g. from Supabase or Neon
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is required (Supabase/Neon connection string).")

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.environ.get('SECRET_KEY', 'replace-this-with-a-secure-secret')

# Make helper functions available inside all templates
@app.context_processor
def inject_helpers():
    return dict(get_user_by_id=get_user_by_id)

# ---------------- Allergen config ----------------
PREDEFINED_ALLERGENS = {
    "milk": ["milk", "lactose", "whey", "casein", "sodium caseinate", "caseinate", "milk protein", "milk solids"],
    "egg": ["egg", "eggs", "albumen", "albumin", "egg white", "egg yolk", "ovomucoid"],
    "peanut": ["peanut", "groundnut", "peanuts"],
    "tree_nuts": ["almond", "cashew", "walnut", "hazelnut", "pistachio", "pecan", "brazil nut", "macadamia"],
    "soy": ["soy", "soya", "soybean", "soy protein", "soy lecithin", "soya lecithin", "lecithin (e322)"],
    "wheat": ["wheat", "gluten", "spelt", "rye", "barley", "semolina", "triticale"],
    "fish": ["fish", "anchovy", "salmon", "tuna", "cod", "haddock", "pollock"],
    "shellfish": ["shrimp", "prawn", "crab", "lobster", "crustacean", "shellfish", "scampi"],
    "sesame": ["sesame", "sesamum", "tahini"],
    "mustard": ["mustard", "mustard seed", "mustard flour"],
    "sulfites": ["sulphite", "sulfite", "sulfur dioxide", "e220", "e221", "e222", "e223", "e224", "e225", "e226", "e227", "e228"],
    "celery": ["celery", "celeriac"],
    "lupin": ["lupin", "lupine"]
}

DISPLAY_NAME = {
    "milk": "Milk / Dairy",
    "egg": "Egg",
    "peanut": "Peanut",
    "tree_nuts": "Tree nuts",
    "soy": "Soy",
    "wheat": "Wheat / Gluten",
    "fish": "Fish",
    "shellfish": "Shellfish / Crustaceans",
    "sesame": "Sesame",
    "mustard": "Mustard",
    "sulfites": "Sulfites",
    "celery": "Celery",
    "lupin": "Lupin"
}

# ---------------- Postgres helpers ----------------
def get_db_connection():
    """
    Returns a psycopg2 connection. Caller should close() it.
    """
    # For Supabase you may need sslmode=require; psycopg2 accepts DATABASE_URL with query params,
    # but enforce sslmode to be safe:
    conn = psycopg2.connect(DATABASE_URL, sslmode="require")
    return conn

def dict_from_row(row):
    if row is None:
        return None
    return dict(row)

# ---------------- DB operations (Postgres versions) ----------------
def get_user_by_id(user_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None

def update_user_allergies(user_id, allergies_list):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET allergies = %s WHERE id = %s", (json.dumps(allergies_list), user_id))
    conn.commit()
    cur.close()
    conn.close()

def get_all_feedback(limit=200):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM feedback ORDER BY timestamp DESC LIMIT %s", (limit,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]

def get_feedback_by_user(username, limit=200):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM feedback WHERE username = %s ORDER BY timestamp DESC LIMIT %s", (username, limit))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]

def get_scan_history_by_user(username, limit=200):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM scan_history WHERE username = %s ORDER BY timestamp DESC LIMIT %s", (username, limit))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]

# ---------------- init DB (creates tables if missing) ----------------
def init_db():
    """
    Creates required tables if they don't exist and seeds some data.
    Safe to run at startup.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    # Use JSONB for allergies
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT,
        allergies JSONB DEFAULT '[]'
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS safe_alternatives (
        id SERIAL PRIMARY KEY,
        allergen TEXT NOT NULL,
        alternative TEXT NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS harmful_ingredients (
        id SERIAL PRIMARY KEY,
        ingredient TEXT NOT NULL UNIQUE,
        weight INTEGER NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS predictive_risks (
        id SERIAL PRIMARY KEY,
        food_item TEXT NOT NULL,
        possible_allergen TEXT NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS feedback (
        id SERIAL PRIMARY KEY,
        username TEXT,
        product_name TEXT,
        reaction TEXT,
        notes TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS scan_history (
        id SERIAL PRIMARY KEY,
        username TEXT,
        product_name TEXT,
        ingredients TEXT,
        detected_allergens TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS hospitals (
        id SERIAL PRIMARY KEY,
        name TEXT,
        pincode TEXT,
        address TEXT,
        phone TEXT
    );
    """)

    conn.commit()

    # Seed some data safely (try/except to skip duplicates)
    try:
        seed_alt = [
            ("peanut", "Almond butter"),
            ("peanut", "Sunflower seed butter"),
            ("milk", "Soy milk"),
            ("milk", "Oat milk"),
            ("wheat", "Rice flour"),
            ("gluten", "Corn flour")
        ]
        for a, alt in seed_alt:
            try:
                cur.execute("INSERT INTO safe_alternatives (allergen, alternative) VALUES (%s, %s)", (a, alt))
            except psycopg2.IntegrityError:
                conn.rollback()
    except Exception:
        conn.rollback()

    try:
        seed_harmful = [
            ("sugar", 20),
            ("high fructose corn syrup", 25),
            ("sodium benzoate", 15),
            ("potassium sorbate", 12),
            ("trans fat", 30),
            ("partially hydrogenated", 30),
            ("artificial sweetener", 15),
            ("monosodium glutamate", 10)
        ]
        for ing, w in seed_harmful:
            try:
                cur.execute("INSERT INTO harmful_ingredients (ingredient, weight) VALUES (%s, %s) ON CONFLICT (ingredient) DO NOTHING", (ing, w))
            except Exception:
                conn.rollback()
    except Exception:
        conn.rollback()

    try:
        seed_rules = [
            ("chocolate", "peanut"),
            ("chocolate", "milk"),
            ("ice cream", "milk"),
            ("soy sauce", "gluten"),
            ("cake", "egg")
        ]
        for fi, pa in seed_rules:
            cur.execute("INSERT INTO predictive_risks (food_item, possible_allergen) VALUES (%s, %s) ON CONFLICT DO NOTHING", (fi, pa))
    except Exception:
        conn.rollback()

    try:
        cur.execute("INSERT INTO hospitals (name, pincode, address, phone) VALUES (%s, %s, %s, %s)",
                    ("City General Hospital", "700091", "MG Road, Kolkata", "+91-33-12345678"))
    except Exception:
        conn.rollback()

    conn.commit()
    cur.close()
    conn.close()

# Initialize DB on startup
init_db()

# ---------------- Utility features ----------------
def get_safe_alternatives(allergen):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT alternative FROM safe_alternatives WHERE allergen = %s", (allergen.lower(),))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [r[0] for r in rows]

def compute_health_score(ingredients_text):
    """
    returns dict {score: int, found: [(ingredient, weight), ...]}
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT ingredient, weight FROM harmful_ingredients")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    text = (ingredients_text or "").lower()
    score = 100
    found = []
    for r in rows:
        ing = r[0].lower()
        w = int(r[1])
        if ing in text:
            score -= w
            found.append((ing, w))
    score = max(0, score)
    return {"score": score, "found": found}

def get_predictive_allergens_from_text(text):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT food_item, possible_allergen FROM predictive_risks")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    text_lower = (text or "").lower()
    preds = set()
    for r in rows:
        if r[0].lower() in text_lower:
            preds.add(r[1])
    return list(preds)

def add_feedback(username, product_name, reaction, notes=""):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO feedback (username, product_name, reaction, notes) VALUES (%s, %s, %s, %s)",
                (username, product_name, reaction, notes))
    conn.commit()
    cur.close()
    conn.close()

def save_scan_history(username, product_name, ingredients, detected_allergens):
    conn = get_db_connection()
    cur = conn.cursor()
    detected = ",".join(detected_allergens) if isinstance(detected_allergens, (list, tuple)) else str(detected_allergens)
    cur.execute("INSERT INTO scan_history (username, product_name, ingredients, detected_allergens) VALUES (%s, %s, %s, %s)",
                (username, product_name, ingredients, detected))
    conn.commit()
    cur.close()
    conn.close()

# ---------------- Allergen detection ----------------
def detect_allergens_from_text(raw_text):
    """
    Scan OCR text and detect allergens.
    Adds severity levels: high, medium, low
    """
    raw_lower = (raw_text or "").lower()
    detected = []

    for allergen_key, keywords in PREDEFINED_ALLERGENS.items():
        for kw in keywords:
            if kw in raw_lower:
                severity = "high"
                detected.append({"allergen": allergen_key, "matched": kw, "severity": severity})
                break  # stop after first match for this allergen

    # Medium risk: "may contain" or "produced in facility"
    if "may contain" in raw_lower or "produced in a facility" in raw_lower:
        for allergen_key in PREDEFINED_ALLERGENS.keys():
            detected.append({"allergen": allergen_key, "matched": "may contain/produced in facility", "severity": "medium"})

    # Low risk: "free from"
    if "free from" in raw_lower or "-free" in raw_lower:
        for allergen_key in PREDEFINED_ALLERGENS.keys():
            for kw in PREDEFINED_ALLERGENS[allergen_key]:
                if f"{kw} free" in raw_lower or f"{kw}-free" in raw_lower:
                    detected.append({"allergen": allergen_key, "matched": f"{kw}-free", "severity": "low"})

    return detected

# ---------------- Auth + decorators ----------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ---------------- Routes ----------------
@app.route('/')
def root():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','')
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name'] if user.get('full_name') else user['username']
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Invalid username/password.')
    return render_template('login.html')

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        full_name = request.form.get('full_name','').strip()
        password = request.form.get('password','')
        selected = request.form.getlist('allergies')  # list of allergen keys
        if not username or not password:
            return render_template('signup.html', error='Username and password required.', allergens=PREDEFINED_ALLERGENS)
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                'INSERT INTO users (username, password_hash, full_name, allergies) VALUES (%s,%s,%s,%s)',
                (username, generate_password_hash(password), full_name, json.dumps(selected))
            )
            conn.commit()
            cur.close()
            conn.close()
            return redirect(url_for('login'))
        except psycopg2.IntegrityError:
            conn.rollback()
            cur.close()
            conn.close()
            return render_template('signup.html', error='Username already exists.', allergens=PREDEFINED_ALLERGENS)
        except Exception as e:
            conn.rollback()
            cur.close()
            conn.close()
            return render_template('signup.html', error=f'Error: {str(e)}', allergens=PREDEFINED_ALLERGENS)
    return render_template('signup.html', allergens=PREDEFINED_ALLERGENS)

@app.route('/dashboard')
@login_required
def dashboard():
    user = get_user_by_id(session['user_id'])

    # Parse allergies safely
    user_allergies = json.loads(user['allergies']) if user and user.get('allergies') else []

    # Prefer full_name if it exists, else fallback
    if user and user.get('full_name'):
        full_name = user['full_name']
    elif session.get('full_name'):
        full_name = session['full_name']
    else:
        full_name = session.get('username')

    return render_template(
        'dashboard.html',
        username=session.get('username'),
        full_name=full_name,
        allergies=user_allergies,
        display=DISPLAY_NAME
    )

@app.route('/profile', methods=['GET','POST'])
@login_required
def profile():
    user = get_user_by_id(session['user_id'])
    if request.method == 'POST':
        selected = request.form.getlist('allergies')
        update_user_allergies(user['id'], selected)
        return redirect(url_for('dashboard'))
    user_allergies = json.loads(user['allergies']) if user else []
    return render_template(
        'profile.html',
        user=user,
        allergens=PREDEFINED_ALLERGENS,
        user_allergies=user_allergies,
        display=DISPLAY_NAME
    )

@app.route('/scan', methods=['GET','POST'])
@login_required
def scan():
    if request.method == 'GET':
        return render_template('scan.html', display=DISPLAY_NAME)

    # handle uploaded image
    file = request.files.get('image')
    if not file or file.filename == '':
        return jsonify({'error': 'No image file provided.'}), 400

    # OCR
    image = Image.open(file.stream).convert('RGB')
    image = ImageOps.grayscale(image)
    # Resize to reasonable size while preserving aspect ratio
    image.thumbnail((1200, 1200), Image.LANCZOS)
    image = ImageOps.autocontrast(image)
    raw_text = pytesseract.image_to_string(image, lang='eng')

    # ------------------ Step 1: Detect allergens ------------------
    detections = detect_allergens_from_text(raw_text)

    # User allergies
    user = get_user_by_id(session['user_id'])
    user_allergies = set(json.loads(user['allergies'])) if user and user.get('allergies') else set()

    # Relevant allergens
    relevant = [d["allergen"] for d in detections if d["allergen"] in user_allergies]

    # ------------------ Step 2: Severity-based message ------------------
    if detections:
        high = [d["allergen"] for d in detections if d["severity"] == "high" and d["allergen"] in user_allergies]
        medium = [d["allergen"] for d in detections if d["severity"] == "medium" and d["allergen"] in user_allergies]
        low = [d["allergen"] for d in detections if d["severity"] == "low" and d["allergen"] in user_allergies]

        parts = []
        if high:
            parts.append(f"🚨 High Risk: {', '.join(high)}")
        if medium:
            parts.append(f"⚠️ Medium Risk: {', '.join(medium)}")
        if low:
            parts.append(f"ℹ️ Low Risk (mentioned as -free or safe): {', '.join(low)}")

        if parts:
            message = "<br>".join(parts)
        else:
            message = "✅ No allergens in your profile detected."
    else:
        message = "✅ No allergens detected at all."

    # ------------------ New Feature: Safe Alternatives ------------------
    allergen_keys = list({d['allergen'] for d in detections}) if detections else []
    safe_alts = {a: get_safe_alternatives(a) for a in allergen_keys}

    # ------------------ New Feature: Health Score ------------------
    health = compute_health_score(raw_text)

    # ------------------ New Feature: Predictive Risks ------------------
    predictive = get_predictive_allergens_from_text(raw_text)

    # ------------------ Save Scan History ------------------
    username = user['username'] if user else 'guest'
    save_scan_history(username, "unknown", raw_text, allergen_keys)

    # ------------------ Response ------------------
    return jsonify({
        "raw_text": raw_text,
        "detections": detections,
        "user_allergies": list(user_allergies),
        "relevant": relevant,
        "message": message,
        "safe_alternatives": safe_alts,
        "health_score": health["score"],
        "health_found": health["found"],
        "predictive_allergens": predictive
    }), 200

@app.route('/scan_barcode', methods=['POST'])
@login_required
def scan_barcode():
    data = request.get_json()
    barcode = data.get("barcode")

    # For demo: sample mapping (later connect to OpenFoodFacts API)
    demo_products = {
        "8901234567890": {"name": "Chocolate Bar", "ingredients": "Milk, Sugar, Cocoa, Peanut oil"},
        "8909876543210": {"name": "Oat Milk", "ingredients": "Water, Oats, Salt"},
        "8901111111111": {"name": "Plain Water", "ingredients": ""}
    }

    product = demo_products.get(barcode)
    if not product:
        return jsonify({"error": "Product not found in database"}), 404

    raw_text = product.get("ingredients", "")

    if not raw_text.strip():
        return jsonify({"error": f"No ingredients available for {product['name']}."}), 200

    detections = detect_allergens_from_text(raw_text)
    health = compute_health_score(raw_text)
    predictive = get_predictive_allergens_from_text(raw_text)

    return jsonify({
        "product_name": product["name"],
        "ingredients": raw_text,
        "detections": detections,
        "health_score": health["score"],
        "predictive_allergens": predictive
    })

# Profile page (view + update allergies, list user feedback & history)
@app.route('/myprofile', methods=['GET', 'POST'])
@login_required
def user_profile():
    user = get_user_by_id(session.get('user_id'))
    if not user:
        return redirect(url_for('root'))

    if request.method == 'POST':
        new_allergies_raw = request.form.get('allergies', '')
        new_allergies = [a.strip() for a in new_allergies_raw.split(',') if a.strip()]
        update_user_allergies(user['id'], new_allergies)
        user = get_user_by_id(user['id'])
        return redirect(url_for('profile'))

    user_allergies = json.loads(user['allergies']) if user.get('allergies') else []
    feedback_list = get_feedback_by_user(user['username'])
    history = get_scan_history_by_user(user['username'])
    return render_template('profile.html', user=user, user_allergies=user_allergies, feedback=feedback_list, history=history)

# Community page
@app.route('/community')
@login_required
def community():
    user = get_user_by_id(session['user_id'])
    user_allergies = json.loads(user['allergies']) if user else []

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT product_name, COUNT(*) as cnt FROM feedback GROUP BY product_name ORDER BY cnt DESC LIMIT 100")
    agg_products = cur.fetchall()
    cur.execute("SELECT username, product_name, reaction, notes, timestamp FROM feedback ORDER BY timestamp DESC LIMIT 100")
    recent = cur.fetchall()
    cur.close()
    conn.close()

    return render_template(
        "community.html",
        user=user,
        user_allergies=user_allergies,
        display=DISPLAY_NAME,
        agg_products=agg_products,
        recent=recent
    )

@app.route('/feedback', methods=['POST'])
@login_required
def feedback():
    data = request.get_json() or {}
    product_name = data.get('product_name', 'unknown')
    reaction = data.get('reaction', 'Not specified')
    notes = data.get('notes', '')
    username = session.get('username', 'guest')
    add_feedback(username, product_name, reaction, notes)
    return jsonify({"status": "ok", "message": "Feedback saved"}), 200

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ---------------- Run ----------------
if __name__ == "__main__":
    # For production use a WSGI server; debug=True for local testing
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
