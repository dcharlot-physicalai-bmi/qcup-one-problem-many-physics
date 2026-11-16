#!/bin/bash
# Run a Python script of this folder with the IonQ key in its environment, taken from the variable IONQ_API_KEY.
# The key is never echoed; only its length is checked. Usage: ionq.sh script.py args...
set -uo pipefail
IONQ_KEY=${IONQ_API_KEY:-}; [ -n "$IONQ_KEY" ] || { echo "set IONQ_API_KEY" >&2; exit 2; }
[ ${#IONQ_KEY} -ge 20 ] || { echo "IonQ key too short (${#IONQ_KEY})" >&2; exit 2; }
export IONQ_KEY
S=$1; shift
exec /usr/bin/python3 -E "$(dirname "$0")/$S" "$@"
