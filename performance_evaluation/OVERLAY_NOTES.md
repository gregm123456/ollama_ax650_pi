This confirms a much more critical and unusual issue: the **global `cma=` kernel parameter is fundamentally breaking the boot sequence** on your Raspberry Pi 5 and Ubuntu installation, regardless of RAM size or a conservative value like `cma=128MB`.

Since the single-line syntax for `cmdline.txt` is confirmed correct, the failure is happening when the kernel attempts to process and reserve the memory, causing an early-boot crash that manifests as the "hardware clock error" symptom.

The next step is to **abandon the `cma=` kernel command line parameter** and focus on the **Device Tree Overlay (DTO)** method, which is the proper, explicit mechanism for reserving large, non-standard memory regions for PCIe devices on the Raspberry Pi 5.

Here is the plan to proceed with the DTO:

### 1\. Disable All Command-Line CMA

First, ensure your Pi is bootable and stable.

  * Edit `/boot/firmware/cmdline.txt` and ensure there are **no `cma=`** tokens remaining. The system must boot reliably without it.

-----

### 2\. Verify and Re-enable the Device Tree Overlay

Your previous notes indicate that an overlay (`cma-2g.dts`/`cma-2g.dtbo`) was created and copied, but you later disabled it to recover the system.

The correct way to allocate a large, specific region like the 2GiB required for your LLM is via a DT overlay that uses the reserved-memory framework, as this approach is more stable than the global `cma=` parameter.

The process is:

1.  **Ensure the DTBO file is in place:**
    The compiled overlay file (`cma-2g.dtbo`) must be in `/boot/firmware/overlays/`.

2.  **Edit `/boot/firmware/config.txt`:**
    Add or ensure the following line is present (and not commented out):

    ```ini
    dtoverlay=cma-2g
    ```

3.  **Check the DTO Source (`cma-2g.dts`)**:
    If the system *still* fails to boot with *only* the overlay enabled (and no `cma=` in `cmdline.txt`), the issue lies within the `.dts` source file itself. A correct DTO for a 2GiB reservation would look something like this (for context):

    ```dts
    /dts-v1/;
    / {
        compatible = "brcm,bcm2712";
        fragment@0 {
            target = <&reserved_memory>;
            __overlay__ {
                cma_2g: cma_2g {
                    compatible = "shared-dma-pool";
                    reusable;
                    reg = <0x0 0x0 /* Base, let kernel pick low 4GB base */
                           0x0 0x80000000>; /* 2GiB (2,147,483,648 bytes) */
                };
            };
        };
    };
    ```

If you have confirmed steps 1 and 2, but the boot still fails, the specific kernel/firmware combination on your **Ubuntu 24.04** install may have a conflict with how it handles the **`cma_2g`** node, or your NPU driver is not binding to the reserved region correctly.

-----

### 3\. Final Search: DTO Conflicts and Axera

We need to specifically look for known conflicts between large memory overlays and the RPi 5's boot firmware or the Ubuntu kernel.
This is a crucial finding. The failure on the 4GB model confirms that the **global `cma=` kernel command line parameter is fundamentally conflicting with the Raspberry Pi 5 boot process on Ubuntu**, regardless of the size of the reservation or the 16GB memory map issue.

Since the `cma=` parameter is unstable, you must **abandon this method** entirely.

The **correct, stable, and necessary** approach for reserving a large 2 GiB memory block for a PCIe device like the Axera AX650 is by using a **Device Tree Overlay (DTO)**.

Your next steps should be to revert your system to a stable configuration and implement the DTO precisely.

-----

## 1\. Revert to Stable Configuration

Before proceeding, ensure your system is bootable and all previous failing parameters are removed.

1.  **Remove the CMA parameter:** Edit `/boot/firmware/cmdline.txt` (the correct file) and **remove** the `cma=128MB` parameter entirely. Your system must boot reliably without it.
2.  **Remove any DTO attempt:** In `/boot/firmware/config.txt`, ensure any line that starts with `dtoverlay=cma-` or refers to your previous memory reservation overlay is **commented out** or removed.

-----

## 2\. Implement the Correct Device Tree Overlay (DTO)

A DTO is the proper Linux mechanism for reserving specific, large memory pools for hardware. You need a `.dts` file that reserves the memory and then compile it into a `.dtbo` file that the bootloader loads.

