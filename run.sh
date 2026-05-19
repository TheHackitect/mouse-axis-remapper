#!/usr/bin/env bash
# Mouse Axis Remapper — launcher
# Activates the project venv and ensures the 'input' group is active
# so /dev/input/* and /dev/uinput are accessible without a re-login.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$SCRIPT_DIR/venv/bin/python3"

if [[ ! -f "$PYTHON" ]]; then
    echo "Virtual environment not found."
    echo "Please run:  bash \"$SCRIPT_DIR/setup.sh\""
    exit 1
fi

# If 'input' group is not yet active in this session, re-exec under it.
# sg activates the group immediately without requiring a log-out.
if ! id -nG | grep -qw input; then
    exec sg input -c "\"$PYTHON\" \"$SCRIPT_DIR/main.py\""
fi

exec "$PYTHON" "$SCRIPT_DIR/main.py" "$@"
