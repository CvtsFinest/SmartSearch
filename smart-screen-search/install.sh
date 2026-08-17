#!/usr/bin/env bash
set -e

echo "Installing SmartSearch system dependencies..."
sudo apt update
sudo apt install -y python3 python3-venv python3-pip tesseract-ocr python3-tk scrot

ENV_DIR="$HOME/.smartsearch-env"

if [ ! -d "$ENV_DIR" ]; then
  python3 -m venv "$ENV_DIR"
fi

source "$ENV_DIR/bin/activate"
python -m pip install --upgrade pip
pip install -r "$(dirname "$0")/requirements.txt"

echo
echo "SmartSearch is ready."
echo "Run:"
echo "  source ~/.smartsearch-env/bin/activate"
echo "  python smartsearch.py"
