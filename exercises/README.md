# Exercises

One folder per module. Work through them **in order** — later modules reuse the
dataset, features, and firmware you build in earlier ones. Each folder has its
own README with step-by-step instructions, expected output, and troubleshooting.

> **Prerequisite:** complete [`../setup-guide.md`](../setup-guide.md) first
> (toolchain, RAK board patch, Python env). Nothing here compiles without it.

| Module | Lab | Kind | Reuses |
|---|---|---|---|
| [`module1-ml-basics`](module1-ml-basics/) | ML basics in Jupyter/Colab — four short exercises | Notebooks | — |
| [`module2-hardware-bringup`](module2-hardware-bringup/) | RAK4631 bring-up: blink → accel read → mic level | PlatformIO ×3 | — |
| [`module3-data-forwarding`](module3-data-forwarding/) | Data pipelines into Edge Impulse (accel forwarder + mic record) | PlatformIO ×2 | M2 |
| [`module4-fan-dataset`](module4-fan-dataset/) | **The Fan Lab** — record a labelled 5-state condition-monitoring dataset | Procedure | M3 |
| [`module5-features`](module5-features/) | Feature engineering: pandas → C on the nRF52840, bit-for-bit matched | Notebook + PlatformIO | M4 |
| [`module6-emlearn`](module6-emlearn/) | emlearn: sklearn Random Forest → C header → on-device (XOR warm-up) | Notebook + PlatformIO | — |
| [`module7-models`](module7-models/) | Build & deploy 3 models on the fan dataset; fill the comparison worksheet | Mixed | M4, M5 |
| [`module8-anomaly`](module8-anomaly/) | Anomaly detection — flag states the classifier was never taught | Notebooks | M4, M7 |
| [`module9-optimisation`](module9-optimisation/) | Quantisation & pruning — shrink the models, measure the deltas | Notebooks | M7 |

## Conventions used throughout

- **Accelerometer:** 100 Hz · windows of 200 samples (2 s) · 50 % overlap.
- **Feature math:** population std (`/N`), biased Fisher kurtosis — C and Python
  match bit-for-bit (validated against golden windows).
- **Audio:** 16 kHz mono PCM · RAK18000 PDM (DATA `WB_IO3`, CLK `WB_IO4`).
- **Serial:** 115200 baud.
- **PlatformIO target:** `board = wiscore_rak4631`, `framework = arduino`.
  Remember to drive **`WB_IO2` HIGH** before `lis.begin()` (RAK1904 slot power).

## Notes

- Firmware here is drafted against the hardware conventions above; some files
  carry `// VERIFY:` comments marking things to confirm on a first hardware
  build-pass.
- Build artifacts (`.pio/`, compiled binaries), captured datasets, and trained
  model files are git-ignored — you generate them as you run the labs.
