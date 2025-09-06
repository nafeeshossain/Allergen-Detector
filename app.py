import streamlit as st
import pandas as pd
import easyocr
import cv2
import numpy as np
from PIL import Image
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
import io

st.title("🥛 Allergy Detector from Food Labels")
st.markdown("Upload a food label image and check if it contains any allergens.")

# Upload Dataset CSV
st.sidebar.header("Step 1: Upload Allergen Dataset (CSV)")
csv_file = st.sidebar.file_uploader("Upload your CSV file", type=["csv"])

if csv_file is not None:
    df = pd.read_csv(csv_file)
    st.success("✅ Dataset Uploaded Successfully!")

    if "Food_Name" not in df.columns or "Allergic" not in df.columns:
        st.error("❌ ERROR: CSV must contain 'Food_Name' and 'Allergic' columns.")
    elif len(df["Allergic"].unique()) < 2:
        st.error("❌ ERROR: Dataset must have both allergic (1) and non-allergic (0) samples.")
    else:
        df["Food_Label"] = df["Food_Name"].astype("category").cat.codes
        X = df[["Food_Label"]]
        y = df["Allergic"]

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        model = LogisticRegression()
        model.fit(X_train, y_train)

        st.success("✅ AI Model Trained Successfully!")

        # Upload Food Label Image
        st.sidebar.header("Step 2: Upload Food Label Image")
        uploaded_img = st.sidebar.file_uploader("Upload an image file", type=["jpg", "png", "jpeg"])

        if uploaded_img is not None:
            image = Image.open(uploaded_img)
            st.image(image, caption="📷 Uploaded Image", use_column_width=True)

            # Convert image for OpenCV
            image_bytes = np.array(image.convert('RGB'))
            gray = cv2.cvtColor(image_bytes, cv2.COLOR_BGR2GRAY)

            # Preprocess image
            gray = cv2.GaussianBlur(gray, (3, 3), 0)
            gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
            kernel = np.ones((1, 1), np.uint8)
            gray = cv2.dilate(gray, kernel, iterations=1)
            gray = cv2.erode(gray, kernel, iterations=1)

            # OCR using EasyOCR
            reader = easyocr.Reader(['en'], gpu=False)
            result = reader.readtext(gray, detail=0)
            extracted_text = ' '.join(result)

            st.subheader("🔍 Extracted Text:")
            st.code(extracted_text)

            # Allergy Detection
            allergen_list = df["Food_Name"].tolist()
            matched_allergens = [word for word in extracted_text.split() if word.lower() in [a.lower() for a in allergen_list]]

            if matched_allergens:
                result_text = "⚠️ Allergic"
                st.error(f"⚠️ Warning! Found allergens: {', '.join(matched_allergens)}")
            else:
                result_text = "✅ Not Allergic"
                st.success("✅ No allergens detected.")

            st.subheader("🧪 Final Result:")
            st.info(result_text)
