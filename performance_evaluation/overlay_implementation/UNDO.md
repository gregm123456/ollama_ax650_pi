UNDO — Revert overlay and cmdline edits (mount-based manual revert)

Purpose

If the DTO or cmdline edits made by the helper scripts cause a boot failure, use these steps to revert the changes from alternate/safe media. This document assumes you booted from safe media (another SD card, USB, or recovery image) and mounted the target filesystem (the Pi root/boot) at a mountpoint (example: `/mnt/target`). Adjust paths if you mounted elsewhere.

Notes
- Paths in this repo's scripts target `/boot/firmware/` as the boot partition. When mounted under `/mnt/target`, these paths become `/mnt/target/boot/firmware/`.
- The staged overlay file names are `cma-128mb.dtbo`, `cma-16mb.dtbo`, or `cma-test-16m.dtbo` (sources kept in the repo). Scripts also create backups with `.bak` suffixes; this file shows how to restore them.
- These commands must be run on the recovery system (not the broken system), with the target filesystem mounted read-write.

Preparation: identify the target device and mount point

1. Find the device node for the Pi's root/boot (for example, `/dev/sda1`, `/dev/mmcblk0p1`). Use `lsblk` or `blkid`.

2. Mount the root and boot if not already mounted. Example mounts:

```bash
# create mountpoint
sudo mkdir -p /mnt/target
# mount the root fs (example)
sudo mount /dev/mmcblk0p2 /mnt/target
# mount the boot/firmware partition (example)
sudo mount /dev/mmcblk0p1 /mnt/target/boot/firmware
```

Replace device nodes with the ones from your system.

Paths used below (when target is mounted at /mnt/target):
- Boot firmware directory: /mnt/target/boot/firmware
- Overlays dir: /mnt/target/boot/firmware/overlays
- config.txt: /mnt/target/boot/firmware/config.txt
- cmdline.txt: /mnt/target/boot/firmware/cmdline.txt

Step A — Restore `config.txt` and remove dtoverlay line

1. If a backup `config.txt.bak` exists, restore it (preferred):

```bash
if [ -f /mnt/target/boot/firmware/config.txt.bak ]; then
  sudo cp -a /mnt/target/boot/firmware/config.txt.bak /mnt/target/boot/firmware/config.txt
  echo "Restored config.txt from config.txt.bak"
else
  # Otherwise remove any dtoverlay=cma-* lines added by the script or manual edits
  sudo sed -i '/^\s*dtoverlay=cma-128mb\b/d' /mnt/target/boot/firmware/config.txt
  sudo sed -i '/^\s*dtoverlay=cma-16mb\b/d' /mnt/target/boot/firmware/config.txt
  sudo sed -i '/^\s*dtoverlay=cma-test-16m\b/d' /mnt/target/boot/firmware/config.txt
  echo "Removed dtoverlay=cma-* lines from config.txt (if present)"
fi
```

2. If you edited `config.txt` manually and want to preserve other changes, prefer removing only the dtoverlay line as above.

Step B — Remove the compiled overlay (dtbo)

1. Remove any `cma-*.dtbo` files from overlays:

```bash
sudo rm -f /mnt/target/boot/firmware/overlays/cma-128mb.dtbo
sudo rm -f /mnt/target/boot/firmware/overlays/cma-16mb.dtbo
sudo rm -f /mnt/target/boot/firmware/overlays/cma-test-16m.dtbo
```

2. If you created an overlays backup directory (script attempted to copy `/boot/firmware/overlays` to `/boot/firmware/overlays.bak`), you can restore it completely:

```bash
if [ -d /mnt/target/boot/firmware/overlays.bak ]; then
  sudo rm -rf /mnt/target/boot/firmware/overlays
  sudo mv /mnt/target/boot/firmware/overlays.bak /mnt/target/boot/firmware/overlays
  echo "Restored overlays dir from overlays.bak"
fi
```

Step C — Restore `cmdline.txt` backup (if safe_cmdline_cma_test.sh was used)

1. The safe cmdline test creates `/boot/firmware/cmdline.txt.bak-overlay-test`. Restore it if present:

```bash
if [ -f /mnt/target/boot/firmware/cmdline.txt.bak-overlay-test ]; then
  sudo cp -a /mnt/target/boot/firmware/cmdline.txt.bak-overlay-test /mnt/target/boot/firmware/cmdline.txt
  echo "Restored cmdline.txt from cmdline.txt.bak-overlay-test"
else
  # Otherwise, remove any cma= tokens we might have added
  sudo sed -i 's/ cma=[^[:space:]]\+//g' /mnt/target/boot/firmware/cmdline.txt
  # Ensure single-line integrity by joining lines (should be a single line)
  sudo awk 'BEGIN{ORS=""} {gsub("\n"," "); print $0} END{print "\n"}' /mnt/target/boot/firmware/cmdline.txt > /tmp/cmdline.fixed
  sudo mv /tmp/cmdline.fixed /mnt/target/boot/firmware/cmdline.txt
  echo "Removed cma= tokens and fixed cmdline.txt single-line format"
fi
```

