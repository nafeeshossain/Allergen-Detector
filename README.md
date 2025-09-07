# 🌟 Allergen Scanner by Creative Techtians  

🚀 A web-based **AI-powered allergen detection and ingredient analysis platform** built by **Creative Techtians**.  
The application allows users to scan food product labels (via images/QR codes), detect allergens based on a personal allergy profile, and get smart recommendations for safe food consumption.  

This repository also includes a **Team Showcase Footer** component that highlights the contributors with a modern card design.  

---
## Screenshot 

<p align="center">
  <img src="Screenshots/screenshot.gif" width="500"/>
</p>

## 📌 Features  

### 🔍 Core Features  
- 📷 **OCR-based Scanning** – Extract text from food labels using **Tesseract OCR**.  
- 🧾 **Ingredient Parsing** – Match scanned ingredients with user’s allergen profile stored in **SQLite database**.  
- ⚡ **Instant Detection** – Alerts if allergens are present.  
- 🧠 **AI Enhancement (optional)** – Uses AI models (Gemini/GPT) for ingredient risk classification & health recommendations.  

### 🎨 UI Features  
- 💻 **Responsive Web Interface** using **Flask + HTML + CSS + JS**.  
- 🖼️ **Profile Footer Section** – Showcases the development team with circular profile images and role descriptions.  
- 🌐 **Simple Deployment** – Runs on **Vercel (frontend)** and **Flask backend**.  

---

## 🛠️ Tech Stack  

| Layer | Technology |
|-------|------------|
| Frontend | HTML, CSS (Poppins font), JavaScript |
| Backend | Python (Flask) |
| Database | SQLite |
| AI/ML | Tesseract OCR, Gemini API (optional for advanced recommendations) |
| Deployment | Vercel (Frontend), Flask Hosting (Backend) |

---

## 📂 Project Structure  

```bash
allergen-scanner/
│── app.py               # Flask backend
│── static/
│   ├── style.css        # CSS styling
│   ├── scan.js          # Frontend scanning logic
│── templates/
│   ├── index.html       # Homepage UI
│   ├── dashboard.html   # User dashboard
│   ├── footer.html      # Team showcase footer component
│── database.db          # SQLite database (user profiles & allergens)
│── README.md            # Project documentation

