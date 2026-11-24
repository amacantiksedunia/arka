"""
Titik masuk untuk Vercel (Vercel mencari objek Flask bernama `app` di index.py).
Untuk menjalankan di laptop tetap pakai:  cd backend  ->  py app.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

from app import app, ensure_db  # noqa: E402  (backend/app.py)

ensure_db()   # buat database + data contoh bila belum ada (di Vercel: /tmp/arka.db)
