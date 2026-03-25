FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# IMPORTANT FIX (Railway port issue solved)
CMD ["sh", "-c", "exec gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120"]