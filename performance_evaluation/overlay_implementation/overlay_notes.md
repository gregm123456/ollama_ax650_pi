# Overlay notes — delta vs existing docs

This file summarizes the minimal staged approach in this directory and the differences vs the repository documents `BOOT_CMA_SUMMARY.md` and `OVERLAY_NOTES.md`.

Summary
- We stage a *conservative* 128MB DTO to validate the overlay/reserved-memory mechanism without risking large early-boot failures.
- We provide both a DTO-based flow (preferred) and a super-conservative cmdline `cma=128M` test (optional) so you can validate which mechanism the kernel/firmware accepts on this exact image.

Differences vs existing docs
- `BOOT_CMA_SUMMARY.md` contains recovery steps, warns about editing the wrong cmdline file, and documents a previously created `cma-2g.dtbo` (2GiB) in `/boot/firmware/overlays/`.
- `OVERLAY_NOTES.md` recommends abandoning global `cma=` for the DTO method and shows a 2GiB DTO. This directory implements the same DTO concept but starts with 128MB as a low-risk first test.

Next steps
1. Run `sudo bash compile_and_install_overlay.sh`, reboot, and run `./verify_cma.sh`.
2. If DTO approach works, iterate the DTS to increase size (e.g., 256M -> 512M -> 2G) and/or adjust `reg` base if needed for 16GB Pi.
3. If DTO fails but cmdline `cma=128M` succeeds, capture dmesg and compare; then refine approach per `OVERLAY_NOTES.md`.
