# Overlay notes — delta vs existing docs

This file summarizes the minimal staged approach in this directory and the differences vs the repository documents `BOOT_CMA_SUMMARY.md` and `OVERLAY_NOTES.md`.

Summary
- We stage a *conservative* 64MiB DTO to validate the overlay/reserved-memory mechanism without risking large early-boot failures. The DTO targets a high physical address to avoid conflicts with low-memory kernel/firmware regions.
- We provide both a DTO-based flow (preferred) and a super-conservative cmdline `cma=128M` test (optional) so you can validate which mechanism the kernel/firmware accepts on this exact image. Do not use both at the same time.
 - We stage a *most-conservative* 16MiB DTO to validate the overlay/reserved-memory mechanism across both 4GB and 16GB devices. This smaller reservation reduces risk while still exercising the overlay mechanism.

Differences vs existing docs
- `BOOT_CMA_SUMMARY.md` contains recovery steps, warns about editing the wrong cmdline file, and documents a previously created `cma-2g.dtbo` (2GiB) in `/boot/firmware/overlays/`.
- `OVERLAY_NOTES.md` recommends abandoning global `cma=` for the DTO method and shows a 2GiB DTO. This directory implements the same DTO concept but starts with 64MiB at a safe base (observed `0x3a000000`) as a conservative first test.

## Update: 2025-11-26 - Syntax Fix for Reserved Memory

The previous `cma-16mb.dts` failed with "reserved memory unsupported node format, ignoring". This was due to incorrect syntax for the `reserved-memory` node overlay.

We have created a new test overlay `cma-test-16m.dts` using the canonical syntax for `shared-dma-pool`:
- Uses `size` and `alignment` instead of fixed `reg` (allows kernel to place it safely).
- Adds `linux,cma-default;` to ensure it's used as the default CMA pool.
- Targets `<&reserved_memory>` correctly.

This new overlay has been compiled to `cma-test-16m.dtbo` and enabled in `config.txt`.

Next steps
1. Run `sudo bash compile_and_install_overlay.sh`, reboot, and run `./verify_cma.sh`.
2. If DTO approach works, iterate the DTS to increase size (e.g., 128M -> 256M -> 512M -> 2G) and/or adjust `reg` base if needed for 16GB Pi.
3. If DTO fails but cmdline `cma=128M` succeeds, capture dmesg and compare; then refine approach per `OVERLAY_NOTES.md`.
