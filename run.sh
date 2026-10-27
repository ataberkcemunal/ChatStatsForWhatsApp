#!/bin/sh
set -eu

cd "$(dirname "$0")"

# Let WeasyPrint find native libraries installed by Homebrew on macOS.
if [ "$(uname -s)" = "Darwin" ]; then
    export DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib:/usr/local/lib${DYLD_FALLBACK_LIBRARY_PATH:+:$DYLD_FALLBACK_LIBRARY_PATH}"
fi

if [ -x .venv/bin/python ]; then
    python=.venv/bin/python
elif [ -x venv/bin/python ]; then
    python=venv/bin/python
else
    echo "Python environment missing. Run ./setup.sh first." >&2
    exit 1
fi

if [ "$#" -eq 0 ]; then
    set -- _chat.txt
fi

exec "$python" ChatStatsForWhatsApp.py "$@"
