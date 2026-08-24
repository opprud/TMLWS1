# Module 5 Exercise — Feature Engineering, from pandas to the nRF52840

Two tracks, in order:

- **Track A — notebooks**: compute time-domain features on WISDM, then on **your own fan dataset** from Module 4 (exported from Edge Impulse), add FFT band energies, choose your on-device feature set.
- **Track B — `features-c/`**: implement the core features + FFT band energy in C on the RAK4631 and **prove numerically** that they match your Python implementation.

⏱ Budget: ~75 min per track.

## Prerequisites

- Python env from the setup guide (`numpy pandas matplotlib scikit-learn jupyterlab`), plus `pip install pyserial` for the validation script.
- Your Module 4 fan dataset in Edge Impulse.
- WISDM dataset: download `WISDM_ar_v1.1_raw.txt` from https://www.cis.fordham.edu/wisdm/dataset.php and place it in `notebooks/Data/`.

---

## Track A — Notebooks

### A1. WISDM walkthrough (`notebooks/01_wisdm_features.ipynb`)

Run top to bottom; stop at every **Question** cell:

1. Load & clean the raw txt (bad lines, stray `;`, zero timestamps).
2. EDA: class balance, per-activity time series, distribution plots.
3. Split **by user** (train: users 1–27, test: 28–36) — why not random? (Same reason as Module 4's split-by-recording rule.)
4. Window: 100 samples @ 20 Hz, 50 % overlap; label = mode of the window.
5. Compute the statistical feature set per axis via `compute_features()`.
6. Baseline logistic regression → **expect ≈ 0.80 accuracy** — plus confusion matrix.
7. Random forest → feature importances → retrain on **top-10** features → compare.

**Expected output:** logistic regression ≈ 80 %, RF ≈ 79 %, top-10 RF ≈ 71 % — small accuracy cost for a 6× smaller feature vector.

### A2. Your fan data (`notebooks/02_fan_features.ipynb`)

1. Export your dataset from EI Studio: **Data acquisition → ⋮ → Export data** (JSON) — or Dashboard → export. Unzip into `notebooks/Data/fan/`. The notebook has loaders for both the EI JSON sample format and plain CSV.
2. Window your recordings (500 samples @ 250 Hz, 50 % overlap) and reuse `compute_features()` from A1.
3. **New — spectral:** compute the FFT of `normal` windows; find the 1× RPM fundamental and check it against your `NOTES.md` nominal RPM (`RPM/60` Hz). Then compute **5 equal band energies over `[0, FS/2)`** per axis — 5 × 25 Hz spanning 0–125 Hz at FS = 250 Hz.
4. Plot per-class feature distributions (boxplots) for: `std`, `rms`, `kurtosis`, `zero-crossings`, each band energy. Which features separate which states?
5. Quick RF + feature importance on the full set (time + spectral).
6. **Decide your on-device feature set** (3–7 per axis) and justify each choice in one sentence (importance / cost / redundancy).
7. Export one **512**-sample window per class to a C header with the provided `window_to_c_array()` helper → you'll use it in Track B. 512 = `FEAT_FFT_N` in `features-c/include/features.h`; change one and you must change the other.

**Expected output:** the 1× RPM peak within ~10 % of the datasheet value; `imbalance` dominating the band containing 1× RPM; `scrape` raising kurtosis and all bands; `blocked` shifting energy between neighbouring bands.

> **Troubleshooting (Track A)**
> - *EI export JSON won't parse*: you exported CBOR. Re-export as JSON, or use the CSV export path in the notebook.
> - *Fundamental peak not where expected*: check the forwarder really ran at 250 Hz (Module 4 checklist) and that `FS` in the notebook matches; a wrong `fs` scales every frequency linearly.
> - *Peak at exactly 50 Hz (or 100 Hz)*: mains hum and its harmonic coupling into the rig, not the fan. At FS = 250 Hz these are genuinely resolved (Nyquist = 125 Hz) rather than aliased — confirm by checking the peak does **not** move when you change fan speed, then look at the second-largest peak.
> - *`blocked` identical to `normal` in every feature*: your blockage was too gentle; re-record that class (Module 4 §6).

---

## Track B — Features in C (`features-c/`)

A PlatformIO project for the RAK4631 that computes, on-device:

- time-domain: **mean, std (population), RMS, min, max, zero-crossings** — one pass, no malloc
- frequency-domain: **512-point FFT → 5 × 25 Hz band energies** at FS = 250 Hz (plain-C DFT by default; real CMSIS-DSP is an optional opt-in, see below)
- execution time of each stage via the **DWT cycle counter** (15.6 ns; `micros()` is far too coarse here — see B4)

### B1. Build & flash

```bash
cd features-c
pio run -e naive -t upload      # default: plain-C DFT, zero external libraries
pio device monitor              # 115200 baud
```

> **FFT backend.** There are two build environments (`platformio.ini`):
> - **`naive`** (default) — a plain-C O(N²) DFT (`band_energies_naive`). Compiles
>   with **zero external libraries**, always works in class. Numerically identical
>   to the FFT and validated by the same golden windows, so B2 is unchanged.
> - **`cmsis`** — the real ARM CMSIS-DSP hardware FFT (`arm_rfft_fast_f32`), which
>   also runs the naive DFT alongside it so you can **compare runtimes** (B4).

### B1b. The CMSIS-DSP FFT build (the runtime comparison)

**Nothing to install — CMSIS-DSP is vendored in `lib/CMSIS-DSP/`:**

```bash
pio run -e cmsis -t upload      # real CMSIS-DSP FFT + timing harness
```

Only the FFT path is committed (115 files, 6.6 MB: `Include/`,
`Source/TransformFunctions/`, `Source/CommonTables/`) — not the ~79 MB of
examples, tests and Python wrappers in the upstream repo. Apache-2.0, upstream
**v1.16.2**, subsetted but unmodified; `lib/CMSIS-DSP/LICENSE` travels with it.

> **Why it is vendored rather than fetched.** The raw `ARM-software/CMSIS-DSP`
> repo is *not* a PlatformIO-packaged library (its `library.json` has no
> `srcFilter`), so putting it in `lib_deps` makes LDF try to compile
> `Examples/.../startup_ARMCM*.c` and fail — and the Adafruit nRF52 BSP ships
> CMSIS *core* only, with no DSP math library to link against. Our glue
> `lib/CMSIS-DSP/library.json` supplies the missing `srcFilter`, compiling just
> the two umbrella translation units the FFT needs:
>
> ```json
> "srcFilter": ["-<*>",
>               "+<Source/TransformFunctions/TransformFunctions.c>",
>               "+<Source/CommonTables/CommonTables.c>"]
> ```
>
> It is committed rather than cloned at setup so the `cmsis` build works with no
> network — Module 5's headline result depends on this env, which is too
> important to gate behind a clone on a locked-down laptop.

To refresh it from upstream (not needed for the course):

```bash
git clone --depth 1 --branch v1.16.2 https://github.com/ARM-software/CMSIS-DSP /tmp/CMSIS-DSP
cp -r /tmp/CMSIS-DSP/Source /tmp/CMSIS-DSP/Include lib/CMSIS-DSP/
```

`.gitignore` keeps everything outside the three needed directories out of the
repo, so the extra ~79 MB never gets committed by accident. The `naive` env
never touches any of this.

The firmware computes features on a **deterministic synthetic golden window** (25 Hz + 40 Hz sines + a small 3.1 Hz sine — the exact same formula exists in the validation script) and prints (the `naive` env):

```
FEATURES_BEGIN
window=synthetic n=512 fs=250.0
axis=x mean=... std=... rms=... min=... max=... zc=...
axis=x band0=... band1=... band2=... band3=... band4=...
timing stats_us=... fft_us=...
FEATURES_END
```

The `cmsis` env adds both FFT timings and an agreement check:

```
timing stats_us=... fft_us=... fft_naive_us=... fft_cmsis_us=... speedup=...
fft_agree max_rel=...           # naive vs CMSIS band energies — must be ~1e-6
```

### B2. Validate against Python

```bash
python validate_features.py --port /dev/cu.usbmodemXXXX      # or COMx / /dev/ttyACM0
```

On macOS use the `/dev/cu.*` node, **not** `/dev/tty.*` — pyserial blocks on the tty node waiting for carrier detect.

The script generates the identical window in numpy, computes the identical features, parses the device output and prints a PASS/FAIL table. It takes `fs` and `n` from the device's own `n=... fs=...` line (override with `--fs` / `--n`) and aborts if they disagree with what it is about to compute — the band edges are `(fs/2)/5`, so a silent `fs` mismatch would fail every `band*` row while all six time-domain rows still pass. **That failure signature — time-domain PASS, all bands FAIL — means the two sides disagree about `fs`, not that your FFT is wrong.**

**Expected output:** every feature `PASS` with relative error `< 1e-4`. Band energies may show slightly larger error (`< 1e-3`) — float32 FFT vs float64 numpy.

### B3. Your own data on-device

1. Run notebook A2 step 7 (notebook section 8) — it writes `win_<label>.h` **and** a matching `win_<label>.csv` for each class directly into `features-c/include/golden/`. No manual copying needed.
2. In `src/main.cpp`, uncomment the golden-file block and point it at your class:

   ```cpp
   #include "golden/win_normal.h"
   #define GOLDEN_WINDOW win_normal
   #define GOLDEN_LEN    WIN_NORMAL_LEN
   ```

   Rebuild and flash — the periodic output now says `window=golden_file`.
3. Re-run the validation script against the auto-generated `.csv` twin of the same window:

   ```bash
   python validate_features.py --port ... --csv include/golden/win_normal.csv
   ```

### B4. Report timing — naive DFT vs CMSIS-DSP FFT

Flash the **`cmsis`** env (B1b) and read the two FFT numbers from one window:

| Stage | µs @ 64 MHz | % of a 2.048 s window |
|---|---|---|
| time-domain stats (512 samples, 1 axis) | 303 | 0.015 % |
| 512-pt band energies — **naive DFT** (`fft_naive_us`) | 6,757,669 | **330 %** |
| 512-pt band energies — **CMSIS-DSP FFT** (`fft_cmsis_us`) | 2,253 | 0.11 % |

Reference values measured on a RAK4631 — yours should land within ~10 %. The firmware
also prints `speedup=` (naive ÷ CMSIS) so you do not have to divide at the bench:
**≈ 3000×**. Feature extraction for all three axes costs 0.37 % duty cycle; the MCU
sleeps the other 99.6 % of the time.

The `fft_agree max_rel` line proves both backends compute the *same* band energies
(~1e-6) — so the only difference you're paying for is speed. The naive O(N²) DFT is
roughly two orders of magnitude slower than the hardware `arm_rfft_fast_f32`; that
gap is the reason real firmware uses CMSIS-DSP.

At N = 512 the naive DFT measures **6.76 s per window** — *3.3× slower than real time*
for 2.048 s of data, and it overruns the firmware's 5 s auto-repeat, so the `naive` env
just runs back-to-back DFTs. Going 256 → 512 cost 4× (O(N²)); that is the headline
number for this exercise. The `naive` env is still the right default for *correctness*
work — it needs no external library — but at this window length only the CMSIS build
could keep up with a live sensor.

> **Measurement caveat — read this before trusting any timing.** `micros()` on this core
> is `dwt_enabled() ? DWT->CYCCNT/64 : tick2us(xTaskGetTickCount())`, and
> `configTICK_RATE_HZ` is **1024**. With no debugger attached DWT is off, so `micros()`
> moves in steps of **976.5625 µs**: the 303 µs stats pass reads as `0`, and the 2,253 µs
> FFT reads as exactly `1953` µs — 2 ticks wearing a microsecond costume. The firmware
> now calls `dwt_timing_enable()` in `setup()`, which sets the two bits `dwt_enabled()`
> tests and gives **15.6 ns** resolution (it also upgrades every other `micros()` call in
> the program to 1 µs). If a timing number is an exact multiple of 976.5625 µs, you are
> reading a tick count, not a measurement.

> **Troubleshooting (Track B)**
> - *Build fails around `arm_math.h` / CMSIS-DSP*: you're on `-e cmsis` but haven't fetched the source — see B1b. The default `-e naive` build needs no CMSIS at all.
> - *std mismatches by a few %*: population vs sample std (`/N` vs `/N-1`). Both sides here use population (`numpy.std` default). If you "fixed" one side, unfix it.
> - *Band energies off by a constant factor*: normalisation mismatch — neither side must scale the forward FFT; check you didn't divide by N on one side only.
> - *zc off by one*: count sign changes of `x[i]-mean` for i=1..N-1, strict product `< 0` (values exactly on the mean don't count). Both implementations use this rule.
> - *No output on monitor*: press RESET; the sketch waits up to 5 s for a serial connection then runs anyway, repeating every 5 s.

## Deliverable

Short summary in your project notes: chosen feature set (with one-line justifications), validation table screenshot/paste, timing table.
