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
 - If this works, we can edit `cma-test-16m.dts` to increase the size (e.g., `0x80000000` for 2 GiB) and recompile for the 16GB Pi.

**Suspicious run details (summary for triage)**

- When suspicion arose: attempting to get the AX650 runtime (`main_api_axcl_aarch64`) to load the Qwen3-4B model into the NPU caused host-side allocation failures.

- Representative commands and observed outputs (capture these when handing off):
	- `egrep -i 'CmaTotal|CmaFree' /proc/meminfo`
		- before changes: `CmaTotal:          65536 kB` / `CmaFree: 42016 kB`
		- after attempted `cma=2048M` or overlay changes: `CmaTotal: 0 kB` / `CmaFree: 0 kB`
	- `axcl-smi info --cmm -d 0` — device-side memory reported: `CMM Total : 7208960 KiB`, `CMM Used : 18876 KiB` (NPU memory present/healthy)
	- Kernel boot log snippets: `OF: reserved mem: node linux,cma compatible matching fail`, `cma: Failed to reserve 2048 MiB on node -1`, and `Reserved memory: bypass linux,cma node, using cmdline CMA params instead`.
	- Early-boot symptom observed when `cmdline.txt` parsing failed: `hctosys: unable to read the hardware clock`.

- Actions performed that triggered the issue:
	- Appended `cma=2048M` to the boot cmdline (initially to the wrong helper file, later to `/boot/firmware/cmdline.txt`) and attempted reboot.
	- Created `performance_evaluation/cma-2g.dts`, compiled to `cma-2g.dtbo`, copied to `/boot/firmware/overlays/`, and added `dtoverlay=cma-2g` to `/boot/firmware/config.txt`.
	- Observed boot failures and kernel messages above; `axcl-smi` continued to show the NPU's CMM as present.

- Interpretation: the NPU's memory (CMM) is present and large enough, but the host kernel will not or cannot reserve the requested contiguous region. Host-side CMA reservation / OF compatibility appears to be the blocking issue (not the NPU hardware itself).

- Recommended logs to attach for upstream triage: `/proc/cmdline`, `/proc/meminfo` (CMA lines), `dmesg` filtered for `cma|reserved|axcl|axera|alloc`, `axcl-smi info --cmm -d 0`, and the exact `/boot/firmware/cmdline.txt` and `/boot/firmware/config.txt` contents plus the created DTS/DTBO files.
