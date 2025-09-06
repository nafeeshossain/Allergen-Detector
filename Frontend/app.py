from flask import Flask, render_template, request, jsonify
import os, json, re, io
from PIL import Image
import numpy as np
import pytesseract
import cv2
from rapidfuzz import fuzz, process

# Load allergen dictionary
with open(os.path.join("data", "allergens.json"), "r") as f:
    ALLERGENS = json.load(f)

app = Flask(__name__)

def preprocess_image(file_bytes: bytes) -> Image.Image:
    # Convert uploaded bytes to OpenCV image
    file_arr = np.frombuffer(file_bytes, np.uint8)
    img = cv2.imdecode(file_arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Unable to read image")
    # Basic preprocessing to help OCR
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Adaptive threshold can help on varied lighting
    thr = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY, 35, 11)
    # Slight dilation to connect characters
    kernel = np.ones((1,1), np.uint8)
    thr = cv2.morphologyEx(thr, cv2.MORPH_OPEN, kernel)
    pil_img = Image.fromarray(thr)
    return pil_img

def clean_text(t: str) -> str:
    # Normalize text for matching
    t = t.lower()
    t = re.sub(r"[^a-z0-9\s\-\(\)\/\.%]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def detect_allergens(text: str, threshold: int = 88):
    """
    Simple fuzzy matching of allergens and synonyms against the extracted text.
    Returns a list of {allergen_key, hits:[{term, score}], max_score}.
    """
    found = []
    for allergen_key, terms in ALLERGENS.items():
        hits = []
        for term in terms:
            # partial ratio is forgiving on noise/line-breaks
            score = fuzz.partial_ratio(term, text)
            if score >= threshold:
                hits.append({"term": term, "score": int(score)})
        if hits:
            found.append({
                "allergen": allergen_key,
                "hits": sorted(hits, key=lambda x: -x["score"]),
                "max_score": max(h["score"] for h in hits)
            })
    # Sort by confidence
    found.sort(key=lambda x: -x["max_score"])
    return found

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")

@app.route("/api/scan", methods=["POST"])
def scan():
    if "image" not in request.files:
        return jsonify({"ok": False, "error": "No file part 'image' found"}), 400
    file = request.files["image"]
    if file.filename == "":
        return jsonify({"ok": False, "error": "No selected file"}), 400

    try:
        raw = file.read()
        pre = preprocess_image(raw)
        # Use English; make sure tesseract-ocr-eng is installed on Ubuntu
        text = pytesseract.image_to_string(pre, lang="eng", config="--psm 6")
        cleaned = clean_text(text)
        matches = detect_allergens(cleaned)

        return jsonify({
            "ok": True,
            "ingredients_raw": text,
            "ingredients_clean": cleaned,
            "matches": matches
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 5000))
    app.run(host=host, port=port, debug=True)
