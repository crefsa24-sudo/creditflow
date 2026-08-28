#!/usr/bin/env bash
# CrediFlow — script de arranque (Linux/macOS)
set -e
cd "$(dirname "$0")"

echo "→ Instalando dependencias..."
pip install -q -r requirements.txt

echo "→ Creando base de datos semilla..."
python backend/seed.py

echo "→ Iniciando servidor en http://localhost:8000/static/login.html"
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
