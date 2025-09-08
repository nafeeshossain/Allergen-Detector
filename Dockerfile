# Use a standard Python 3.11 base image
FROM python:3.11-slim-bullseye

# Set environment variables for best practice
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory
WORKDIR /app

# Update apt, install Tesseract, and clean up to keep the image small
RUN apt-get update && apt-get install -y tesseract-ocr --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Copy and install Python requirements using python's own pip module
COPY requirements.txt .
RUN python -m pip install --upgrade pip && \
    python -m pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Command to run the application (using python -m to find gunicorn)
CMD python -m gunicorn app:app --bind 0.0.0.0:$PORT
