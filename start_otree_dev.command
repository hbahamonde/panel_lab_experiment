#!/bin/zsh

set -u

SCRIPT_DIR="${0:A:h}"
PROJECT_DIR="$SCRIPT_DIR/otree_project"
OTREE_BIN="$SCRIPT_DIR/.venv/bin/otree"
PORT=8000

function stop_with_message() {
    echo
    echo "Could not start the development server."
    echo "$1"
    echo
    read "?Press Return to close this window."
    exit 1
}

[[ -x "$OTREE_BIN" ]] || stop_with_message "Expected oTree at: $OTREE_BIN"
[[ -f "$PROJECT_DIR/settings.py" ]] || stop_with_message "Could not find: $PROJECT_DIR/settings.py"

cd "$PROJECT_DIR" || stop_with_message "Could not enter the oTree project folder."

clear
echo "Undemocratic Reversals — development server"
echo "Project: $PROJECT_DIR"
echo
echo "Resetting the local development database..."
"$OTREE_BIN" resetdb --noinput || stop_with_message "The database reset failed."

echo
echo "Starting oTree at http://localhost:$PORT"
echo "Keep this Terminal window open while testing."
echo "Press Control-C here to stop the server."
echo

( sleep 2; open "http://localhost:$PORT" ) &
exec "$OTREE_BIN" devserver "$PORT"
