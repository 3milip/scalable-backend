#!/bin/bash
set -e
SETTINGS=/sio2/deployment/settings.py
MARKER="# scalable-backend adapter_report"
if ! grep -qF "$MARKER" "$SETTINGS"; then
  printf '\n%s\nimport extra_settings\nextra_settings.apply(globals())\n' "$MARKER" >> "$SETTINGS"
fi
exec /sio2/oioioi/oioioi_init.sh "$@"
