## Overlay implementation — conservative 64MiB test

This directory contains staged files to implement and test a conservative CMA reservation (64MiB) using a Device Tree Overlay (DTO). The DTO is intentionally conservative and targets a high physical address to avoid reserving low RAM.

Goals
- Provide a minimal, safe DTO that reserves 64MiB at a high physical address (avoids low-memory overlap).
- Provide scripts to compile/install the overlay and to verify the reservation after reboot.
- Provide an optional, safe cmdline-based test script for `cma=128M` (only use as a diagnostic, not concurrently with DTO).

Files
- `cma-16mb.dts` — Device Tree Source to reserve 16MiB as a shared DMA pool at a safe base (default base used: `0x3a000000`). This is the most-conservative test for both 4GB and 16GB devices.
- `compile_and_install_overlay.sh` — compile the DTS to a DTBO, copy to `/boot/firmware/overlays/`, and enable in `/boot/firmware/config.txt` (creates backups). This script now builds `cma-16mb.dts` by default for the safest initial test.
- `safe_cmdline_cma_test.sh` — optionally append `cma=128M` to `/boot/firmware/cmdline.txt` safely (backup/restore). Use this only for isolated tests and remove `cma=` before using the DTO.
- `verify_cma.sh` — check `/proc/meminfo`, `dmesg`, and verify `cmdline.txt` is single-line and ends with a newline.
- `overlay_notes.md` — short comparison notes and recommended next steps.

How to use
1. Prefer the DTO approach. On the Pi, run (requires sudo):

```bash
sudo bash compile_and_install_overlay.sh
```

2. Reboot the system:

```bash
sudo reboot
```

3. After reboot, run the verifier (no sudo required for read-only checks):

```bash
./verify_cma.sh
```

Optional: if you want to test the kernel cmdline mechanism first (super-conservative 128MB), run the `safe_cmdline_cma_test.sh` script, then reboot. Do NOT leave `cma=` in `cmdline.txt` while testing the DTO.

Safety notes
- `cmdline.txt` must be a single line. The scripts back up `cmdline.txt` and `config.txt` before editing.
- Do not reserve low physical addresses (for example at or near `0x0`) — that can overlap kernel/firmware memory and break boot. This DTO intentionally uses a high base address observed to be accepted by the kernel (`0x3a000000`).
- If anything goes wrong, restore the backups created by the scripts (`*.bak`) before rebooting.

