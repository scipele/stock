
#!/usr/bin/env bash

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_SCRIPT="$ROOT_DIR/py/intr_calc_main.py"

pause_if_interactive() {
    if [[ -t 0 ]]; then
        read -r -p "Press Enter to close..."
    fi
}

die() {
    echo "ERROR: $1" >&2
    pause_if_interactive
    exit 1
}

find_python() {
    local candidates=()
    if [[ -n "${INTR_CALC_PYTHON:-}" ]]; then
        candidates+=("$INTR_CALC_PYTHON")
    fi
    candidates+=(
        "$ROOT_DIR/../.venv/bin/python"
        "/home/dev/stock/.venv/bin/python"
        "/home/dev/py/.venv/bin/python"
        "python3"
    )

    local candidate
    for candidate in "${candidates[@]}"; do
        if command -v "$candidate" >/dev/null 2>&1; then
            command -v "$candidate"
            return 0
        elif [[ -x "$candidate" ]]; then
            echo "$candidate"
            return 0
        fi
    done

    return 1
}

[[ -f "$PYTHON_SCRIPT" ]] || die "Python script not found: $PYTHON_SCRIPT"

PYTHON="$(find_python)" || die "No usable Python interpreter found."

if ! "$PYTHON" -c "import tkinter, matplotlib" >/dev/null 2>&1; then
    cat >&2 <<'EOF'
ERROR: Required Python modules are missing for this launcher.

Recommended fix from repository root:
  python3 -m venv .venv
  . .venv/bin/activate
  python -m pip install -r intr_calc/requirements.txt
EOF
    pause_if_interactive
    exit 1
fi

 "$PYTHON" "$PYTHON_SCRIPT"
status=$?
if [[ $status -ne 0 ]]; then
    echo "Program exited with status $status." >&2
    pause_if_interactive
    exit "$status"
fi
