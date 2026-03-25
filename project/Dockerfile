FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["sh", "-c", "PORT=${PORT:-8080}; echo Starting on $PORT; exec gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120 --preload"]