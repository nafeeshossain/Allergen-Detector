# Personalized Allergen Detection — Local Prototype

This is a minimal starter to run a local prototype with a Python (Flask) backend and an HTML/CSS/JS frontend.

## 1) Ubuntu prerequisites

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip   tesseract-ocr tesseract-ocr-eng
```

> If `tesseract --version` fails, ensure the package was installed correctly.

## 2) Create and activate a Python virtual environment

```bash
cd allergen-scanner-starter
python3 -m venv .venv
source .venv/bin/activate
```

## 3) Install Python dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## 4) (Optional) VS Code setup

- Install the **Python** extension.
- Open this folder, select the `.venv` interpreter.
- Create a `.env` by copying `.env.example` if you want to change host/port.

## 5) Run the app

```bash
python app.py
# or: flask --app app.py run --debug
```

Now open: http://127.0.0.1:5000

## 6) Use it

- Click **Your Allergy Profile** tags to toggle what you're allergic to (saved to localStorage).
- Upload a **clear photo** of the ingredient label. Better lighting and sharp focus improve OCR.
- The app shows raw OCR text, detected allergens (with fuzzy scores), and personalized warnings.

## 7) Troubleshooting

- **Tesseract not found**: Install `tesseract-ocr` and `tesseract-ocr-eng`. Verify `tesseract --version`.
- **ImportError**: Re-run `pip install -r requirements.txt` inside the activated `.venv`.
- **Permission denied on port**: Change `PORT` in `.env` or run `python app.py` without sudo.
- **OCR quality poor**: Try brighter images, crop to the ingredients area, or scan at higher resolution.

## 8) Notes

This is a demo. Always manually verify food labels before consumption.
You can expand `data/allergens.json` with more synonyms/brands/additives and tweak matching thresholds in `app.py`.
