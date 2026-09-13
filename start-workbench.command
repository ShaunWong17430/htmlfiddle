#!/bin/sh
# HTML Fiddle - start the local visual HTML editor (macOS / Linux entry point)
#
# On macOS you may need to make this executable once:
#     chmod +x start-workbench.command
# then double-click it from Finder, or run it from a terminal.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)

# Validate a candidate by actually running it, not by mere presence: on macOS
# `python3` can exist as a stub that refuses to run until the Xcode command line
# tools are installed. launcher.py --version exits non-zero below Python 3.9.
find_python() {
  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 &&
       "$candidate" "$HERE/scripts/launcher.py" --version >/dev/null 2>&1; then
      PY="$candidate"
      return 0
    fi
  done
  return 1
}

if ! find_python; then
  echo "[ERROR] No usable Python 3.9+ found on PATH." >&2
  echo "        HTML Fiddle needs Python 3.9 or newer (standard library only)." >&2
  echo "        On macOS, 'python3' may exist as a stub until the Xcode" >&2
  echo "        command line tools are installed:  xcode-select --install" >&2
  exit 2
fi

exec "$PY" "$HERE/scripts/launcher.py" "$@"
