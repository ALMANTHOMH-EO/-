#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
if ! command -v python >/dev/null 2>&1; then
  pkg install -y python
fi
python -m pip install --upgrade pip
python -m pip install -r requirements-termux.txt
export COOKIE_SECURE=false
mkdir -p data
exec uvicorn app.main:app --host 127.0.0.1 --port 8000
