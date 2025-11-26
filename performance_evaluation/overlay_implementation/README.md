# Overlay implementation — conservative 128MB test

This directory contains staged files to implement and test a conservative CMA reservation (128MB) using a Device Tree Overlay (DTO), plus a safe cmdline test as an optional, conservative check.

Goals
- Provide a minimal, safe DTO to reserve 128MB.
- Provide scripts to compile/install the overlay and to verify the reservation after reboot.
- Provide a safe cmdline-based test script for `cma=128M` (optional) for quick verification.

Files
- `cma-128mb.dts` — Device Tree Source to reserve 128MB as a shared DMA pool.
- `compile_and_install_overlay.sh` — compile the DTS to a DTBO, copy to `/boot/firmware/overlays/`, and enable in `/boot/firmware/config.txt` (creates backups).
- `safe_cmdline_cma_test.sh` — optionally append `cma=128M` to `/boot/firmware/cmdline.txt` safely (backup/restore). Use this only if you want to verify kernel cmdline accepts a small CMA.
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

Optional: if you want to test the kernel cmdline mechanism first (super-conservative 128MB), run:

```bash
sudo bash safe_cmdline_cma_test.sh
# then reboot
sudo reboot
```

Safety notes
- `cmdline.txt` must be a single line. The scripts back up `cmdline.txt` and `config.txt` before editing.
- If anything goes wrong, restore the backups created by the scripts (`*.bak`) before rebooting.

