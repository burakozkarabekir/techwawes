FROM python:3.11-slim

WORKDIR /app

# Bagimliliklar (once requirements -> katman cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama
COPY backend ./backend
COPY frontend ./frontend

# Host PORT degiskeni verir (Render/Railway). Lokalde 8000.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn backend.app:app --host 0.0.0.0 --port ${PORT}"]
