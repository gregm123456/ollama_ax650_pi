Overlay implementation — status and next actions

Current status (as of this run):
- Modified `cma-test-16m.dts` to target the existing `/reserved-memory/linux,cma` node in the base DT and override its `reg` property to reserve 16 MiB instead of the default 64 MiB (keeping base address `0x3a000000`).
- Compiled the updated `cma-test-16m.dts` to `cma-test-16m.dtbo`.
- Installed `cma-test-16m.dtbo` to `/boot/firmware/overlays/` (overwriting the previous version).
- `config.txt` already has `dtoverlay=cma-test-16m` appended.
- System ready to reboot and verify the CMA reservation is now 16 MiB.

Recommended test order:
- Reboot and verify on the current Pi. The overlay now modifies the base DT's CMA node directly, which should reduce the reservation to 16 MiB.
- If successful, we can scale up to larger sizes by editing the DTS and recompiling.

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
2. Remove the dtoverlay line from `config.txt` and remove the DTBO:

```bash
sudo sed -i '/^\s*dtoverlay=cma-test-16m\b/d' /mnt/target/boot/firmware/config.txt
sudo rm -f /mnt/target/boot/firmware/overlays/cma-test-16m.dtbo
sync
```

More general recovery instructions are in `UNDO.md` in this directory.

Notes:
- The overlay now modifies the base DT's `linux,cma` node instead of adding a new one, which should make the 16 MiB reservation take effect.
- Do NOT add `cma=` to `/boot/firmware/cmdline.txt` while testing DTOs — stick to one method.
- If this works, we can edit `cma-test-16m.dts` to increase the size (e.g., `0x80000000` for 2 GiB) and recompile for the 16GB Pi.
