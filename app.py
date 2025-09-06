# app.py
import os
import sqlite3
import json
import re
import difflib
from functools import wraps
from io import BytesIO

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image, ImageOps, ImageFilter
import pytesseract

# If tesseract binary not in PATH, uncomment and set the path:
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, 'allergy_app.db')

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.environ.get('SECRET_KEY', 'replace-this-with-a-secure-secret')

# Predefined allergen keywords -> synonyms/keywords used for matching OCR text
PREDEFINED_ALLERGENS = {
    "milk": ["milk", "lactose", "whey", "casein"],
    "egg": ["egg", "eggs", "albumen", "albumin"],
    "peanut": ["peanut", "groundnut"],
    "tree_nuts": ["almond", "cashew", "walnut", "hazelnut", "pistachio", "pecan", "nut"],
    "soy": ["soy", "soya", "soybean", "soy lecithin", "soya lecithin"],
    "wheat": ["wheat", "gluten", "spelt", "rye", "barley", "semolina"],
    "fish": ["fish", "anchovy", "salmon", "tuna", "cod"],
    "shellfish": ["shrimp", "prawn", "crab", "lobster", "crustacean", "shellfish"],
    "sesame": ["sesame", "sesamum"],
    "mustard": ["mustard"],
    "sulfites": ["sulphite", "sulfite", "sulfur dioxide"],
    "celery": ["celery"],
    "lupin": ["lupin"]
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

# ---------------- DB helpers ----------------
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            allergies TEXT DEFAULT '[]'  -- JSON array of allergen keys
        );
    ''')
    conn.commit()
    conn.close()

init_db()

# ---------------- auth helpers ----------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def get_user_by_id(user_id):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return user

# ---------------- routes ----------------
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
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
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
        try:
            conn.execute(
                'INSERT INTO users (username, password_hash, full_name, allergies) VALUES (?,?,?,?)',
                (username, generate_password_hash(password), full_name, json.dumps(selected))
            )
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            conn.close()
            return render_template('signup.html', error='Username already exists.', allergens=PREDEFINED_ALLERGENS)
    return render_template('signup.html', allergens=PREDEFINED_ALLERGENS)

@app.route('/dashboard')
@login_required
def dashboard():
    user = get_user_by_id(session['user_id'])
    user_allergies = json.loads(user['allergies']) if user else []
    return render_template('dashboard.html', username=session.get('username'), allergies=user_allergies, display=DISPLAY_NAME)

@app.route('/profile', methods=['GET','POST'])
@login_required
def profile():
    user = get_user_by_id(session['user_id'])
    if request.method == 'POST':
        selected = request.form.getlist('allergies')
        conn = get_db_connection()
        conn.execute('UPDATE users SET allergies = ? WHERE id = ?', (json.dumps(selected), user['id']))
        conn.commit()
        conn.close()
        return redirect(url_for('dashboard'))
    user_allergies = json.loads(user['allergies']) if user else []
    return render_template('profile.html', allergens=PREDEFINED_ALLERGENS, user_allergies=user_allergies, display=DISPLAY_NAME)

@app.route('/scan', methods=['GET','POST'])
@login_required
def scan():
    # GET: render scan UI
    if request.method == 'GET':
        return render_template('scan.html', display=DISPLAY_NAME)

    # POST: handle image upload
    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided.'}), 400
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'Empty filename.'}), 400

    # read image into PIL
    try:
        image = Image.open(file.stream).convert('RGB')
    except Exception as e:
        return jsonify({'error': f'Could not open image: {str(e)}'}), 400

    # Preprocessing to improve OCR:
    # convert to grayscale, upscale, median filter, autocontrast
    image = ImageOps.grayscale(image)
    w, h = image.size
    image = image.resize((max(800, w*2), max(800, h*2)), Image.LANCZOS)
    image = image.filter(ImageFilter.MedianFilter(size=3))
    image = ImageOps.autocontrast(image)

    # OCR:
    try:
        raw_text = pytesseract.image_to_string(image, lang='eng')
    except Exception as e:
        raw_text = ''
    norm_text = raw_text.lower()

    # tokenization for fuzzy search
    tokens = re.findall(r"[a-zA-Z0-9']+", norm_text)

    detected = set()
    for allergen_key, keywords in PREDEFINED_ALLERGENS.items():
        for kw in keywords:
            if kw in norm_text:
                detected.add(allergen_key)
                break
            # fuzzy match tokens for OCR mistakes
            close = difflib.get_close_matches(kw, tokens, n=1, cutoff=0.85)
            if close:
                detected.add(allergen_key)
                break

    # intersect with user's allergy profile
    user = get_user_by_id(session['user_id'])
    user_allergies = set(json.loads(user['allergies'])) if user else set()
    relevant = sorted(list(detected & user_allergies))

    # generate friendly messages
    if relevant:
        message = f"Warning — allergen(s) detected: {', '.join([DISPLAY_NAME.get(r, r) for r in relevant])}"
    else:
        if detected:
            # found allergens in general but not ones user marked
            message = f"No user allergens detected. But product contains: {', '.join([DISPLAY_NAME.get(d, d) for d in detected])}"
        else:
            message = "No allergens detected from the predefined list."

    return jsonify({
        'detected_allergens_in_label': sorted(list(detected)),
        'user_allergies': sorted(list(user_allergies)),
        'relevant': relevant,
        'raw_text': raw_text,
        'message': message
    }), 200

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# static files served automatically by Flask from /static

if __name__ == '__main__':
    app.run(debug=True)
