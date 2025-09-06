# Dockerfile
FROM python:3.11-slim

# Install OS packages required by tesseract & pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libtesseract-dev \
    libleptonica-dev \
    poppler-utils \
    gcc \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . /app

ENV PYTHONUNBUFFERED=1
ENV PORT=5000

EXPOSE 5000

# Use gunicorn to run the app; make sure app:app is correct (Flask instance name)
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000", "--workers", "4"]
