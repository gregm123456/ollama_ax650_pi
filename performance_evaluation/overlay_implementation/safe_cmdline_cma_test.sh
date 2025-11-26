#!/usr/bin/env bash
set -euo pipefail

# safe_cmdline_cma_test.sh
# Safely test cma=128M by editing /boot/firmware/cmdline.txt (creates backup).

CMDLINE="/boot/firmware/cmdline.txt"
BACKUP="${CMDLINE}.bak-overlay-test"

if [ "$EUID" -ne 0 ]; then
  echo "This script requires sudo/root. Rerun with sudo." >&2
  exit 2
fi

if [ ! -f "$CMDLINE" ]; then
  echo "$CMDLINE not found. Are you on a Raspberry Pi with /boot/firmware mounted?" >&2
  exit 3
fi

# Backup
cp -a "$CMDLINE" "$BACKUP"

# Remove any existing cma= tokens
sed -i 's/ cma=[^[:space:]]\+//g' "$CMDLINE"

# Append cma=128M safely at end of single-line file
# Use sed to append without adding newlines elsewhere
sed -i 's/$/ cma=128M/' "$CMDLINE"

# Ensure file ends with a single newline
# If last char isn't newline, append one (portable way)
if [ -n "$(tail -c1 "$CMDLINE")" ]; then
  echo >> "$CMDLINE"
fi

# Show resulting single-line check
echo "After edit, /boot/firmware/cmdline.txt has $(wc -l < "$CMDLINE") lines (should be 1)"

echo "Backup saved to: $BACKUP"

echo "Now reboot to test. If you need to revert before reboot, run:\n  sudo cp -a $BACKUP $CMDLINE" 
