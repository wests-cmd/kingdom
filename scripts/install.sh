#!/usr/bin/env bash
set -e

echo "=== Kingdom Installer v40.2 ==="

OS="$(uname -s)"
ARCH="$(uname -m)"

echo "Detected OS: ${OS} (${ARCH})"

case "${OS}" in
    Linux*)     PLATFORM="Linux";;
    Darwin*)    PLATFORM="macOS";;
    CYGWIN*|MINGW*|MSYS*) PLATFORM="Windows";;
    *)          PLATFORM="Unknown:${OS}";;
esac

echo "Platform: ${PLATFORM}"

command -v python3 >/dev/null 2>&1 || { echo "Error: python3 is required but not installed." >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "Error: npm is required but not installed." >&2; exit 1; }

echo "Creating Python Virtual Environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate || source venv/Scripts/activate

echo "Installing Python Dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Installing Frontend Dependencies & Building UI..."
if [ -d "frontend" ]; then
    cd frontend
    npm install
    npm run build
    cd ..
fi

echo "=== Installation Verification ==="
python3 -c "import fastapi, pydantic, uvicorn; print('Backend runtime dependencies verified.')"

echo "Kingdom v40.2 Installation Complete."
