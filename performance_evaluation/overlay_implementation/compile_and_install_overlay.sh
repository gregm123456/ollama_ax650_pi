#!/usr/bin/env bash
set -euo pipefail

# compile_and_install_overlay.sh
# Compile cma-128mb.dts to a .dtbo and install it to /boot/firmware/overlays/
# Then enable via /boot/firmware/config.txt (creates backups).

# Use the conservative, safe 64MiB DTO by default
# Default to the most-conservative 16MiB DTO for testing across devices
DTS_SRC="$(dirname "$0")/cma-16mb.dts"
DTBO_NAME="cma-16mb.dtbo"
OVERLAY_BASE="${DTBO_NAME%.dtbo}"
OVERLAY_DIR="/boot/firmware/overlays"
CONFIG_TXT="/boot/firmware/config.txt"

if [ "$EUID" -ne 0 ]; then
  echo "This script requires sudo/root. Rerun with sudo." >&2
  exit 2
fi

# Ensure dtc is installed
if ! command -v dtc >/dev/null 2>&1; then
  echo "dtc (device tree compiler) is not installed. Installing..."
  apt-get update
  apt-get install -y device-tree-compiler
fi

# Compile
echo "Compiling $DTS_SRC -> $DTBO_NAME"
dtc -@ -I dts -O dtb -o "$DTBO_NAME" "$DTS_SRC"

# Backup overlay dir (best-effort) and copy
mkdir -p "$OVERLAY_DIR"
cp -a "$OVERLAY_DIR" "$OVERLAY_DIR".bak 2>/dev/null || true
cp -a "$DTBO_NAME" "$OVERLAY_DIR/"

# Backup config.txt
cp -a "$CONFIG_TXT" "$CONFIG_TXT".bak

# Add dtoverlay line if not present
if ! grep -qE "^\s*dtoverlay=${OVERLAY_BASE}\b" "$CONFIG_TXT"; then
  echo "dtoverlay=${OVERLAY_BASE}" >> "$CONFIG_TXT"
  echo "Added 'dtoverlay=${OVERLAY_BASE}' to $CONFIG_TXT (backup: $CONFIG_TXT.bak)"
else
  echo "dtoverlay=${OVERLAY_BASE} already present in $CONFIG_TXT"
fi

echo "Installed $DTBO_NAME to $OVERLAY_DIR and enabled via dtoverlay=${OVERLAY_BASE} in $CONFIG_TXT"

echo "Done. Review $CONFIG_TXT.bak and $OVERLAY_DIR.bak if you need to revert." 
