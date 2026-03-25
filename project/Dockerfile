FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure logs are not buffered so Railway can show them immediately
ENV PYTHONUNBUFFERED=1

# 🔥 FINAL FIX: Use shell form CMD to correctly expand the $PORT environment variable provided by Railway
CMD gunicorn app:app --bind 0.0.0.0:${PORT:-8080} --workers 2 --threads 4 --timeout 120