Step D — Verify file permissions and newline

1. Ensure `cmdline.txt` is a single line and ends with a newline:

```bash
wc -l /mnt/target/boot/firmware/cmdline.txt
# Show last byte as octal to confirm newline (expected 012)
tail -c1 /mnt/target/boot/firmware/cmdline.txt | od -An -t o1
```

2. If needed, force a trailing newline:

```bash
sudo bash -c 'if [ -n "$(tail -c1 /mnt/target/boot/firmware/cmdline.txt)" ]; then echo >> /mnt/target/boot/firmware/cmdline.txt; fi'
```

Step E — Clean up any helper artifacts created by the scripts

1. Remove the dtbo file from the repo copy (if you copied it into the target overlays directory earlier and prefer a clean state) — already handled above.
2. Remove any temporary backup files you don't want to keep. Example (use with care):

```bash
# WARNING: only run if you're sure you want to remove backups
# sudo rm -f /mnt/target/boot/firmware/config.txt.bak
# sudo rm -rf /mnt/target/boot/firmware/overlays.bak
# sudo rm -f /mnt/target/boot/firmware/cmdline.txt.bak-overlay-test
```

Step F — Sync and unmount

```bash
sudo sync
sudo umount /mnt/target/boot/firmware || true
sudo umount /mnt/target || true
```

Step G — Reboot into the repaired system

Remove the recovery media and boot from the Pi's SD/target device. Monitor the serial console or HDMI if you have it, and confirm it boots normally.

Troubleshooting

- If the system still fails to boot, capture the bootloader/firmware UART or serial messages if available.
- If you restored backups but still see the dtoverlay line in `config.txt`, double-check you edited the correct `config.txt` (some images use `/boot/config.txt` or other mounts) — confirm where the firmware partition is mounted.
- If you are unsure which partition is boot, use `blkid` and `lsblk -f` to inspect labels and mounts.

Advanced: explicitly remove overlay DTB references from config.txt in a safe way

If you have a complex `config.txt` and prefer not to fully restore the backup, you can remove only the overlay lines and leave everything else intact:

```bash
sudo sed -i.bak '/^\s*dtoverlay=cma-128mb\b/d' /mnt/target/boot/firmware/config.txt
sudo sed -i.bak '/^\s*dtoverlay=cma-16mb\b/d' /mnt/target/boot/firmware/config.txt
sudo sed -i.bak '/^\s*dtoverlay=cma-test-16m\b/d' /mnt/target/boot/firmware/config.txt
# This creates config.txt.bak with the pre-edit version
```

Final notes

- These steps assume the scripts in `performance_evaluation/overlay_implementation/` were used or manual edits similar to them. If you made different edits, adapt accordingly.
- If you want, copy this `UNDO.md` off the SD card and keep it with your recovery media for quick access.

Actions performed on mounted /media volumes (by me during this recovery session)

Date: 2025-11-26

I performed a minimal, reversible undo for the most recent failed CMA DTO overlay test. I moved test artifacts (rather than permanently deleting them) so they can be restored if needed. Exact commands run (logged here for traceability):

sudo sed -i '/^\s*dtoverlay=cma-test-16m\b/d' /media/gregm/bootfs/config.txt
sudo rm -f /media/gregm/bootfs/overlays/cma-test-16m.dtbo
sudo mv /media/gregm/bootfs/overlays/cma-16mb.dtbo /media/gregm/bootfs/overlays/cma-16mb.dtbo.removed-by-test
sudo mv /media/gregm/bootfs/cmdline_1024broken.txt /media/gregm/bootfs/cmdline_1024broken.txt.removed-by-test
sudo sync

Result summary:
- Removed `dtoverlay=cma-test-16m` line from `/media/gregm/bootfs/config.txt` (if present).
- Deleted `/media/gregm/bootfs/overlays/cma-test-16m.dtbo` (explicit test DTBO).
- Moved `/media/gregm/bootfs/overlays/cma-16mb.dtbo` to `/media/gregm/bootfs/overlays/cma-16mb.dtbo.removed-by-test` (this was a test artifact).
- Moved `/media/gregm/bootfs/cmdline_1024broken.txt` to `/media/gregm/bootfs/cmdline_1024broken.txt.removed-by-test` (a leftover containing a malformed `cma=1024M` attempt).
- Left stock files alone (for example `/media/gregm/bootfs/overlays/cma.dtbo` and `/media/gregm/bootfs/overlays/cma-2g.dtbo.disabled` were not removed).

Recommended next steps for you (safe):
1. Inspect `/media/gregm/bootfs/overlays` to verify only the `.removed-by-test` copies of test files are present and that `cma.dtbo` remains.
2. If everything looks good, unmount and boot from the target SD card/drive to confirm normal boot.
3. If you prefer to permanently delete the moved files after several successful boots, you can remove the `.removed-by-test` filenames.

If you want, I can also restore the entire `config.txt` from `/media/gregm/bootfs/config.txt.bak` now — say `restore-config` — but it's not required because the dtoverlay line was removed already.

