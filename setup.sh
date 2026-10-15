#!/bin/sh
set -eu

cd "$(dirname "$0")"

if [ -x .venv/bin/python ]; then
    setup_python=.venv/bin/python
else
    setup_python=
    for candidate in python3 python3.14 python3.13 python3.12 python3.11; do
        if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(not ((3, 11) <= sys.version_info[:2] <= (3, 14)))'; then
            setup_python=$candidate
            break
        fi
    done
    if [ -z "$setup_python" ]; then
        echo "Python 3.11–3.14 bulunamadı. Önce desteklenen bir Python sürümü yükleyin." >&2
        exit 1
    fi
fi

"$setup_python" -c 'import sys; sys.exit(0 if (3, 11) <= sys.version_info[:2] <= (3, 14) else "Python 3.11–3.14 gerekli.")'

if [ "$(uname -s)" = "Darwin" ]; then
    if ! command -v brew >/dev/null 2>&1; then
        echo "PDF kütüphaneleri için Homebrew gerekli: https://brew.sh" >&2
        exit 1
    fi
    if ! brew list --versions pango >/dev/null 2>&1; then
        brew install pango
    fi
fi

if [ ! -x .venv/bin/python ]; then
    "$setup_python" -m venv .venv
fi
.venv/bin/python -c 'import sys; sys.exit(0 if (3, 11) <= sys.version_info[:2] <= (3, 14) else "Mevcut .venv Python 3.11–3.14 kullanmalı.")'
.venv/bin/python -m pip install -r requirements.txt
echo "Kurulum tamamlandı. Çalıştırmak için: ./run.sh"
