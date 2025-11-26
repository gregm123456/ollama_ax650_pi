#!/usr/bin/env bash
set -euo pipefail

# verify_cma.sh
# Run post-boot checks for CMA reservation and file integrity.

echo "Checking /proc/meminfo for CMA totals..."
grep -i 'CmaTotal\|CmaFree' /proc/meminfo || echo "No CMA lines found"

echo "\nChecking dmesg for CMA or cma messages..."
dmesg | grep -i cma || echo "No CMA-related dmesg entries found"

echo "\nCheck kernel cmdline seen by kernel:"
cat /proc/cmdline

echo "\nCheck /boot/firmware/cmdline.txt is single line and ends with newline (if present)"
if [ -f /boot/firmware/cmdline.txt ]; then
  echo -n "Lines: "
  wc -l /boot/firmware/cmdline.txt
  echo -n "Last byte (print non-printable as octal): "
  tail -c1 /boot/firmware/cmdline.txt | od -An -t o1
else
  echo "/boot/firmware/cmdline.txt not present on this system"
fi

echo "\nDone. If you expected a CMA reservation, verify CmaTotal is non-zero and approximately the requested size." 
