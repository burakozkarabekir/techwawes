#!/usr/bin/env bash
# Finansal Analist - kurulum + calistirma
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "[kurulum] sanal ortam olusturuluyor..."
  python3 -m venv .venv
fi
source .venv/bin/activate

echo "[kurulum] bagimliliklar yukleniyor..."
pip install -q -r requirements.txt

echo "[bilgi] dashboard: http://127.0.0.1:8000"
uvicorn backend.app:app --host 127.0.0.1 --port 8000