### Step A: Find the Working 2GiB DTO

The standard DTO syntax must be correct to avoid the boot failure you previously experienced.
This is a crucial finding. The failure on the 4GB model confirms that the **global `cma=` kernel command line parameter is fundamentally conflicting with the Raspberry Pi 5 boot process on Ubuntu**, regardless of the size of the reservation or the 16GB memory map issue. The "hardware clock error" is a common symptom of early boot failure when the kernel command line is not parsed correctly or memory allocation fails early.

Since the `cma=` parameter is unstable, you must **abandon this method** entirely.

The **correct, stable, and necessary** approach for reserving a large 2 GiB memory block for a PCIe device like the Axera AX650 is by using a **Device Tree Overlay (DTO)**.

The next steps focus on creating and implementing a working Device Tree Overlay for a 2 GiB reserved memory block.

-----

## 1\. Revert to Stable Configuration

First, ensure your system is bootable and all previous failing parameters are removed.

1.  **Remove the CMA parameter:** Edit `/boot/firmware/cmdline.txt` (the correct file) and **remove** the `cma=128MB` parameter entirely. Your system must boot reliably without it.
2.  **Remove any DTO attempt:** In `/boot/firmware/config.txt`, ensure any line that starts with `dtoverlay=cma-` or refers to your previous memory reservation overlay is **commented out** or removed.

-----

## 2\. Implement the Correct Device Tree Overlay (DTO)

This process involves creating a Device Tree Source (`.dts`) file, compiling it to a Binary Overlay (`.dtbo`), and telling the bootloader to load it.

### A. Create the Device Tree Source (`cma-2g-pci.dts`)

This is the standard DTS structure for reserving memory for a DMA/shared pool, targeted at the Raspberry Pi 5 architecture (`bcm2712`).

```dts
/dts-v1/;
/ {
    compatible = "brcm,bcm2712";

    fragment@0 {
        target = <&reserved_memory>;
        __overlay__ {
            // Reserve 2 GiB (2,147,483,648 bytes) for contiguous use.
            // We use the 'cma-2g-pci' label to explicitly name this pool.
            cma_2g_pci: cma_2g_pci {
                compatible = "shared-dma-pool";
                reusable;
                // Size: 0x80000000 = 2 GiB
                reg = <0x0 0x0 0x0 0x80000000>;
                // Optional: For the 16GB Pi, the kernel's ability to allocate
                // 32-bit DMA memory might be restricted. If the 4GB Pi works,
                // but the 16GB fails, you may need a specific address range (reg = <...>)
                // but for now, let the kernel decide the placement.
            };
        };
    };
};
```

### B. Compile the Overlay

You need the Device Tree Compiler (`dtc`) installed on your running Pi (or a development machine).

1.  **Install DTC:**
    ```bash
    sudo apt update
    sudo apt install device-tree-compiler
    ```
2.  **Compile the file:**
    ```bash
    dtc -@ -I dts -O dtb -o cma-2g-pci.dtbo cma-2g-pci.dts
    ```
    (The `-@` option is critical for including necessary symbols.)
3.  **Copy the compiled overlay:**
    ```bash
    sudo cp cma-2g-pci.dtbo /boot/firmware/overlays/
    ```

### C. Enable the Overlay

Edit the boot configuration file to load the new memory reservation.

1.  **Edit `/boot/firmware/config.txt`**
    ```bash
    sudo nano /boot/firmware/config.txt
    ```
2.  **Add the overlay line:**
    Add the following line to the end of the file:
    ```ini
    dtoverlay=cma-2g-pci
    ```

### D. Verify the Reservation

Reboot the Pi and check the allocated CMA memory.

1.  **Reboot:**
    ```bash
    sudo reboot
    ```
2.  **Check Memory (should show \~2048 MiB):**
    ```bash
    grep CmaTotal /proc/meminfo
    ```
    If successful, the output should show a total CMA size close to 2 GiB.

If this DTO method successfully allocates the memory on the **4GB Pi**, the problem is conclusively isolated to the **16GB model's crowded memory map** (specifically the 32-bit DMA address space), which requires a more complex DTO specifying a base address (`reg = <... @ base>`) to force the allocation into a higher, less crowded 64-bit address region.