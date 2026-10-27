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
[[ -z "${DATABASE_URL:-}" ]] || stop_with_message "Unset DATABASE_URL before resetting a local development database."
# Local rehearsals must never consume the production treatment-allocation queue.
export TREATMENT_ALLOCATION_NAMESPACE=development

clear
echo "Undemocratic Reversals — development server"
echo "Project: $PROJECT_DIR"
echo
echo "Resetting the local development database..."
"$OTREE_BIN" resetdb --noinput || stop_with_message "The database reset failed."
# Stamp the freshly reset development database for oTree's in-memory loader.
"$SCRIPT_DIR/.venv/bin/python" -c 'import sqlite3; from otree.database import version_for_pragma; connection = sqlite3.connect("db.sqlite3"); connection.execute(f"PRAGMA user_version = {version_for_pragma()}"); connection.commit(); connection.close()' || stop_with_message "The development database version could not be recorded."

echo
echo "Starting oTree at http://localhost:$PORT"
echo "Keep this Terminal window open while testing."
echo "Press Control-C here to stop the server."
echo

( sleep 2; open "http://localhost:$PORT" ) &
exec "$SCRIPT_DIR/.venv/bin/python" study_server.py devserver_inner "$PORT"
