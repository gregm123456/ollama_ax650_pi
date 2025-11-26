Overlay implementation — status and next actions

Current status (as of this run):
- `cma-16mb.dts` compiled to `cma-16mb.dtbo` and copied to `/boot/firmware/overlays/` on the mounted target filesystem.
- `dtoverlay=cma-16mb` was appended to `/boot/firmware/config.txt`. A backup of the original `config.txt` was saved as `/boot/firmware/config.txt.bak`.
- A best-effort backup of the overlays directory was created at `/boot/firmware/overlays.bak` (if an overlays directory existed previously).

Recommended test order:
- Test on the 4GB Pi first. The `cma-16mb` overlay reserves a very small amount of memory and uses a base address that was observed working in prior logs. The 4GB device provides faster recovery and easier debugging.
- If the 4GB boot succeeds and `CmaTotal` shows the expected reserved amount, repeat the test on the 16GB Pi.

Quick verification steps (after boot):

```bash
# Verify kernel sees the reserved CMA pool
grep -i 'CmaTotal\|CmaFree' /proc/meminfo
dmesg | egrep -i 'Reserved memory|linux,cma|CMA|cma=' -n

# Run the included verifier script
cd performance_evaluation/overlay_implementation
./verify_cma.sh
```

Undo steps (if boot fails) — when mounted from recovery media:

1. Mount the target filesystem at `/mnt/target`.
2. Restore the backed-up `config.txt` and remove the installed DTBO:

```bash
sudo cp -a /mnt/target/boot/firmware/config.txt.bak /mnt/target/boot/firmware/config.txt
sudo rm -f /mnt/target/boot/firmware/overlays/cma-16mb.dtbo
if [ -d /mnt/target/boot/firmware/overlays.bak ]; then
  sudo rm -rf /mnt/target/boot/firmware/overlays
  sudo mv /mnt/target/boot/firmware/overlays.bak /mnt/target/boot/firmware/overlays
fi
sync
```

More general recovery instructions are in `UNDO.md` in this directory.

Notes:
- Do NOT keep any `cma=` token in `/boot/firmware/cmdline.txt` while testing DTOs — mixed methods can cause inconsistencies.
- The overlay is intentionally tiny (16MiB) to reduce risk. If this test succeeds, we can scale up gradually.
