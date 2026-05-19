#!/usr/bin/env bash
# Mouse Axis Remapper — launcher
# Activates the project venv and runs the app.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$SCRIPT_DIR/venv/bin/python3"

if [[ ! -f "$PYTHON" ]]; then
    echo "Virtual environment not found."
    echo "Please run:  bash \"$SCRIPT_DIR/setup.sh\""
    exit 1
fi

exec "$PYTHON" "$SCRIPT_DIR/main.py" "$@"
